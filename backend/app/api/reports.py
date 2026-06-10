"""周报 API"""
import os
import uuid
import shutil
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.models import WeeklyReport, ReportScore, Person, AdminUser
from app.schemas.schemas import ReportCreate, ReportResponse
from app.services.scoring import trigger_scoring
from app.services.ai_scorer import AIScoringError
from app.core.auth import require_admin, write_operation_log
from app.services.document_parser import (
    parse_report, extract_week_dates, get_template_path,
    classify_report_week, get_current_week, SUPPORTED_EXTENSIONS,
)

router = APIRouter(prefix="/api/v1/reports", tags=["周报管理"])

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)


def is_safe_upload_path(file_path: str) -> bool:
    if not file_path:
        return False
    resolved_path = os.path.abspath(file_path)
    return resolved_path.startswith(UPLOAD_DIR + os.sep) and os.path.isfile(resolved_path)


def safe_download_name(filename: Optional[str], fallback: str) -> str:
    name = os.path.basename(filename or fallback).replace("\x00", "")
    return name or fallback


def iso_week_number(d):
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.isocalendar()[1]


def build_report_dict(r, scores=None):
    ws = r.week_start
    we = r.week_end
    ws_str = ws.isoformat() if hasattr(ws, "isoformat") else str(ws)
    we_str = we.isoformat() if hasattr(we, "isoformat") else str(we)
    return {
        "id": r.id,
        "author_name": r.author_name,
        "department": r.department or "",
        "person_id": r.person_id,
        "department_id": r.department_id,
        "week_start": ws_str,
        "week_end": we_str,
        "week_num": iso_week_number(ws),
        "content": r.content,
        "status": r.status,
        "report_type": getattr(r, "report_type", "normal") or "normal",
        "week_diff": getattr(r, "week_diff", 0) or 0,
        "total_score": float(scores.total_score) if scores else None,
        "grade": scores.grade if scores else None,
        "original_filename": r.original_filename,
        "submit_time": r.submit_time.isoformat() if r.submit_time else None,
        "score_time": r.score_time.isoformat() if r.score_time else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/template/download")
async def download_template():
    """下载 Excel 周报模板"""
    template_path = get_template_path()
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="模板文件不存在")

    monday, sunday = get_current_week()
    filename = f"周报模板_{monday.strftime('%Y%m%d')}-{sunday.strftime('%Y%m%d')}.xlsx"

    return FileResponse(
        path=template_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


async def extract_author_and_match_department(
    file_path: str,
    original_filename: str,
    parsed_content: dict,
    db: AsyncSession,
):
    """
    从文件内容 / 文件名中尝试识别提交人并匹配部门
    返回 (author_name, department, person_id, department_id, auto_detected: bool)
    """
    import re as _re

    # 1. 先从解析内容的表格数据中查找 "汇报人"
    candidate_name = None
    all_items = parsed_content.get("last_week_work", []) + parsed_content.get("this_week_plan", [])
    for item in all_items:
        reporter = item.get("汇报人") or item.get("提交人") or item.get("姓名")
        if reporter and isinstance(reporter, str) and 2 <= len(reporter.strip()) <= 10:
            candidate_name = reporter.strip()
            break

    # 2. 回退到文件名识别：xxx周报_xxx.xlsx
    if not candidate_name and original_filename:
        stem = os.path.splitext(original_filename)[0]
        match = _re.search(r"[\u4e00-\u9fa5]{2,4}", stem)
        if match:
            candidate_name = match.group(0)

    if not candidate_name:
        return None, "", None, "", False

    # 3. 匹配 persons 表中是否存在此人
    try:
        person_q = select(Person).where(Person.name == candidate_name)
        person_r = await db.execute(person_q)
        person = person_r.scalar_one_or_none()
        if person:
            return (
                person.name,
                person.department_name or "",
                person.id,
                person.department_id or "",
                True,
            )
    except Exception:
        pass

    # 4. 未在人员库中找到，使用识别到的姓名但无部门信息
    return candidate_name, "", None, "", False


@router.post("/upload")
async def upload_report(
    file: UploadFile = File(...),
    person_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    author_name: str = Form("匿名"),
    department: str = Form(""),
    confirmed_week_start: Optional[str] = Form(None),
    confirmed_week_end: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """上传周报文件，支持 .xlsx/.xls/.docx/.pdf。自动识别提交人并匹配部门。"""
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}，支持：{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    original_filename = file.filename or ""

    if person_id:
        person_r = await db.execute(select(Person).where(Person.id == person_id))
        person = person_r.scalar_one_or_none()
        if person:
            author_name = person.name
            if not department and person.department_name:
                department = person.department_name
            if not department_id and person.department_id:
                department_id = person.department_id

    file_id = str(uuid.uuid4())
    saved_filename = f"{file_id}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        parsed = parse_report(file_path)
        week_start, week_end = extract_week_dates(file_path)

        if confirmed_week_start and confirmed_week_end:
            week_start = date.fromisoformat(confirmed_week_start)
            week_end = date.fromisoformat(confirmed_week_end)

        classification = classify_report_week(week_start, week_end)

        if classification["is_future"]:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=classification["message"])

        content = parsed["raw_content"]

        if not content or len(content.strip()) < 20:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="文件内容为空或格式不正确，无法解析周报内容")

        if week_start is None:
            monday, sunday = get_current_week()
            week_start = monday
            week_end = sunday

        # 自动识别提交人并匹配部门（仅当用户未显式指定 person_id 时生效）
        auto_detected = False
        if not person_id:
            detected_name, detected_dept, detected_person_id, detected_dept_id, detected = await (
                extract_author_and_match_department(file_path, original_filename, parsed, db)
            )
            if detected and detected_name:
                author_name = detected_name
                if not department and detected_dept:
                    department = detected_dept
                if detected_person_id:
                    person_id = detected_person_id
                if detected_dept_id:
                    department_id = detected_dept_id
                auto_detected = True

        report_type = classification["report_type"]
        week_diff = classification["week_diff"]

        report = WeeklyReport(
            id=file_id,
            author_name=author_name,
            department=department,
            person_id=person_id,
            department_id=department_id,
            week_start=week_start,
            week_end=week_end,
            content=content,
            file_path=file_path,
            original_filename=original_filename,
            status="submitted",
            report_type=report_type,
            week_diff=week_diff,
            submit_time=datetime.now(timezone(timedelta(hours=8))),
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

        score_result = None
        scoring_error = None
        try:
            score_result = await trigger_scoring(report.id, db)
        except AIScoringError as e:
            scoring_error = str(e)
        except Exception as e:
            scoring_error = f"评分失败：{str(e)}"

        # 评分完成后读取完整 score 信息（含 ai_comment / ai_suggestion）
        dimension_scores = []
        ai_comment = ""
        ai_suggestion = ""
        if score_result and not scoring_error:
            try:
                detail_q = select(ReportScore).where(ReportScore.report_id == report.id)
                detail_r = await db.execute(detail_q)
                score_row = detail_r.scalar_one_or_none()
                if score_row:
                    dimension_scores = score_row.dimension_scores or []
                    ai_comment = score_row.ai_comment or ""
                    ai_suggestion = score_row.ai_suggestion or ""
            except Exception:
                pass

        result = {
            "message": "上传成功",
            "report_id": report.id,
            "report_type": report_type,
            "week_diff": week_diff,
            "classification_message": classification["message"],
            "needs_confirmation": classification["needs_confirmation"],
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "author_name": author_name,
            "department": department,
            "auto_detected": auto_detected,
            "total_score": score_result["total_score"] if score_result else None,
            "grade": score_result["grade"] if score_result else None,
            "dimension_scores": dimension_scores,
            "ai_comment": ai_comment,
            "ai_suggestion": ai_suggestion,
            "scoring_error": scoring_error,
        }

        if scoring_error:
            result["message"] = f"上传成功，但评分失败：{scoring_error}"
        elif report_type == "catch_up":
            result["message"] = f"补周报上传成功（{week_diff}周前）"
        elif report_type == "normal":
            result["message"] = "本周周报上传成功"

        if classification["needs_confirmation"]:
            if scoring_error:
                result["message"] = f"上传成功，但未能自动识别周报时间，且评分失败：{scoring_error}"
            else:
                result["message"] = "上传成功，但未能自动识别周报时间，请确认"

        return result

    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")


@router.post("")
async def create_report(req: ReportCreate, db: AsyncSession = Depends(get_db)):
    """创建/保存周报草稿"""
    monday, sunday = get_current_week()
    ws = req.week_start or monday
    we = req.week_end or sunday

    report = WeeklyReport(
        id=str(uuid.uuid4()),
        author_name=req.author_name,
        department=req.department or "",
        person_id=req.person_id,
        department_id=req.department_id,
        week_start=ws,
        week_end=we,
        content=req.content,
        template_id=req.template_id,
        status="draft",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return {"message": "周报已保存", "id": report.id, "status": "draft"}


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    author_name: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    is_catch_up: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("desc"),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """获取周报列表"""
    query = select(WeeklyReport)
    count_query = select(func.count()).select_from(WeeklyReport)

    if status:
        statuses = status.split(",")
        query = query.where(WeeklyReport.status.in_(statuses))
        count_query = count_query.where(WeeklyReport.status.in_(statuses))

    if author_name:
        query = query.where(WeeklyReport.author_name.contains(author_name))
        count_query = count_query.where(WeeklyReport.author_name.contains(author_name))
    if department:
        query = query.where(WeeklyReport.department.contains(department))
        count_query = count_query.where(WeeklyReport.department.contains(department))
    if is_catch_up == "yes":
        query = query.where(WeeklyReport.report_type == "catch_up")
        count_query = count_query.where(WeeklyReport.report_type == "catch_up")
    elif is_catch_up == "no":
        query = query.where(WeeklyReport.report_type == "normal")
        count_query = count_query.where(WeeklyReport.report_type == "normal")

    # 排序
    sort_col = WeeklyReport.created_at
    if sort_by == "week":
        sort_col = WeeklyReport.week_start
    elif sort_by == "submit_time":
        sort_col = WeeklyReport.submit_time

    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(desc(sort_col))

    total_r = await db.execute(count_query)
    total = total_r.scalar() or 0

    result = await db.execute(query.offset((page - 1) * size).limit(size))
    reports = result.scalars().all()

    report_ids = [r.id for r in reports]
    scores_map = {}
    if report_ids:
        scores_r = await db.execute(
            select(ReportScore).where(ReportScore.report_id.in_(report_ids))
        )
        for s in scores_r.scalars().all():
            scores_map[s.report_id] = s

    items = [build_report_dict(r, scores_map.get(r.id)) for r in reports]

    return {"items": items, "total": total, "page": page, "size": size}


@router.post("/export")
async def export_reports(
    report_ids: list[str],
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """批量导出周报原始文件为 ZIP"""
    import zipfile
    from io import BytesIO
    import urllib.parse

    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id.in_(report_ids))
    )
    reports = result.scalars().all()

    if not reports:
        raise HTTPException(status_code=404, detail="未找到所选周报")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        added = set()
        for r in reports:
            if is_safe_upload_path(r.file_path):
                base_name = safe_download_name(r.original_filename, f"{r.author_name}_周报.xlsx")
                name = base_name
                counter = 1
                while name in added:
                    stem, ext = os.path.splitext(base_name)
                    name = f"{stem}_{counter}{ext}"
                    counter += 1
                added.add(name)
                zf.write(os.path.abspath(r.file_path), name)

    if not added:
        raise HTTPException(status_code=404, detail="所选周报没有可下载的文件")

    await write_operation_log(
        db,
        user,
        "export",
        "report",
        "",
        request,
        {"report_ids": report_ids, "exported_count": len(added)},
    )
    await db.commit()

    zip_buffer.seek(0)
    filename = f"周报_{datetime.now().strftime('%Y%m%d')}.zip"
    encoded = urllib.parse.quote(filename)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.post("/batch-delete")
async def batch_delete_reports(
    report_ids: list[str],
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """批量删除周报"""
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id.in_(report_ids))
    )
    reports = result.scalars().all()

    # 删除关联的评分记录
    scores_result = await db.execute(
        select(ReportScore).where(ReportScore.report_id.in_(report_ids))
    )
    for score in scores_result.scalars().all():
        await db.delete(score)

    for report in reports:
        await db.delete(report)

    await write_operation_log(db, user, "batch_delete", "report", "", request, {"report_ids": report_ids})
    await db.commit()
    return {"message": "批量删除成功", "deleted_count": len(reports)}


