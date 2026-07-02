"""统一评分 API（管理员端使用）

流程：
1. 对所有未评分的周报执行 AI 评分
2. 对所有未识别的一周小结图片执行 OCR
3. 对所有有数据的（员工+周）组合执行三项聚合（周报/考勤/沟通）

上传不触发任何评分操作；评分集中在此处一次性执行。
"""
import os
import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.database import get_db
from app.core.auth import require_admin
from app.models.models import WeeklyReport, WeeklySummary, AttendanceRecord, ChatRecord, Person
from app.services.ocr_service import parse_summary_image, OCRParseError
from app.services.scoring import trigger_scoring
from app.services.aggregator import auto_aggregate
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scoring", tags=["统一评分"])


async def _get_valid_person_names(db: AsyncSession) -> set:
    """获取人员库中所有启用人员的姓名集合（用于过滤非本单位人员）"""
    result = await db.execute(
        select(Person.name).where(Person.is_active == True)
    )
    names = {row[0] for row in result.all() if row[0]}
    logger.info(f"[scoring] 人员库共 {len(names)} 位启用人员")
    return names

# 与 upload_unified.py 保持一致
SUMMARY_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "weeklysummary")
)
os.makedirs(SUMMARY_UPLOAD_DIR, exist_ok=True)


async def _score_all_reports(db: AsyncSession, valid_names: set) -> dict:
    """查找所有未评分周报（author_name 需在人员库中）并执行 AI 评分"""
    result = await db.execute(
        select(WeeklyReport).where(
            or_(WeeklyReport.status != "scored", WeeklyReport.status.is_(None))
        )
    )
    all_reports = result.scalars().all()

    reports = [r for r in all_reports if r.author_name in valid_names]
    skipped = len(all_reports) - len(reports)
    if skipped > 0:
        logger.info(f"[scoring] 跳过 {skipped} 份周报（提交人不在人员库中，跳过评分")

    if not reports:
        logger.info("[scoring] 无待评分周报，跳过")
        return {"total": 0, "scored": 0, "skipped": skipped, "errors": []}

    logger.info(f"[scoring] 开始 AI 评分 {len(reports)} 份周报")
    scored = 0
    errors = []
    for idx, report in enumerate(reports, 1):
        try:
            await trigger_scoring(report.id, db)
            scored += 1
            logger.info(f"[scoring] 周报 {idx}/{len(reports)} - {report.author_name} 评分完成")
        except Exception as e:
            logger.warning(f"[scoring] 周报 {idx}/{len(reports)} - report_id={report.id} 失败: {e}")
            errors.append({"author_name": report.author_name, "error": str(e)})

    return {"total": len(reports), "scored": scored, "skipped": skipped, "errors": errors}


async def _ocr_all_summaries(db: AsyncSession, valid_names: set) -> dict:
    """查找所有未 OCR 的一周小结并识别（仅处理人员库中的人员）"""
    result = await db.execute(
        select(WeeklySummary).where(WeeklySummary.work_session_count.is_(None))
    )
    all_summaries = result.scalars().all()

    summaries = [s for s in all_summaries if s.author_name in valid_names]
    skipped = len(all_summaries) - len(summaries)
    if skipped > 0:
        logger.info(f"[scoring] 跳过 {skipped} 份一周小结（提交人不在人员库中）")

    if not summaries:
        logger.info("[scoring] 无未识别的一周小结，跳过")
        return {"total": 0, "processed": 0, "skipped": skipped, "errors": []}

    logger.info(f"[scoring] 开始 OCR {len(summaries)} 份一周小结")
    processed = 0
    errors = []
    for idx, summary in enumerate(summaries, 1):
        if not summary.source_file:
            errors.append({
                "author_name": summary.author_name,
                "error": "未记录图片文件，无法识别",
            })
            continue
        image_path = os.path.join(SUMMARY_UPLOAD_DIR, summary.source_file)
        if not os.path.exists(image_path):
            errors.append({
                "author_name": summary.author_name,
                "error": f"图片文件不存在: {summary.source_file}",
            })
            continue
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            parsed = await parse_summary_image(
                image_bytes, summary.source_file,
                override_author_name=summary.author_name,
            )
            try:
                summary.work_session_count = (
                    int(parsed.get("work_session_count"))
                    if parsed.get("work_session_count") is not None else None
                )
            except Exception:
                summary.work_session_count = None
            try:
                summary.total_minutes = (
                    int(parsed.get("total_minutes"))
                    if parsed.get("total_minutes") is not None else None
                )
            except Exception:
                summary.total_minutes = None
            summary.latest_time = (parsed.get("latest_time") or "")
            summary.raw_ocr_text = (parsed.get("raw_ocr_text") or "")
            summary.updated_at = bj_now()
            await db.commit()
            processed += 1
            logger.info(f"[scoring] 一周小结 {idx}/{len(summaries)} - {summary.author_name} 识别完成")
        except OCRParseError as e:
            logger.warning(f"[scoring] 一周小结 OCR 失败 {idx}/{len(summaries)} - summary_id={summary.id}: {e}")
            errors.append({"author_name": summary.author_name, "error": str(e)})
        except Exception as e:
            logger.warning(f"[scoring] 一周小结异常 {idx}/{len(summaries)} - summary_id={summary.id}: {e}")
            errors.append({"author_name": summary.author_name, "error": str(e)})

    return {"total": len(summaries), "processed": processed, "skipped": skipped, "errors": errors}


