"""周报 + 一周小结 联合上传 API（员工端首页使用）

设计原则：
- 必须同时上传周报文件（.xlsx）与一周小结图片（.png / .jpg / .jpeg）
- 统一使用「周报文件名」识别的提交人姓名作为一周小结的员工姓名
- 任何解析失败均返回明确错误，不做兜底策略
"""
import os
import uuid
import logging
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import WeeklySummary, WeeklyReport
from app.services.document_parser import (
    parse_report,
    extract_week_dates,
    classify_report_week,
    get_current_week,
)
# 复用 reports 模块中的姓名/部门识别函数
from app.api.reports import extract_author_and_match_department
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/upload", tags=["联合上传"])

UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "weeklysummary")
)
REPORT_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "reports")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(REPORT_UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg"}
ALLOWED_REPORT_EXT = {".xlsx"}


@router.post("/unified")
async def upload_unified(
    report: UploadFile = File(..., description="周报文件，仅支持 .xlsx"),
    summary: UploadFile = File(..., description="一周小结图片，仅支持 .png / .jpg / .jpeg"),
    db: AsyncSession = Depends(get_db),
):
    # 1. 文件格式校验
    if not report or not report.filename:
        raise HTTPException(status_code=400, detail="请上传周报文件")
    if not summary or not summary.filename:
        raise HTTPException(status_code=400, detail="请上传一周小结图片")

    report_ext = os.path.splitext(report.filename or "")[1].lower()
    if report_ext not in ALLOWED_REPORT_EXT:
        raise HTTPException(status_code=400, detail=f"周报仅支持 .xlsx 格式（当前文件：{report.filename}）")

    summary_ext = os.path.splitext(summary.filename or "")[1].lower()
    if summary_ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="一周小结仅支持 .png / .jpg / .jpeg 图片格式")

    # 2. 读取并保存文件
    try:
        report_bytes = await report.read()
        summary_bytes = await summary.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    if not report_bytes:
        raise HTTPException(status_code=400, detail="上传的周报文件为空，请重新选择")
    if not summary_bytes:
        raise HTTPException(status_code=400, detail="上传的一周小结图片为空，请重新选择")

    report_file_id = str(uuid.uuid4())
    report_saved_name = f"{report_file_id}{report_ext}"
    report_path = os.path.join(REPORT_UPLOAD_DIR, report_saved_name)
    with open(report_path, "wb") as f:
        f.write(report_bytes)

    summary_file_id = str(uuid.uuid4())
    summary_saved_name = f"{summary_file_id}{summary_ext}"
    summary_path = os.path.join(UPLOAD_DIR, summary_saved_name)
    with open(summary_path, "wb") as f:
        f.write(summary_bytes)

    # 3. 解析周报内容 / 周区间
    try:
        report_parsed = parse_report(report_path)
        week_start, week_end = extract_week_dates(report_path)
        classification = classify_report_week(week_start, week_end)
        if classification.get("is_future"):
            raise HTTPException(status_code=400, detail=classification.get("message", "周报所属时间在未来"))

        if not report_parsed or not (report_parsed.get("raw_content") or "").strip():
            raise HTTPException(status_code=400, detail="周报内容为空或格式不正确，无法解析")

        if week_start is None:
            week_start, week_end = get_current_week()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[unified] 周报解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"周报解析失败: {e}")

    # 4. 从周报文件名识别提交人姓名与部门（与 /reports/upload 保持一致）
    try:
        detected_name, detected_dept, detected_person_id, detected_dept_id, detected, dup_hint = (
            await extract_author_and_match_department(report.filename or "", db)
        )
    except Exception as e:
        logger.warning(f"[unified] 识别提交人失败: {e}")
        raise HTTPException(status_code=400, detail=f"识别提交人失败: {e}")

    if not detected:
        raise HTTPException(
            status_code=400,
            detail=f"系统中无员工信息：{detected_name or '（文件名需为「姓名-YYYY年MM月第N周周报YYYYMMDD.xlsx」）'}{dup_hint}",
        )
    if not detected_dept:
        raise HTTPException(
            status_code=400,
            detail=f"系统中无员工信息：{detected_name}（未配置部门）{dup_hint}",
        )

    author_name = detected_name
    department = detected_dept
    person_id = detected_person_id
    department_id = detected_dept_id

    # 4b. 同周重复提交检查（与 /reports/upload 保持一致）
    existing_q = select(WeeklyReport).where(
        WeeklyReport.author_name == author_name,
        WeeklyReport.week_start == week_start,
    )
    existing_r = await db.execute(existing_q)
    if existing_r.scalar_one_or_none():
        # 清理已保存的文件（不会写入 DB 记录）
        try:
            os.remove(report_path)
            os.remove(summary_path)
        except OSError:
            pass
        raise HTTPException(
            status_code=409,
            detail=(
                f"{author_name} 本周（{week_start.isoformat()}）已提交周报，"
                f"如需重新提交，请先在周评列表中删除旧周报后再上传。"
            ),
        )

    # 5. 写入周报记录（随后立即触发后台异步 AI 评分，不阻塞当前请求）
    report_record = WeeklyReport(
        id=report_file_id,
        author_name=author_name,
        department=department,
        person_id=person_id,
        department_id=department_id,
        week_start=week_start,
        week_end=week_end,
        content=report_parsed.get("raw_content", ""),
        file_path=report_path,
        original_filename=report.filename or "",
        status="submitted",
        report_type=classification.get("report_type"),
        week_diff=classification.get("week_diff", 0),
        submit_time=bj_now(),
    )
    db.add(report_record)
    try:
        await db.commit()
        await db.refresh(report_record)
    except Exception as e:
        logger.warning(f"[unified] 写入周报记录失败: {e}")
        raise HTTPException(status_code=400, detail=f"写入周报记录失败: {e}")

    # 6. 写入一周小结记录（同样立即触发后台 OCR）
    existing_sum = await db.execute(
        select(WeeklySummary).where(
            WeeklySummary.author_name == author_name,
            WeeklySummary.week_start == week_start,
            WeeklySummary.week_end == week_end,
        ).limit(1)
    )
    existing_summary = existing_sum.scalar_one_or_none()

    if existing_summary:
        existing_summary.source_file = summary_saved_name
        existing_summary.updated_at = bj_now()
        summary_record = existing_summary
    else:
        summary_record = WeeklySummary(
            id=summary_file_id,
            person_id=person_id,
            author_name=author_name,
            department=department,
            department_id=department_id,
            week_start=week_start,
            week_end=week_end,
            source_file=summary_saved_name,
        )
        db.add(summary_record)

    try:
        await db.commit()
        await db.refresh(summary_record)
    except Exception as e:
        logger.warning(f"[unified] 写入一周小结记录失败: {e}")
        raise HTTPException(status_code=400, detail=f"写入一周小结记录失败: {e}")

    # 7. 立即在后台触发异步周报 AI 评分 + 一周小结 OCR（不阻塞本次请求）
    from app.core.task_queue import submit_report_scoring, submit_summary_ocr
    try:
        submit_report_scoring(report_record.id)
        submit_summary_ocr(summary_record.id)
        logger.info(f"[unified] 已提交异步任务：report_id={report_record.id}, summary_id={summary_record.id}")
    except Exception as e:
        logger.warning(f"[unified] 提交异步任务失败（不影响提交）: {e}")

    return {
        "message": "提交成功，AI 正在评分中",
        "report_id": report_record.id,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "author_name": author_name,
        "department": department,
        "auto_detected": True,
        "report_type": classification.get("report_type"),
        "week_diff": classification.get("week_diff", 0),
        "summary": {
            "id": summary_record.id,
            "author_name": summary_record.author_name,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
        },
    }
