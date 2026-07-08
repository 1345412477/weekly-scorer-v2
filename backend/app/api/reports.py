"""周报 API"""
import os
import re
import uuid
import shutil
import logging
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete

from app.database import get_db
from app.models.models import WeeklyReport, ReportScore, Person, AdminUser, WeeklyAggregate
from app.schemas.schemas import ReportCreate, ReportResponse
from app.services.scoring import trigger_scoring
from app.services.ai_scorer import AIScoringError
from app.core.auth import require_admin, write_operation_log
from app.services.document_parser import (
    parse_report, extract_week_dates, get_template_path,
    classify_report_week, get_current_week, SUPPORTED_EXTENSIONS,
    extract_author_from_filename,
)
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["周报管理"])

from app.utils.file_utils import is_safe_upload_path, get_upload_dir

UPLOAD_DIR = get_upload_dir()


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
    original_filename: str,
    db: AsyncSession,
):
    """
    仅从文件名识别提交人，并在人员库中精确匹配。

    文件名规范（严格要求）：
      「提交人名字-YYYY年MM月第N周周报YYYYMMDD.xlsx」
      例如：张三-2026年6月第2周周报20260614.xlsx

    返回：
      (author_name, department_name, person_id, department_id, detected, dup_hint)

    规则：
      1. 从 extract_author_from_filename 解析首段中文姓名
      2. 精确匹配 persons.name，取 department_name / department_id
      3. 未命中人员库 → detected=False（由调用方抛出 400）
      4. 命中人员但部门为空 → detected=False（由调用方抛出 400）
      5. 姓名命中且有部门信息 → detected=True
    """
    candidate_name, hint = extract_author_from_filename(original_filename)
    if not candidate_name:
        return None, "", None, "", False, ""

    matched_person = None
    dup_hint = ""
    try:
        person_q = select(Person).where(Person.name == candidate_name)
        person_r = await db.execute(person_q)
        persons_found = person_r.scalars().all()

        if len(persons_found) == 0:
            matched_person = None
        elif len(persons_found) == 1:
            matched_person = persons_found[0]
        else:
            # 同名优先取 is_active=True 的
            actives = [p for p in persons_found if getattr(p, "is_active", True)]
            matched_person = actives[0] if actives else persons_found[0]
            dup_hint = f"（存在 {len(persons_found)} 个同名员工，请在管理后台清理）"
            logger.warning(
                f"persons 表中 name={candidate_name!r} 存在多条记录: "
                f"{[(p.id, getattr(p, 'is_active', True)) for p in persons_found]}"
            )
    except Exception as e:
        logger.warning(f"匹配人员库失败: {e}")
        matched_person = None

    if not matched_person:
        return candidate_name, "", None, "", False, ""

    dept_name = matched_person.department_name or ""
    if not dept_name:
        # 存在但未配置部门 → 拒绝
        return candidate_name, "", matched_person.id, matched_person.department_id or "", False, dup_hint

    return (
        matched_person.name,
        dept_name,
        matched_person.id,
        matched_person.department_id or "",
        True,
        dup_hint,
    )