async def _aggregate_all(db: AsyncSession, valid_names: set) -> dict:
    """扫描所有（员工+周）组合并执行三项聚合（仅处理人员库中的员工）
    
    注：此函数为管理员手动触发的统一评分，不是常规 API。
    数据量预期在正常范围（数百员工 × 数十周），全量扫描可接受。
    """
    MAX_WEEK_KEYS = 2000
    week_keys = set()

    queries = [
        select(WeeklyReport.author_name, WeeklyReport.person_id,
               WeeklyReport.department, WeeklyReport.department_id,
               WeeklyReport.week_start, WeeklyReport.week_end),
        select(WeeklySummary.author_name, WeeklySummary.person_id,
               WeeklySummary.department, WeeklySummary.department_id,
               WeeklySummary.week_start, WeeklySummary.week_end),
        select(AttendanceRecord.author_name, AttendanceRecord.person_id,
               AttendanceRecord.department, AttendanceRecord.department_id,
               AttendanceRecord.week_start, AttendanceRecord.week_end),
        select(ChatRecord.author_name, ChatRecord.person_id,
               ChatRecord.department, ChatRecord.department_id,
               ChatRecord.week_start, ChatRecord.week_end),
    ]

    for q in queries:
        result = await db.execute(q)
        for row in result.all():
            author_name, person_id, dept, dept_id, ws, we = row
            if author_name and ws and we and author_name in valid_names:
                week_keys.add((author_name, person_id or None, dept or "", dept_id or None, ws, we))

    if len(week_keys) > MAX_WEEK_KEYS:
        logger.warning(f"[scoring] 待聚合组合数 {len(week_keys)} 超过上限 {MAX_WEEK_KEYS}，可能影响性能")

    aggregated = 0
    skipped_non_person = 0
    errors = []
    logger.info(f"[scoring] 开始聚合 {len(week_keys)} 个（员工+周）组合")
    for idx, (author_name, person_id, dept, dept_id, ws, we) in enumerate(week_keys, 1):
        try:
            await auto_aggregate(
                db,
                person_id=person_id,
                author_name=author_name,
                department=dept,
                department_id=dept_id,
                week_start=ws,
                week_end=we,
            )
            aggregated += 1
            if idx % 10 == 0 or idx == len(week_keys):
                logger.info(f"[scoring] 聚合 {idx}/{len(week_keys)} 完成")
        except Exception as e:
            logger.warning(f"[scoring] 聚合失败 {idx}/{len(week_keys)} - {author_name} {ws}-{we}: {e}")
            errors.append({"author_name": author_name, "week": f"{ws}~{we}", "error": str(e)})

    return {"total": len(week_keys), "aggregated": aggregated, "skipped": skipped_non_person, "errors": errors}


@router.post("/run")
async def run_scoring(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_admin),
):
    """统一评分：对所有已提交材料进行 OCR、AI 评分、聚合（仅处理人员库中的员工）"""
    t0 = time.time()
    logger.info("[scoring] ========== 统一评分流程启动 ==========")

    valid_names = await _get_valid_person_names(db)
    if not valid_names:
        logger.warning("[scoring] 人员库为空，无法进行任何评分")
        return {
            "message": "人员库为空，请先添加员工",
            "elapsed_seconds": round(time.time() - t0, 2),
            "reports": {"total": 0, "scored": 0, "skipped": 0, "errors": []},
            "summaries": {"total": 0, "processed": 0, "skipped": 0, "errors": []},
            "aggregates": {"total": 0, "aggregated": 0, "skipped": 0, "errors": []},
        }

    report_result = await _score_all_reports(db, valid_names)
    summary_result = await _ocr_all_summaries(db, valid_names)
    aggregate_result = await _aggregate_all(db, valid_names)

    elapsed = round(time.time() - t0, 2)
    logger.info(f"[scoring] ========== 统一评分完成，耗时 {elapsed}s ==========")

    return {
        "message": "评分完成",
        "elapsed_seconds": elapsed,
        "reports": report_result,
        "summaries": summary_result,
        "aggregates": aggregate_result,
    }
