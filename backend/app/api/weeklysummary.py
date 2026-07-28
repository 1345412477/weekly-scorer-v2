"""一周小结上传 API（员工端首页使用）

设计原则：
- 仅接受图片文件上传（.png / .jpg / .jpeg）
- OCR 失败或关键字段缺失时返回明确 400 错误，不做任何兜底策略
"""
import os
import uuid
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import WeeklySummary, Person
from app.services.ocr_service import parse_summary_image, infer_week_range, OCRParseError
from app.services.aggregator import auto_aggregate
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/weeklysummary", tags=["一周小结"])

UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "weeklysummary")
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg"}


@router.post("/upload")
async def upload_summary(
    file: UploadFile = File(..., description="一周小结图片，仅支持 .png / .jpg / .jpeg"),
    db: AsyncSession = Depends(get_db),
):
    """上传一周小结图片，OCR 解析后写入 weekly_summaries 并触发自动聚合.

    不提供文本兜底、不提供手动填写姓名；任何无法识别情况返回明确错误。
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="请上传一周小结图片")

    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise HTTPException(status_code=400, detail="仅支持 .png / .jpg / .jpeg 图片格式")

    try:
        image_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    if not image_bytes:
        raise HTTPException(status_code=400, detail="上传的图片为空，请重新选择")

    # 保存源文件
    saved_name = f"{uuid.uuid4()}{ext}"
    saved_path = os.path.join(UPLOAD_DIR, saved_name)
    with open(saved_path, "wb") as f:
        f.write(image_bytes)

    # OCR 解析（失败直接抛 400，无兜底）
    try:
        parsed = await parse_summary_image(image_bytes, filename, db=db)
    except OCRParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.warning(f"[一周小结] OCR 解析异常: {e}")
        raise HTTPException(status_code=400, detail=f"图片解析失败: {e}")

    resolved_name = (parsed.get("author_name") or "").strip()
    if not resolved_name:
        raise HTTPException(status_code=400, detail="未识别到员工姓名，请确认图片内容清晰完整")

    # 匹配人员库（仅用于部门填充；匹配不到不拦截，但会在聚合时按姓名对齐）
    person = None
    try:
        res = await db.execute(select(Person).where(Person.name == resolved_name).limit(1))
        person = res.scalar_one_or_none()
    except Exception as e:
        logger.warning(f"匹配人员库失败: {e}")

    department_name = (person.department_name or "") if person else ""
    department_id = (person.department_id or "") if person else ""

    # 周范围
    ws = parsed.get("week_start")
    we = parsed.get("week_end")
    week_start: Optional[date] = None
    week_end: Optional[date] = None
    try:
        if ws:
            week_start = date.fromisoformat(str(ws))
    except Exception:
        week_start = None
    try:
        if we:
            week_end = date.fromisoformat(str(we))
    except Exception:
        week_end = None

    if not week_start or not week_end:
        week_start, week_end = infer_week_range()

    # 写入 weekly_summaries（一周一人一条，重复则更新）
    existing_res = await db.execute(
        select(WeeklySummary).where(
            WeeklySummary.author_name == resolved_name,
            WeeklySummary.week_start == week_start,
            WeeklySummary.week_end == week_end,
        ).limit(1)
    )
    summary = existing_res.scalar_one_or_none()

    work_session_count = parsed.get("work_session_count")
    if work_session_count is not None:
        try:
            work_session_count = int(work_session_count)
        except Exception:
            work_session_count = None

    total_minutes = parsed.get("total_minutes")
    if total_minutes is not None:
        try:
            total_minutes = int(total_minutes)
        except Exception:
            total_minutes = None

    latest_time_parsed = None
    if parsed.get("latest_time"):
        try:
            latest_time_parsed = datetime.strptime(str(parsed["latest_time"]), "%H:%M").time()
        except Exception:
            latest_time_parsed = None

    if summary:
        summary.work_session_count = work_session_count
        summary.total_minutes = total_minutes
        summary.latest_time = (parsed.get("latest_time") or "")
        summary.latest_time_parsed = latest_time_parsed
        summary.raw_ocr_text = (parsed.get("raw_ocr_text") or "")
        summary.source_file = saved_name
        summary.updated_at = bj_now()
    else:
        summary = WeeklySummary(
            id=str(uuid.uuid4()),
            person_id=(person.id if person else None),
            author_name=resolved_name,
            department=department_name,
            department_id=department_id,
            week_start=week_start,
            week_end=week_end,
            work_session_count=work_session_count,
            total_minutes=total_minutes,
            latest_time=(parsed.get("latest_time") or ""),
            latest_time_parsed=latest_time_parsed,
            raw_ocr_text=(parsed.get("raw_ocr_text") or ""),
            source_file=saved_name,
        )
        db.add(summary)

    await db.commit()
    await db.refresh(summary)

    # 触发自动聚合（参与沟通分口径）
    aggregate = None
    try:
        aggregate = await auto_aggregate(
            db,
            person_id=(person.id if person else None),
            author_name=resolved_name,
            department=department_name,
            department_id=department_id,
            week_start=week_start,
            week_end=week_end,
        )
    except Exception as e:
        logger.warning(f"[一周小结] 自动聚合失败: {e}")

    return {
        "message": "一周小结上传成功",
        "summary_id": summary.id,
        "author_name": resolved_name,
        "work_session_count": summary.work_session_count,
        "total_minutes": summary.total_minutes,
        "latest_time": summary.latest_time,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "aggregate": {
            "report_score": float(aggregate.report_score) if aggregate and aggregate.report_score is not None else None,
            "attendance_score": float(aggregate.attendance_score) if aggregate and aggregate.attendance_score is not None else None,
            "chat_score": float(aggregate.chat_score) if aggregate and aggregate.chat_score is not None else None,
            "composite_score": float(aggregate.composite_score) if aggregate and aggregate.composite_score is not None else None,
        } if aggregate else None,
    }