@router.post("/upload")
async def upload_report(
    file: UploadFile = File(...),
    person_id: Optional[str] = Form(None),
    department_id: Optional[str] = Form(None),
    author_name: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    confirmed_week_start: Optional[str] = Form(None),
    confirmed_week_end: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """上传周报文件，仅支持 .xlsx。从文件名自动识别提交人并匹配部门，未在人员库中则拒绝上传。"""
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}，仅支持 .xlsx 文件"
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
            detected_name, detected_dept, detected_person_id, detected_dept_id, detected, dup_hint = await (
                extract_author_and_match_department(original_filename, db)
            )
            if detected:
                author_name = detected_name
                department = detected_dept
                person_id = detected_person_id
                department_id = detected_dept_id
                auto_detected = True
            else:
                # 命中人员但未配置部门 → 拒绝
                if detected_name and not detected_dept:
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=400,
                        detail=f"系统中无员工信息：{detected_name}（未配置部门）{dup_hint}"
                    )
                # 否则：调用方显式提供 author_name + department 则使用之；若均未提供，使用"匿名"兜底
                if not (author_name and department):
                    if author_name and not department:
                        os.remove(file_path)
                        raise HTTPException(
                            status_code=400,
                            detail="提交人已提供但部门信息缺失，无法上传"
                        )
                    # 两者均未提供 → 以"匿名/未填写部门"兜底
                    author_name = author_name or "匿名"
                    department = department or "未填写部门"

        # 最后做一次安全默认值
        department = department or "未填写部门"
        department_id = department_id or None
        author_name = author_name or "匿名"

        # === 同周重复提交检查：同一用户同一周只能有一条周报记录 ===
        dup_q = select(WeeklyReport).where(
            WeeklyReport.author_name == author_name,
            WeeklyReport.week_start == week_start,
        )
        dup_r = await db.execute(dup_q)
        existing_report = dup_r.scalar_one_or_none()
        if existing_report:
            os.remove(file_path)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{author_name} 本周（{week_start.isoformat()}）已提交周报，"
                    f"如需重新提交，请先在周评列表中删除旧周报后再上传。"
                )
            )

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
            submit_time=bj_now(),
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
            except Exception as e:
                logger.warning(f"读取评分详情失败: {e}")

        # 触发周评自动聚合（综合三项分数）
        aggregate_data = None
        try:
            from app.services.aggregator import auto_aggregate
            agg = await auto_aggregate(
                db,
                person_id=report.person_id,
                author_name=author_name,
                department=department,
                department_id=report.department_id,
                week_start=week_start,
                week_end=week_end,
            )
            if agg:
                aggregate_data = {
                    "report_score": float(agg.report_score) if agg.report_score is not None else None,
                    "attendance_score": float(agg.attendance_score) if agg.attendance_score is not None else None,
                    "chat_score": float(agg.chat_score) if agg.chat_score is not None else None,
                    "composite_score": float(agg.composite_score) if agg.composite_score is not None else None,
                }
        except Exception as e:
            logger.warning(f"周报上传后自动聚合失败: {e}")

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
            "content_preview": (content[:300] + "…") if content and len(content) > 300 else (content or ""),
            "total_score": score_result["total_score"] if score_result else None,
            "grade": score_result["grade"] if score_result else None,
            "dimension_scores": dimension_scores,
            "ai_comment": ai_comment,
            "ai_suggestion": ai_suggestion,
            "scoring_error": scoring_error,
            "aggregate": aggregate_data,
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

    # === 同周重复提交检查：同一用户同一周只能有一条周报记录 ===
    dup_q = select(WeeklyReport).where(
        WeeklyReport.author_name == req.author_name,
        WeeklyReport.week_start == ws,
    )
    dup_r = await db.execute(dup_q)
    existing_report = dup_r.scalar_one_or_none()
    if existing_report:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{req.author_name} 本周（{ws.isoformat()}）已存在周报（状态：{existing_report.status}），"
                f"如需重新提交，请先删除旧周报。"
            )
        )

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
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """批量导出周报原始文件为 ZIP"""
    import zipfile
    from io import BytesIO
    import urllib.parse

    # 同时兼容 { "report_ids": [...] } 和 裸数组 [...]
    if isinstance(payload, list):
        report_ids = payload
    else:
        report_ids = payload.get("report_ids") or payload.get("ids") or []
    if not isinstance(report_ids, list):
        raise HTTPException(status_code=400, detail="参数 report_ids 必须是数组")

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
    filename = f"周报_{bj_now().strftime('%Y%m%d')}.zip"
    encoded = urllib.parse.quote(filename)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


