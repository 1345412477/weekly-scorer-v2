"""周评综合列表 API（管理员端查看/修改三项分数）"""
import logging
import os
import uuid
from io import BytesIO
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from app.utils.time_utils import bj_today

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.models import WeeklyAggregate, WeeklyReport, ReportScore, Person, WeeklySummary
from app.core.auth import require_admin, write_operation_log
from app.services.aggregator import list_aggregates, update_aggregate_scores, restore_ai_scores
from app.utils.file_utils import is_safe_upload_path
from app.utils.time_utils import bj_now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/weekly-aggregates", tags=["周评列表"])


@router.get("")
async def get_aggregates(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    author_name: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    week_start: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """分页获取周评列表（含三项分数与综合分）"""
    ws = None
    if week_start:
        try:
            ws = date.fromisoformat(week_start)
        except Exception:
            raise HTTPException(status_code=400, detail="week_start 格式错误，应为 YYYY-MM-DD")

    return await list_aggregates(db, page=page, size=size,
                                  author_name=author_name, department=department,
                                  week_start=ws)


@router.put("/{aggregate_id}")
async def put_aggregate(
    aggregate_id: str,
    payload: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """管理员手动修改三项分数之一。composite_score 不允许直接传入，由后端自动计算."""
    report_score = payload.get("report_score")
    attendance_score = payload.get("attendance_score")
    chat_score = payload.get("chat_score")

    # 禁止直接传入 composite_score
    if "composite_score" in payload:
        raise HTTPException(status_code=400, detail="composite_score 不允许直接修改，由系统自动计算")

    # 至少一项
    provided = []
    if report_score is not None:
        try:
            report_score = float(report_score)
            provided.append(("report_score", report_score))
        except Exception:
            raise HTTPException(status_code=400, detail="report_score 必须是数字")
    if attendance_score is not None:
        try:
            attendance_score = float(attendance_score)
            provided.append(("attendance_score", attendance_score))
        except Exception:
            raise HTTPException(status_code=400, detail="attendance_score 必须是数字")
    if chat_score is not None:
        try:
            chat_score = float(chat_score)
            provided.append(("chat_score", chat_score))
        except Exception:
            raise HTTPException(status_code=400, detail="chat_score 必须是数字")

    if not provided:
        raise HTTPException(status_code=400, detail="至少提供一项待修改的分数: report_score / attendance_score / chat_score")

    agg = await update_aggregate_scores(
        db,
        aggregate_id=aggregate_id,
        report_score=report_score,
        attendance_score=attendance_score,
        chat_score=chat_score,
        modified_by=getattr(admin, "username", "admin"),
    )

    if not agg:
        raise HTTPException(status_code=404, detail="周评记录不存在")

    await write_operation_log(
        db, admin, "update", "weekly_aggregate", aggregate_id, request,
        {"changes": dict(provided)},
    )
    await db.commit()

    from app.services.aggregator import aggregate_to_dict
    return {"message": "更新成功", "aggregate": aggregate_to_dict(agg)}


@router.post("/{aggregate_id}/restore-ai")
async def restore_ai(
    aggregate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """对人工覆盖的周评记录恢复 AI 原始评分."""
    agg = await restore_ai_scores(db, aggregate_id)
    if not agg:
        raise HTTPException(status_code=404, detail="周评记录不存在")

    await write_operation_log(
        db, admin, "restore_ai", "weekly_aggregate", aggregate_id, request, {},
    )
    await db.commit()

    from app.services.aggregator import aggregate_to_dict
    return {"message": "已恢复 AI 评分", "aggregate": aggregate_to_dict(agg)}


# ===============================
# 删除/下载/批量删除/批量导出
# ===============================

@router.delete("/{aggregate_id}")
async def delete_aggregate(
    aggregate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """删除单条周评记录（同时清理关联的 AI 评分记录；周报文件默认保留）"""
    result = await db.execute(
        select(WeeklyAggregate).where(WeeklyAggregate.id == aggregate_id)
    )
    agg = result.scalar_one_or_none()
    if not agg:
        raise HTTPException(status_code=404, detail="周评记录不存在")

    # 清理关联的 WeeklyReport（通过 author_name + week_start 直接匹配，更可靠）
    await db.execute(WeeklyReport.__table__.delete().where(
        WeeklyReport.author_name == agg.author_name,
        WeeklyReport.week_start == agg.week_start
    ))
    
    # 清理关联的 ReportScore（若存在）
    if agg.report_score_id:
        await db.execute(ReportScore.__table__.delete().where(
            ReportScore.id == agg.report_score_id
        ))

    # 清理关联的 WeeklySummary（一周小结）
    await db.execute(WeeklySummary.__table__.delete().where(
        WeeklySummary.author_name == agg.author_name,
        WeeklySummary.week_start == agg.week_start
    ))

    await db.delete(agg)
    await write_operation_log(db, admin, "delete", "weekly_aggregate", aggregate_id, request,
                              {"author_name": agg.author_name, "week_start": str(agg.week_start)})
    await db.commit()
    return {"message": "删除成功"}


@router.post("/batch-delete")
async def batch_delete_aggregates(
    payload: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """批量删除周评记录；兼容 {ids:[...]} / {aggregate_ids:[...]} / 裸数组"""
    if isinstance(payload, list):
        ids = payload
    else:
        ids = payload.get("aggregate_ids") or payload.get("ids") or []
    if not isinstance(ids, list) or len(ids) == 0:
        raise HTTPException(status_code=400, detail="请选择要删除的周评记录")

    result = await db.execute(
        select(WeeklyAggregate).where(WeeklyAggregate.id.in_(ids))
    )
    aggs = result.scalars().all()
    if not aggs:
        raise HTTPException(status_code=404, detail="未找到所选周评记录")

    # 清理关联的 WeeklyReport（通过 author_name + week_start 直接匹配，更可靠）
    for a in aggs:
        await db.execute(WeeklyReport.__table__.delete().where(
            WeeklyReport.author_name == a.author_name,
            WeeklyReport.week_start == a.week_start
        ))
    
    # 清理关联的 ReportScore（若存在）
    related_ids = [a.report_score_id for a in aggs if a.report_score_id]
    if related_ids:
        await db.execute(ReportScore.__table__.delete().where(
            ReportScore.id.in_(related_ids)
        ))

    # 清理关联的 WeeklySummary（一周小结）
    for a in aggs:
        await db.execute(WeeklySummary.__table__.delete().where(
            WeeklySummary.author_name == a.author_name,
            WeeklySummary.week_start == a.week_start
        ))

    for a in aggs:
        await db.delete(a)

    await write_operation_log(db, admin, "batch_delete", "weekly_aggregate", "", request,
                              {"count": len(aggs), "ids": ids})
    await db.commit()
    return {"message": f"成功删除 {len(aggs)} 条记录", "deleted": len(aggs)}


@router.get("/{aggregate_id}/download-report")
async def download_report_by_aggregate(
    aggregate_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """通过周评记录下载对应的周报文件"""
    agg_result = await db.execute(
        select(WeeklyAggregate).where(WeeklyAggregate.id == aggregate_id)
    )
    agg = agg_result.scalar_one_or_none()
    if not agg:
        raise HTTPException(status_code=404, detail="周评记录不存在")

    # 由 author_name + week_start 反向定位周报
    report_result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.author_name == agg.author_name,
            WeeklyReport.week_start == agg.week_start,
        ).order_by(WeeklyReport.submit_time.asc()).limit(1)
    )
    report = report_result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="未找到关联的周报文件")

    if not is_safe_upload_path(report.file_path):
        raise HTTPException(status_code=404, detail="文件不存在，可能已被清理")

    await write_operation_log(db, admin, "download", "weekly_aggregate", aggregate_id, request,
                              {"original_filename": report.original_filename})
    await db.commit()

    filename = report.original_filename or f"{agg.author_name}-周报.xlsx"
    import urllib.parse
    filename = urllib.parse.quote(filename)
    return FileResponse(
        os.path.abspath(report.file_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )


@router.post("/export")
async def export_aggregates(
    payload: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """批量下载选中周评记录所关联的周报原始文件（打包为 ZIP）"""
    import zipfile
    from io import BytesIO
    import urllib.parse

    if isinstance(payload, list):
        aggregate_ids = payload
    else:
        aggregate_ids = payload.get("aggregate_ids") or payload.get("ids") or []

    if not isinstance(aggregate_ids, list) or len(aggregate_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择要导出的周评记录")

    agg_result = await db.execute(
        select(WeeklyAggregate).where(WeeklyAggregate.id.in_(aggregate_ids))
    )
    aggs = agg_result.scalars().all()

    if not aggs:
        raise HTTPException(status_code=404, detail="未找到所选周评记录")

    # 反向查找 WeeklyReport：author_name + week_start 匹配
    report_files = []
    for agg in aggs:
        r_result = await db.execute(
            select(WeeklyReport).where(
                WeeklyReport.author_name == agg.author_name,
                WeeklyReport.week_start == agg.week_start,
            ).order_by(WeeklyReport.submit_time.asc()).limit(1)
        )
        report = r_result.scalar_one_or_none()
        if report and report.file_path and is_safe_upload_path(report.file_path):
            report_files.append((agg, report))

    if not report_files:
        raise HTTPException(status_code=404, detail="所选记录均未关联周报文件")

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        added = set()
        for agg, report in report_files:
            # 生成带中文的安全文件名：姓名_起止日期_周报.xlsx
            base_name = f"{agg.author_name}_{agg.week_start}_{report.original_filename or '周报.xlsx'}"
            safe_name = base_name
            i = 1
            while safe_name in added:
                safe_name = f"{i}_{base_name}"
                i += 1
            added.add(safe_name)
            try:
                zf.write(os.path.abspath(report.file_path), arcname=safe_name)
            except Exception as e:
                logger.warning(f"[aggregate-export] 文件不存在或读取失败 {report.file_path}: {e}")

    zip_buffer.seek(0)

    await write_operation_log(
        db, admin, "export", "weekly_aggregate", "", request,
        {"count": len(report_files)},
    )
    await db.commit()

    fname = f"周报打包_{len(report_files)}份_{bj_today().isoformat()}.zip"
    fname_encoded = urllib.parse.quote(fname)
    return StreamingResponse(
        iter([zip_buffer.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{fname_encoded}",
        },
    )


# ===============================
# 定时评分配置
# ===============================

class ScheduleConfig(BaseModel):
    enabled: bool = True
    hour: int = 3  # 0-23
    minute: int = 0  # 0-59
    recurrence: str = "daily"  # 'daily' / 'weekly'
    weekdays: Optional[list] = None  # 0-6, 如 [0,2,4]


_WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _parse_weekdays(raw) -> list:
    """统一解析 weekdays 到 0-6 的列表，支持 None / int / '0,2,4' / '0，2，4' / [0,2,4] / (0,2,4)。
    遇到非法元素自动跳过（不再整体返回空），保证合法数字仍被解析。"""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        result = []
        for p in raw:
            try:
                v = int(str(p).strip())
                if 0 <= v <= 6 and v not in result:
                    result.append(v)
            except (TypeError, ValueError):
                continue
        return sorted(result)
    if isinstance(raw, (int, float)):
        try:
            v = int(raw)
            if 0 <= v <= 6:
                return [v]
        except (TypeError, ValueError):
            return []
    if isinstance(raw, str):
        # 支持英文逗号 / 中文逗号 / 空格
        normalized = raw.replace("，", ",").replace(" ", "").strip()
        if not normalized:
            return []
        # 纯数字字符串 "2"
        if normalized.isdigit():
            v = int(normalized)
            if 0 <= v <= 6:
                return [v]
            return []
        parts = [p.strip() for p in normalized.split(",") if p.strip()]
        result = []
        for p in parts:
            try:
                v = int(p)
                if 0 <= v <= 6 and v not in result:
                    result.append(v)
            except (TypeError, ValueError):
                continue
        return sorted(result)
    return []


def _weekdays_to_db(wd: list) -> str:
    return ",".join(str(x) for x in wd) if wd else ""


def _format_weekday_hint(wd: list) -> str:
    if not wd:
        return ""
    return "、".join(_WEEKDAY_LABELS[i] for i in wd)


@router.get("/schedule")
async def get_schedule(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """获取当前定时聚合评分配置"""
    from app.models.models import ScoringSchedule
    result = await db.execute(select(ScoringSchedule).limit(1))
    cfg = result.scalar_one_or_none()
    # 合并运行时配置（可能被其它入口更新）
    from app.core.task_queue import get_aggregate_schedule
    runtime_cfg = get_aggregate_schedule()
    if cfg:
        recurrence_db = getattr(cfg, "recurrence", None) or "daily"
        weekdays_db_raw = getattr(cfg, "weekdays", "") or ""
        weekdays_db = _parse_weekdays(weekdays_db_raw)
        recurrence = runtime_cfg.get("recurrence", recurrence_db)
        weekdays = runtime_cfg.get("weekdays", weekdays_db)
        return {
            "enabled": cfg.enabled,
            "hour": runtime_cfg.get("hour", cfg.hour),
            "minute": runtime_cfg.get("minute", cfg.minute),
            "recurrence": recurrence,
            "weekdays": list(weekdays) if weekdays else [0, 1, 2, 3, 4],
        }
    return {
        "enabled": runtime_cfg.get("enabled", False),
        "hour": runtime_cfg.get("hour", 3),
        "minute": runtime_cfg.get("minute", 0),
        "recurrence": runtime_cfg.get("recurrence", "daily"),
        "weekdays": runtime_cfg.get("weekdays", [0, 1, 2, 3, 4]),
    }


@router.post("/schedule")
async def update_schedule(
    payload: ScheduleConfig,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """更新定时聚合评分时间配置（支持每天/每周 + 星期选择）"""
    if not (0 <= payload.hour <= 23):
        raise HTTPException(status_code=400, detail="hour 必须为 0-23")
    if not (0 <= payload.minute <= 59):
        raise HTTPException(status_code=400, detail="minute 必须为 0-59")

    recurrence = payload.recurrence if payload.recurrence in ("daily", "weekly") else "daily"
    weekdays = _parse_weekdays(payload.weekdays)

    # weekly 模式下若未选中任何天 → 拒绝，避免永不触发的配置
    if recurrence == "weekly" and not weekdays:
        raise HTTPException(status_code=400, detail="每周模式下至少需选择一天")

    from app.models.models import ScoringSchedule
    result = await db.execute(select(ScoringSchedule).limit(1))
    cfg = result.scalar_one_or_none()
    db_weekdays = _weekdays_to_db(weekdays)
    if cfg:
        cfg.enabled = payload.enabled
        cfg.hour = payload.hour
        cfg.minute = payload.minute
        cfg.recurrence = recurrence
        cfg.weekdays = db_weekdays
        cfg.updated_at = bj_now()
    else:
        cfg = ScoringSchedule(
            id=str(uuid.uuid4()),
            enabled=payload.enabled,
            hour=payload.hour,
            minute=payload.minute,
            recurrence=recurrence,
            weekdays=db_weekdays,
        )
        db.add(cfg)
    await db.commit()

    # 更新运行时调度线程
    from app.core.task_queue import update_aggregate_schedule
    update_aggregate_schedule(
        enabled=payload.enabled,
        hour=payload.hour,
        minute=payload.minute,
        recurrence=recurrence,
        weekdays=weekdays,
    )

    await write_operation_log(
        db, admin, "update_schedule", "weekly_aggregate", "", request,
        {
            "enabled": payload.enabled,
            "hour": payload.hour,
            "minute": payload.minute,
            "recurrence": recurrence,
            "weekdays": weekdays,
        },
    )
    await db.commit()

    if recurrence == "daily":
        pattern_msg = f"每日 {payload.hour:02d}:{payload.minute:02d}"
    else:
        pattern_msg = f"每周 {_format_weekday_hint(weekdays)} {payload.hour:02d}:{payload.minute:02d}"
    return {
        "message": f"定时评分已更新：{'启用' if payload.enabled else '禁用'}，{pattern_msg} 自动聚合评分",
        "enabled": payload.enabled,
        "hour": payload.hour,
        "minute": payload.minute,
        "recurrence": recurrence,
        "weekdays": weekdays,
    }


@router.get("/status", summary="获取聚合评分进度")
async def get_aggregate_scoring_status():
    """返回当前聚合评分的执行进度。

    包含：
    - running: 是否正在执行
    - total / processed / errors: 总人数 / 已完成 / 失败数
    - current_person: 正在处理的员工姓名
    - last_run_at / last_result / last_message: 最近一次执行的结果
    - scheduler_alive: 调度线程是否存活
    """
    from app.core.task_queue import get_aggregate_status, _scheduler_thread
    result = get_aggregate_status()
    result["scheduler_alive"] = bool(_scheduler_thread and _scheduler_thread.is_alive())
    if _scheduler_thread:
        result["scheduler_config"] = _scheduler_thread.get_config()
    return result


@router.post("/status/trigger", summary="手动触发聚合评分")
async def trigger_aggregate_now(
    request: Request,
    admin=Depends(require_admin),
):
    """立即触发一次聚合评分（不等待定时任务）。

    1. 如果当前正在评分 → 返回 409
    2. 否则在后台线程中启动评分并返回当前状态
    """
    from app.core.task_queue import get_aggregate_status, _scheduler_thread
    status = get_aggregate_status()
    if status.get("running"):
        raise HTTPException(status_code=409, detail="聚合评分正在执行中，请稍后再试")

    def _run():
        if _scheduler_thread:
            _scheduler_thread._execute_aggregate()

    import threading
    t = threading.Thread(target=_run, daemon=True, name="ManualAggregateTrigger")
    t.start()
    return {"message": "聚合评分已触发", "status": get_aggregate_status()}


@router.post("/recalculate", summary="重新计算指定周的聚合评分")
async def recalculate_week(
    payload: Dict[str, Any],
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """对指定周的所有员工强制重新计算聚合评分（force=True）。

    适用场景：管理员上传了错误的考勤/聊天数据后更正重传，需要对该周数据重新评分。
    请求体: {"week_start": "2026-07-20"}
    """
    week_start_str = payload.get("week_start")
    if not week_start_str:
        raise HTTPException(status_code=400, detail="请提供 week_start 参数（格式: YYYY-MM-DD）")

    try:
        week_start = date.fromisoformat(week_start_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="week_start 格式错误，应为 YYYY-MM-DD")

    week_end = week_start + timedelta(days=6)

    # 获取所有启用员工
    result = await db.execute(select(Person).where(Person.is_active == True))
    persons = list(result.scalars().all())
    if not persons:
        raise HTTPException(status_code=400, detail="无启用员工")

    from app.services.aggregator import auto_aggregate

    success_count = 0
    error_count = 0
    for p in persons:
        try:
            await auto_aggregate(
                db,
                person_id=p.id,
                author_name=p.name,
                department=p.department_name or "",
                department_id=p.department_id,
                week_start=week_start,
                week_end=week_end,
                preserve_manual=False,
                force=True,
            )
            success_count += 1
        except Exception as e:
            logger.warning(f"[重新计算] 处理 {p.name} 失败: {e}")
            error_count += 1

    await write_operation_log(
        db, admin, "recalculate", "weekly_aggregate", "", request,
        {"week_start": week_start_str, "week_end": week_end.isoformat(),
         "success": success_count, "errors": error_count},
    )
    await db.commit()

    return {
        "message": f"重新计算完成：成功 {success_count} 人，失败 {error_count} 人",
        "week_start": week_start_str,
        "week_end": week_end.isoformat(),
        "success_count": success_count,
        "error_count": error_count,
    }