@router.get("/{report_id}")
async def get_report(report_id: str, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    """获取周报详情（含评分维度）"""
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="周报不存在")

    scores_r = await db.execute(
        select(ReportScore).where(ReportScore.report_id == report_id)
    )
    scores = scores_r.scalar_one_or_none()

    ws = report.week_start
    we = report.week_end
    ws_str = ws.isoformat() if hasattr(ws, "isoformat") else str(ws)
    we_str = we.isoformat() if hasattr(we, "isoformat") else str(we)

    dim_scores = []
    if scores and scores.dimension_scores:
        dim_scores = scores.dimension_scores

    return {
        "id": report.id,
        "author_name": report.author_name,
        "department": report.department or "",
        "person_id": report.person_id,
        "department_id": report.department_id,
        "week_start": ws_str,
        "week_end": we_str,
        "week_num": iso_week_number(ws),
        "content": report.content,
        "status": report.status,
        "report_type": getattr(report, "report_type", "normal") or "normal",
        "week_diff": getattr(report, "week_diff", 0) or 0,
        "total_score": float(scores.total_score) if scores else None,
        "grade": scores.grade if scores else None,
        "dimension_scores": dim_scores,
        "ai_comment": scores.ai_comment if scores else None,
        "ai_suggestion": scores.ai_suggestion if scores else None,
        "original_filename": report.original_filename,
        "submit_time": report.submit_time.isoformat() if report.submit_time else None,
        "score_time": report.score_time.isoformat() if report.score_time else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.post("/{report_id}/submit")
async def submit_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """提交周报并触发评分"""
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="周报不存在")
    if report.status != "draft":
        raise HTTPException(status_code=400, detail="周报已提交，不可重复提交")

    report.status = "submitted"
    report.submit_time = datetime.now(timezone(timedelta(hours=8)))
    await db.commit()

    try:
        score_result = await trigger_scoring(report_id, db)
        return {
            "message": "提交并评分成功",
            "report_id": report_id,
            "total_score": score_result["total_score"],
            "grade": score_result["grade"],
        }
    except AIScoringError as e:
        return {
            "message": f"提交成功，但评分失败：{str(e)}",
            "report_id": report_id,
            "total_score": None,
            "grade": None,
            "scoring_error": str(e),
        }
    except Exception as e:
        error_msg = f"评分失败：{str(e)}"
        return {
            "message": f"提交成功，但{error_msg}",
            "report_id": report_id,
            "total_score": None,
            "grade": None,
            "scoring_error": error_msg,
        }


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """删除周报"""
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="周报不存在")

    scores_r = await db.execute(
        select(ReportScore).where(ReportScore.report_id == report_id)
    )
    score = scores_r.scalar_one_or_none()
    if score:
        await db.delete(score)

    await db.delete(report)

    await write_operation_log(db, user, "delete", "report", report_id, request, {"author_name": report.author_name})
    await db.commit()
    return {"message": "周报已删除"}


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """下载周报原始文件"""
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="周报不存在")

    if not is_safe_upload_path(report.file_path):
        raise HTTPException(status_code=404, detail="文件不存在，可能已被清理")

    await write_operation_log(
        db,
        user,
        "download",
        "report",
        report_id,
        request,
        {"filename": report.original_filename},
    )
    await db.commit()

    return FileResponse(
        os.path.abspath(report.file_path),
        filename=safe_download_name(report.original_filename, f"周报_{report.author_name}.xlsx"),
        media_type="application/octet-stream",
    )