@router.post("/batch-delete")
async def batch_delete_reports(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """批量删除周报（同时兼容裸数组 / {report_ids:[...]} / {ids:[...]}）"""
    if isinstance(payload, list):
        report_ids = payload
    else:
        report_ids = payload.get("report_ids") or payload.get("ids") or []
    if not isinstance(report_ids, list) or len(report_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择要删除的周报")
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id.in_(report_ids))
    )
    reports = result.scalars().all()

    # 删除关联的评分记录
    scores_result = await db.execute(
        select(ReportScore).where(ReportScore.report_id.in_(report_ids))
    )
    score_rows = scores_result.scalars().all()
    score_ids = [s.id for s in score_rows]
    for score in score_rows:
        await db.delete(score)

    # 级联删除对应的 WeeklyAggregate，保证仪表盘数据一致
    # 通过 report_score_id 匹配（直接关联） 或 author_name+week_start 匹配（间接关联）
    deleted_aggregates = 0
    if score_ids or reports:
        agg_q = select(WeeklyAggregate).where(
            (WeeklyAggregate.report_score_id.in_(score_ids))
            | (
                (WeeklyAggregate.author_name.in_([r.author_name for r in reports]))
                & (WeeklyAggregate.week_start.in_([r.week_start for r in reports]))
            )
        )
        agg_r = await db.execute(agg_q)
        for agg in agg_r.scalars().all():
            await db.delete(agg)
            deleted_aggregates += 1

    for report in reports:
        await db.delete(report)

    await write_operation_log(db, user, "batch_delete", "report", "", request, {"report_ids": report_ids, "deleted_aggregates": deleted_aggregates})
    await db.commit()
    return {
        "message": "批量删除成功",
        "deleted_count": len(reports),
        "deleted_aggregates": deleted_aggregates,
    }


@router.post("/clear-all")
async def clear_all_reports(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    """清空所有周报和评分数据（保留 draft 状态的周报草稿）"""
    # 1. 收集要删除的周报 ID（非 draft 状态）
    reports_q = await db.execute(
        select(WeeklyReport).where(WeeklyReport.status != "draft")
    )
    reports_to_delete = reports_q.scalars().all()
    report_ids = [r.id for r in reports_to_delete]

    # 2. 删除文件
    deleted_files = 0
    for r in reports_to_delete:
        if r.file_path and os.path.exists(r.file_path):
            try:
                os.remove(r.file_path)
                deleted_files += 1
            except Exception as e:
                logger.warning(f"删除文件失败 {r.file_path}: {e}")

    # 3. 删除关联的 ReportScore
    deleted_scores = 0
    if report_ids:
        scores_r = await db.execute(
            select(func.count()).select_from(ReportScore).where(ReportScore.report_id.in_(report_ids))
        )
        deleted_scores = scores_r.scalar() or 0
        await db.execute(
            delete(ReportScore).where(ReportScore.report_id.in_(report_ids))
        )

    # 4. 删除所有 WeeklyAggregate（定时聚合评分）
    agg_r = await db.execute(
        select(func.count()).select_from(WeeklyAggregate)
    )
    deleted_aggregates = agg_r.scalar() or 0
    await db.execute(delete(WeeklyAggregate))

    # 5. 删除周报
    deleted_reports = len(report_ids)
    if report_ids:
        await db.execute(
            delete(WeeklyReport).where(WeeklyReport.id.in_(report_ids))
        )

    # 6. 记录操作日志
    await write_operation_log(
        db,
        user,
        "clear_all",
        "report",
        "",
        request,
        {
            "deleted_reports": deleted_reports,
            "deleted_scores": deleted_scores,
            "deleted_aggregates": deleted_aggregates,
            "deleted_files": deleted_files,
        },
    )
    await db.commit()

    logger.info(
        f"[clear_all] 管理员 {user.username} 清空了所有评分数据："
        f"{deleted_reports} 条周报 / {deleted_scores} 条评分 / "
        f"{deleted_aggregates} 条聚合分数 / {deleted_files} 个文件"
    )

    return {
        "message": "所有评分数据已清空",
        "deleted_reports": deleted_reports,
        "deleted_scores": deleted_scores,
        "deleted_aggregates": deleted_aggregates,
        "deleted_files": deleted_files,
    }


@router.get("/public/{report_id}")
async def get_public_report(report_id: str, db: AsyncSession = Depends(get_db)):
    """员工端查看周报详情（无需管理员认证，含评分和 AI 评语）"""
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
        "week_start": ws_str,
        "week_end": we_str,
        "week_num": iso_week_number(ws),
        "content": report.content,
        "status": report.status,
        "total_score": float(scores.total_score) if scores else None,
        "grade": scores.grade if scores else None,
        "dimension_scores": dim_scores,
        "ai_comment": scores.ai_comment if scores else None,
        "ai_suggestion": scores.ai_suggestion if scores else None,
        "submit_time": report.submit_time.isoformat() if report.submit_time else None,
        "score_time": report.score_time.isoformat() if report.score_time else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


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
    """提交周报并触发评分与聚合"""
    result = await db.execute(
        select(WeeklyReport).where(WeeklyReport.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="周报不存在")
    if report.status != "draft":
        raise HTTPException(status_code=400, detail="周报已提交，不可重复提交")

    report.status = "submitted"
    report.submit_time = bj_now()
    await db.commit()

    scoring_error = None
    score_result = None
    try:
        score_result = await trigger_scoring(report_id, db)
    except AIScoringError as e:
        scoring_error = str(e)
    except Exception as e:
        scoring_error = f"评分失败：{str(e)}"

    # 触发周评自动聚合（同步到 WeeklyAggregate，周评列表可见）
    aggregate = None
    try:
        from app.services.aggregator import auto_aggregate
        aggregate = await auto_aggregate(
            db,
            person_id=report.person_id,
            author_name=report.author_name,
            department=report.department,
            department_id=report.department_id,
            week_start=report.week_start,
            week_end=report.week_end,
        )
    except Exception as e:
        logger.warning(f"提交周报后自动聚合失败 report_id={report_id}: {e}")

    aggregate_data = None
    if aggregate:
        aggregate_data = {
            "report_score": float(aggregate.report_score) if aggregate.report_score is not None else None,
            "attendance_score": float(aggregate.attendance_score) if aggregate.attendance_score is not None else None,
            "chat_score": float(aggregate.chat_score) if aggregate.chat_score is not None else None,
            "composite_score": float(aggregate.composite_score) if aggregate.composite_score is not None else None,
        }

    if scoring_error:
        return {
            "message": f"提交成功，但{scoring_error}",
            "report_id": report_id,
            "total_score": None,
            "grade": None,
            "scoring_error": scoring_error,
            "aggregate": aggregate_data,
        }

    return {
        "message": "提交并评分成功",
        "report_id": report_id,
        "total_score": score_result["total_score"] if score_result else None,
        "grade": score_result["grade"] if score_result else None,
        "aggregate": aggregate_data,
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
    score_id = score.id if score else None
    if score:
        await db.delete(score)

    # 级联删除对应的 WeeklyAggregate，保证仪表盘数据一致
    deleted_aggregates = 0
    agg_q = select(WeeklyAggregate).where(
        (WeeklyAggregate.report_score_id == score_id)
        | (
            (WeeklyAggregate.author_name == report.author_name)
            & (WeeklyAggregate.week_start == report.week_start)
        )
    )
    agg_r = await db.execute(agg_q)
    for agg in agg_r.scalars().all():
        await db.delete(agg)
        deleted_aggregates += 1

    await db.delete(report)

    await write_operation_log(db, user, "delete", "report", report_id, request,
                              {"author_name": report.author_name, "deleted_aggregates": deleted_aggregates})
    await db.commit()
    return {"message": "周报已删除", "deleted_aggregates": deleted_aggregates}


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
