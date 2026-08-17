"""异步任务调度器 - 用 FastAPI 事件循环 + 轻量 threading 实现

设计原则：
1. 立即任务（周报评分/OCR）→ asyncio.create_task 在事件循环中异步执行
2. 定时任务（每日聚合评分）→ 独立后台线程，按配置时间触发
3. 简单、可靠、不引入复杂 broker/事件循环嵌套
"""
import asyncio
import os
import threading
import time
import uuid
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any

from app.utils.logger import log_info, log_error, log_warning
from app.utils.time_utils import bj_now, bj_today

# 一周小结图片存储目录（与 upload_unified.py / weeklysummary.py 保持一致）
_SUMMARY_UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "weeklysummary")
)

# --- 任务状态内存记录（小量够用，重启不丢失评分结果本身在 DB）---
_running_tasks: Dict[str, Dict[str, Any]] = {}  # task_id -> {type, ref, status, started_at}
_scheduler_thread: Optional["AggregateSchedulerThread"] = None
_pending_retry_thread: Optional["PendingRetryThread"] = None  # P0-2: pending 自动重试线程
_pending_schedule_cfg: Optional[Dict[str, Any]] = None  # 调度线程未启动时保存配置
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None  # 主事件循环引用（避免线程用 asyncpg 冲突）

# 聚合评分进度追踪（供前端轮询）
_aggregate_status: Dict[str, Any] = {
    "running": False,
    "started_at": None,
    "total": 0,
    "processed": 0,
    "errors": 0,
    "current_person": "",
    "last_run_at": None,
    "last_result": None,
    "last_message": "",
}


# ============================================================
# 立即任务 API
# ============================================================

def submit_report_scoring(report_id: str) -> str:
    """提交"周报 AI 评分"到后台异步执行，不阻塞当前请求"""
    task_id = f"score_report_{report_id}_{uuid.uuid4().hex[:8]}"

    async def _do():
        report_info = None  # (person_id, author_name, department, department_id, week_start, week_end)
        try:
            _running_tasks[task_id] = {"type": "report_scoring", "report_id": report_id,
                                        "status": "running", "started_at": bj_now().isoformat()}
            from app.services.scoring import trigger_scoring
            from app.database import async_session
            from app.models.models import WeeklyReport
            from sqlalchemy import select
            async with async_session() as db:
                # 先读一次报告信息，失败分支也要用
                rep_result = await db.execute(select(WeeklyReport).where(WeeklyReport.id == report_id))
                report = rep_result.scalar_one_or_none()
                if report:
                    report_info = (report.person_id, report.author_name, report.department or "",
                                   report.department_id, report.week_start, report.week_end)

                result = await trigger_scoring(report_id, db)
                log_info(f"[task] 周报评分完成 report_id={report_id}, total={result.get('total_score')}")

                # ===== P0 修复 1：评分成功后在同一 session 内推进聚合状态 =====
                # 旧实现：评分 commit 后关闭 session，再开新 session 调 auto_aggregate，
                #         跨 session 可能读不到刚写入的 ReportScore → 误判"未评分" →
                #         二次触发 AI 评分 → 失败后 status 卡 pending（前端显示"评分超时"）。
                # 新实现：同 session 聚合（必然能读到刚 commit 的 ReportScore），
                #         再用兜底函数强制把滞留 pending 推进为 done。
                if report_info:
                    pid, name, dept, dept_id, ws, we = report_info
                    try:
                        from app.services.aggregator import auto_aggregate
                        await auto_aggregate(
                            db,
                            person_id=pid,
                            author_name=name,
                            department=dept,
                            department_id=dept_id,
                            week_start=ws,
                            week_end=we,
                            preserve_manual=True,
                            force=False,
                        )
                        log_info(f"[task] 聚合更新完成（同 session）author_name={name}")
                    except Exception as agg_e:
                        await db.rollback()
                        log_warning(f"[task] 聚合更新失败 report_id={report_id}: {agg_e}")

                    # 兜底：若聚合后仍卡 pending 但评分已写入 → 直接同步分数并置 done
                    try:
                        await _force_done_if_scored(db, report_id, report_info)
                    except Exception as fin_e:
                        await db.rollback()
                        log_warning(f"[task] 兜底状态推进失败 report_id={report_id}: {fin_e}")

            _running_tasks[task_id]["status"] = "done"
        except Exception as e:
            err_msg = str(e)[:500]
            log_error(f"[task] 周报评分失败 report_id={report_id}: {err_msg}")
            _running_tasks[task_id]["status"] = f"failed: {err_msg[:100]}"

            # ===== 关键修复：评分失败后仍必须创建/更新聚合，持久化错误消息（防止永远卡 pending）=====
            # 1. 先用 report_id 再尝试读一次 report_info
            if report_info is None:
                try:
                    from app.database import async_session as _s
                    from app.models.models import WeeklyReport as _WR
                    from sqlalchemy import select as _sel
                    async with _s() as _db:
                        _rr = await _db.execute(_sel(_WR).where(_WR.id == report_id))
                        _rpt = _rr.scalar_one_or_none()
                        if _rpt:
                            report_info = (_rpt.person_id, _rpt.author_name, _rpt.department or "",
                                           _rpt.department_id, _rpt.week_start, _rpt.week_end)
                except Exception as inner_e:
                    log_warning(f"[task] 失败后二次读取周报信息也失败 report_id={report_id}: {inner_e}")

            if report_info is not None:
                try:
                    from app.services.aggregator import auto_aggregate, WeeklyAggregate as _WAgg
                    from app.database import async_session as _s2
                    from sqlalchemy import select as _sel2
                    from app.utils.time_utils import bj_now as _bjnow
                    from datetime import datetime as _dt

                    pid, name, dept, dept_id, ws, we = report_info

                    # 2. 先执行一次聚合 → 创建出 pending 状态记录（若不存在）
                    #    即使 pending 聚合内触发了评分并失败，也会把错误信息写进去
                    async with _s2() as _db:
                        try:
                            await auto_aggregate(
                                _db,
                                person_id=pid, author_name=name, department=dept,
                                department_id=dept_id, week_start=ws, week_end=we,
                                preserve_manual=True, force=False,
                            )
                            await _db.commit()
                            log_info(f"[task] 评分失败后已触发聚合 author_name={name}（将走重试/转失败逻辑）")
                        except Exception:
                            await _db.rollback()
                            # 3. 兜底：如果 auto_aggregate 自身也失败，直接写 DB 记录错误
                            rs = await _db.execute(
                                _sel2(_WAgg).where(
                                    _WAgg.author_name == name,
                                    _WAgg.week_start == ws,
                                ).limit(1)
                            )
                            agg = rs.scalar_one_or_none()
                            if agg is None:
                                agg = _WAgg(
                                    person_id=pid,
                                    author_name=name,
                                    department=dept or "",
                                    department_id=dept_id,
                                    week_start=ws,
                                    week_end=we,
                                    report_score=None,
                                    attendance_score=None,
                                    chat_score=None,
                                    composite_score=None,
                                    status="failed",
                                    error_message=err_msg,
                                    retry_count=1,
                                    manual_override={},
                                )
                                _db.add(agg)
                            else:
                                agg.error_message = err_msg
                                agg.retry_count = int(getattr(agg, "retry_count", 0) or 0) + 1
                                if agg.retry_count >= 3:
                                    agg.status = "failed"
                                else:
                                    agg.status = "pending"
                            agg.updated_at = _bjnow()
                            await _db.commit()
                            log_warning(
                                f"[task] 评分失败+聚合也失败，已直接写入 WeeklyAggregate "
                                f"status={agg.status}, retry_count={agg.retry_count} author_name={name}"
                            )
                except Exception as outer_e:
                    log_error(
                        f"[task] 评分失败后持久化错误到聚合表再次失败 report_id={report_id}: {outer_e}"
                    )
            else:
                log_error(
                    f"[task] 无法获取周报信息 report_id={report_id}，"
                    f"错误信息无法持久化到聚合表（下次聚合需自行检查）"
                )

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # FastAPI 请求上下文中，事件循环正在跑 → create_task
            loop.create_task(_do())
        else:
            # 离线场景（极少发生）→ 同步跑
            loop.run_until_complete(_do())
    except RuntimeError:
        # 无事件循环 → 新建一个
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(_do())

    log_info(f"[task] 已提交周报评分任务: {task_id}")
    return task_id


async def _force_done_if_scored(db, report_id: str, report_info):
    """P0 修复 1 兜底：评分已写入但聚合仍卡 pending 时，直接同步周报分并置 done。

    保证"评分成功"与"状态完成"强一致，不依赖二次聚合是否正确推进状态。
    必须在 trigger_scoring 同一 session 内调用（评分已 commit，此处必能读到）。
    """
    from app.models.models import WeeklyAggregate, ReportScore
    from sqlalchemy import select
    from decimal import Decimal

    pid, name, dept, dept_id, ws, we = report_info
    agg_r = await db.execute(
        select(WeeklyAggregate).where(
            WeeklyAggregate.author_name == name,
            WeeklyAggregate.week_start == ws,
        ).limit(1)
    )
    agg = agg_r.scalar_one_or_none()
    if agg is None or agg.status != "pending":
        return  # 聚合已正常推进（done/manual/failed），无需兜底

    score_r = await db.execute(
        select(ReportScore).where(ReportScore.report_id == report_id).limit(1)
    )
    score = score_r.scalar_one_or_none()
    if score is None or score.total_score is None:
        return  # 评分确实未写入，交给 P0-2 重试线程处理

    agg.report_score = Decimal(str(round(float(score.total_score), 1)))
    agg.report_score_id = score.id
    total = (
        float(agg.report_score or 0)
        + float(agg.attendance_score or 0)
        + float(agg.chat_score or 0)
    )
    agg.composite_score = Decimal(str(round(total, 2)))
    agg.status = "done"
    agg.error_message = ""
    agg.updated_at = bj_now()
    await db.commit()
    log_info(f"[task] 兜底推进：{name} {ws} pending→done（report_score={agg.report_score}）")


def submit_summary_ocr(summary_id: str) -> str:
    """提交"一周小结 OCR"到后台异步执行"""
    task_id = f"ocr_summary_{summary_id}_{uuid.uuid4().hex[:8]}"

    async def _do():
        try:
            _running_tasks[task_id] = {"type": "ocr", "summary_id": summary_id,
                                        "status": "running", "started_at": bj_now().isoformat()}
            from app.services.ocr_service import parse_summary_image
            from app.database import async_session
            from app.models.models import WeeklySummary
            from sqlalchemy import select
            import os

            async with async_session() as db:
                result = await db.execute(select(WeeklySummary).where(WeeklySummary.id == summary_id))
                summary = result.scalar_one_or_none()
                if not summary:
                    log_warning(f"[task] OCR 任务找不到小结: {summary_id}")
                    _running_tasks[task_id]["status"] = "not_found"
                    return
                if summary.work_session_count is not None:
                    log_info(f"[task] 小结已 OCR 过，跳过: {summary_id}")
                    _running_tasks[task_id]["status"] = "already_done"
                    return

                source_file = summary.source_file
                if not source_file:
                    log_warning(f"[task] 小结 source_file 为空: {summary_id}")
                    _running_tasks[task_id]["status"] = "file_missing"
                    return

                # 构造完整路径（source_file 仅存文件名，需拼接上传目录）
                full_path = source_file if os.path.isabs(source_file) else os.path.join(_SUMMARY_UPLOAD_DIR, source_file)
                if not os.path.exists(full_path):
                    log_warning(f"[task] 小结图片不存在: {full_path}")
                    _running_tasks[task_id]["status"] = "file_missing"
                    return

                with open(full_path, "rb") as f:
                    image_bytes = f.read()

                ocr_result = await parse_summary_image(image_bytes, full_path,
                                                        override_author_name=summary.author_name,
                                                        db=db)
                summary.work_session_count = ocr_result.get("work_session_count")
                summary.total_minutes = ocr_result.get("total_minutes")
                summary.latest_time = ocr_result.get("latest_time")
                summary.raw_ocr_text = ocr_result.get("raw_ocr_text", "")
                await db.commit()
                log_info(f"[task] 一周小结 OCR 完成: session={summary.work_session_count}")

                # OCR 完成后触发聚合评分，更新沟通分
                try:
                    from app.services.aggregator import auto_aggregate
                    await auto_aggregate(
                        db,
                        person_id=summary.person_id,
                        author_name=summary.author_name,
                        department=summary.department or "",
                        department_id=summary.department_id,
                        week_start=summary.week_start,
                        week_end=summary.week_end,
                        preserve_manual=True,
                        force=False,
                    )
                    log_info(f"[task] 聚合更新完成 author_name={summary.author_name}")
                except Exception as e:
                    log_warning(f"[task] OCR 后聚合更新失败: {e}")

                _running_tasks[task_id]["status"] = "done"
        except Exception as e:
            log_error(f"[task] OCR 失败 summary_id={summary_id}: {e}")
            _running_tasks[task_id]["status"] = f"failed: {str(e)[:100]}"

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_do())
        else:
            loop.run_until_complete(_do())
    except RuntimeError:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(_do())

    log_info(f"[task] 已提交一周小结 OCR 任务: {task_id}")
    return task_id


# ============================================================
# 定时任务线程（每天到点执行一次聚合评分）
# ============================================================

class AggregateSchedulerThread(threading.Thread):
    """后台线程：在配置的时间点触发聚合评分（支持每天/每周模式）。

    _last_run_date 会持久化到 DB scoring_schedule.last_run_date，
    确保后端重启/重载后不会在同一天重复触发。
    """

    WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    def __init__(self):
        super().__init__(daemon=True, name="AggregateScheduler")
        self._stop_event = threading.Event()
        # 默认时间：每天 03:00
        self._enabled = True
        self._hour = 3
        self._minute = 0
        self._recurrence = "daily"  # 'daily' / 'weekly'
        self._weekdays = [0, 1, 2, 3, 4]  # 默认周一到周五（仅 weekly 生效）
        self._last_run_date: Optional[date] = None  # 防止同一天内多次跑

    def _save_last_run_date_to_db(self, run_date: Optional[date]):
        """将 _last_run_date 持久化到 DB scoring_schedule 表"""
        try:
            global _main_event_loop
            async def _save():
                from app.database import async_session
                from app.models.models import ScoringSchedule
                from sqlalchemy import select
                async with async_session() as db:
                    result = await db.execute(select(ScoringSchedule).limit(1))
                    cfg = result.scalar_one_or_none()
                    if cfg:
                        cfg.last_run_date = run_date
                        await db.commit()
            if _main_event_loop and _main_event_loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_save(), _main_event_loop)
                future.result(timeout=30)
        except Exception as e:
            log_warning(f"[scheduler] 持久化 last_run_date 失败: {e}")

    def configure(self, enabled: bool, hour: int, minute: int,
                  recurrence: str = "daily", weekdays=None):
        old_enabled = self._enabled
        old_hour, old_minute = self._hour, self._minute
        old_recurrence = self._recurrence
        old_weekdays = list(self._weekdays)
        self._enabled = enabled
        self._hour = hour
        self._minute = minute
        self._recurrence = recurrence if recurrence in ("daily", "weekly") else "daily"
        if isinstance(weekdays, (list, tuple)):
            cleaned = []
            for w in weekdays:
                try:
                    v = int(w)
                    if 0 <= v <= 6 and v not in cleaned:
                        cleaned.append(v)
                except (TypeError, ValueError):
                    pass
            self._weekdays = sorted(cleaned)
        elif isinstance(weekdays, str):
            parsed = self._parse_weekdays_str(weekdays)
            if parsed is not None:
                self._weekdays = parsed
        # weekly 模式下若没选中任何天 → 回退到 daily，避免永不触发
        if self._recurrence == "weekly" and not self._weekdays:
            self._recurrence = "daily"
        # 任意配置发生变化 → 重置 _last_run_date 并持久化，确保新配置能按时触发
        config_changed = (
            old_enabled != enabled
            or old_hour != hour
            or old_minute != minute
            or old_recurrence != self._recurrence
            or sorted(old_weekdays) != sorted(self._weekdays)
        )
        if config_changed and self._last_run_date is not None:
            log_info(
                f"[scheduler] 配置变更 (time={old_hour:02d}:{old_minute:02d}→{hour:02d}:{minute:02d}, "
                f"recurrence={old_recurrence}→{self._recurrence}, weekdays={old_weekdays}→{self._weekdays})，重置运行标记"
            )
            self._last_run_date = None
            self._save_last_run_date_to_db(None)
        weekday_hint = ""
        if self._recurrence == "weekly":
            weekday_hint = "（" + "、".join(self.WEEKDAY_LABELS[i] for i in self._weekdays) + "）"
        log_info(
            f"[scheduler] 定时聚合评分已配置: enabled={enabled}, "
            f"recurrence={self._recurrence}{weekday_hint}, time={hour:02d}:{minute:02d}"
        )

    @staticmethod
    def _parse_weekdays_str(s: str):
        """解析 '0,2,4' 形式的字符串为有序列表，非法值返回 None"""
        if s is None:
            return None
        parts = [p.strip() for p in str(s).split(",") if p.strip()]
        result = []
        for p in parts:
            try:
                v = int(p)
                if 0 <= v <= 6 and v not in result:
                    result.append(v)
            except (TypeError, ValueError):
                return None
        return sorted(result)

    def get_config(self) -> Dict[str, Any]:
        return {
            "enabled": self._enabled,
            "hour": self._hour,
            "minute": self._minute,
            "recurrence": self._recurrence,
            "weekdays": list(self._weekdays),
        }

    def stop(self):
        self._stop_event.set()

    def _should_run_now(self) -> bool:
        if not self._enabled:
            return False
        now = bj_now()
        today = now.date()
        # 今天已跑过 → 不再跑
        if self._last_run_date == today:
            return False
        # 当前时间 >= 配置时间 → 才可能触发
        if not (now.hour > self._hour or (now.hour == self._hour and now.minute >= self._minute)):
            return False
        # 重复模式判断
        if self._recurrence == "weekly":
            # Python datetime.weekday(): 周一=0, 周日=6，与我们存储一致
            if now.weekday() not in self._weekdays:
                return False
        # daily 模式：每天都触发
        return True

    def run(self):
        log_info(f"[scheduler] 定时聚合评分线程已启动")
        while not self._stop_event.is_set():
            try:
                if self._should_run_now():
                    log_info(f"[scheduler] ===== 触发定时聚合评分 {bj_now().strftime('%Y-%m-%d %H:%M:%S')} =====")
                    run_date = bj_now().date()
                    self._last_run_date = run_date
                    self._save_last_run_date_to_db(run_date)
                    # 在新线程中跑 async 逻辑，避免阻塞调度线程
                    t = threading.Thread(target=self._execute_aggregate, daemon=True, name="AggregateWorker")
                    t.start()
                    t.join(timeout=3600)  # 1 小时超时
            except Exception as e:
                log_error(f"[scheduler] 调度线程异常: {e}")
            # 每 30 秒检查一次是否到点了
            self._stop_event.wait(30)
        log_info("[scheduler] 定时聚合评分线程已退出")

    @staticmethod
    def _execute_aggregate():
        """执行聚合评分（在主事件循环上运行）"""
        try:
            global _main_event_loop
            if _main_event_loop and _main_event_loop.is_running():
                future = asyncio.run_coroutine_threadsafe(
                    _aggregate_worker_coro(), _main_event_loop
                )
                future.result(timeout=3600)
        except Exception as e:
            log_error(f"[scheduler] _execute_aggregate 异常: {e}")


def get_aggregate_status() -> Dict[str, Any]:
    """返回当前聚合评分进度（供 API 查询）"""
    return dict(_aggregate_status)


async def _aggregate_worker_coro():
    """聚合评分工作协程 — 每员工独立提交，一人失败不影响其他人"""
    global _aggregate_status
    from app.database import async_session
    from app.services.aggregator import auto_aggregate
    from app.models.models import Person
    from app.services.aggregator import _get_week_range_for_date
    from sqlalchemy import select
    from datetime import date

    _aggregate_status["running"] = True
    _aggregate_status["started_at"] = bj_now().isoformat()
    _aggregate_status["errors"] = 0
    _aggregate_status["processed"] = 0
    _aggregate_status["last_result"] = None
    _aggregate_status["last_message"] = ""
    week_start, week_end = _get_week_range_for_date(bj_today())

    try:
        async with async_session() as db:
            result = await db.execute(select(Person).where(Person.is_active == True))
            persons = list(result.scalars().all())
            _aggregate_status["total"] = len(persons)
            _aggregate_status["current_person"] = ""

            if not persons:
                _aggregate_status["last_message"] = "无活跃员工"
                _aggregate_status["running"] = False
                _aggregate_status["last_run_at"] = bj_now().isoformat()
                _aggregate_status["last_result"] = "ok"
                log_info("[scheduler] 无启用员工，跳过")
                return

            for p in persons:
                _aggregate_status["current_person"] = p.name
                try:
                    await auto_aggregate(
                        db,
                        person_id=p.id,
                        author_name=p.name,
                        department=p.department_name or "",
                        department_id=p.department_id,
                        week_start=week_start,
                        week_end=week_end,
                        preserve_manual=True,
                        force=False,
                    )
                    await db.commit()  # 每人独立提交
                    _aggregate_status["processed"] += 1
                except Exception as e:
                    await db.rollback()  # 只回滚当前人的操作
                    _aggregate_status["errors"] += 1
                    log_warning(f"[scheduler] 处理 {p.name} 失败(已跳过): {e}")
                    continue

        _aggregate_status["last_result"] = "ok"
        _aggregate_status["last_message"] = (
            f"完成 {_aggregate_status['processed']}/{_aggregate_status['total']} 人"
            + (f"，{_aggregate_status['errors']} 人失败" if _aggregate_status["errors"] else "")
        )
        log_info(f"[scheduler] 定时聚合评分: {_aggregate_status['last_message']}")
    except Exception as e:
        _aggregate_status["last_result"] = "error"
        _aggregate_status["last_message"] = str(e)[:200]
        log_error(f"[scheduler] 定时聚合评分失败: {e}")
    finally:
        _aggregate_status["running"] = False
        _aggregate_status["current_person"] = ""
        _aggregate_status["last_run_at"] = bj_now().isoformat()


class PendingRetryThread(threading.Thread):
    """P0 修复 2：后台重试线程 — 周期扫描滞留 pending 的聚合记录并自动重评。

    解决问题：评分失败后 retry_count<3 时状态保持 pending，但系统此前无自动重试入口，
    只能等次日定时聚合（默认 24h）或管理员手动重试 → 前端长时间显示"评分超时"。

    策略：每 5 分钟扫描一次 status=pending 且 updated_at 超过 5 分钟未变化的记录，
    逐条调用 auto_aggregate：
    - 若 ReportScore 已存在（历史卡住记录）→ 直接同步分数并置 done（不调 AI，秒级）
    - 若确实未评分 → 内部自动重试 AI 评分；连续失败达上限后转 failed，不再被扫描
    """

    SCAN_INTERVAL = 300   # 扫描间隔（秒）
    STALE_MINUTES = 5     # pending 超过 N 分钟未变化才重试（避开正在评分中的记录）
    BATCH_LIMIT = 10      # 每轮最多处理条数（防止单轮耗时过长）

    def __init__(self):
        super().__init__(daemon=True, name="PendingRetry")
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        log_info(f"[pending-retry] pending 自动重试线程已启动（每 {self.SCAN_INTERVAL}s 扫描一次）")
        while not self._stop_event.is_set():
            try:
                self._check_once()
            except Exception as e:
                log_error(f"[pending-retry] 重试线程异常: {e}")
            self._stop_event.wait(self.SCAN_INTERVAL)
        log_info("[pending-retry] pending 自动重试线程已退出")

    def _check_once(self):
        global _main_event_loop
        if not (_main_event_loop and _main_event_loop.is_running()):
            return
        future = asyncio.run_coroutine_threadsafe(_retry_pending_coro(), _main_event_loop)
        future.result(timeout=600)  # 单轮最多等 10 分钟，超时后协程继续在主循环中执行


async def _retry_pending_coro():
    """扫描滞留 pending 的聚合记录并自动重试（auto_aggregate 内部自带失败计数与转 failed 逻辑）"""
    from app.database import async_session
    from app.services.aggregator import auto_aggregate
    from app.models.models import WeeklyAggregate
    from sqlalchemy import select

    cutoff = bj_now() - timedelta(minutes=PendingRetryThread.STALE_MINUTES)
    async with async_session() as db:
        result = await db.execute(
            select(WeeklyAggregate)
            .where(
                WeeklyAggregate.status == "pending",
                WeeklyAggregate.updated_at < cutoff,
            )
            .order_by(WeeklyAggregate.updated_at.asc())
            .limit(PendingRetryThread.BATCH_LIMIT)
        )
        pendings = list(result.scalars().all())
        if not pendings:
            return

        log_info(f"[pending-retry] 发现 {len(pendings)} 条滞留 pending 记录，开始自动重试")
        for agg in pendings:
            try:
                await auto_aggregate(
                    db,
                    person_id=agg.person_id,
                    author_name=agg.author_name,
                    department=agg.department or "",
                    department_id=agg.department_id,
                    week_start=agg.week_start,
                    week_end=agg.week_end,
                    preserve_manual=True,
                    force=False,
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                log_error(
                    f"[pending-retry] 重试失败 author_name={agg.author_name} "
                    f"week={agg.week_start}: {e}"
                )
        log_info(f"[pending-retry] 本轮重试完成，共处理 {len(pendings)} 条")


# ============================================================
# 启动/关闭
# ============================================================

async def init_scheduler():
    """在 FastAPI lifespan 中调用 - 启动调度线程"""
    global _scheduler_thread, _pending_schedule_cfg, _main_event_loop, _pending_retry_thread
    _main_event_loop = asyncio.get_running_loop()
    if _scheduler_thread is None or not _scheduler_thread.is_alive():
        _scheduler_thread = AggregateSchedulerThread()

        # 1) 优先读取用户刚设置但线程未启动时写入的内存配置
        if _pending_schedule_cfg:
            cfg = _pending_schedule_cfg
            _scheduler_thread.configure(
                enabled=cfg.get("enabled", True),
                hour=int(cfg.get("hour", 3)),
                minute=int(cfg.get("minute", 0)),
                recurrence=cfg.get("recurrence", "daily"),
                weekdays=cfg.get("weekdays") or [],
            )
            _pending_schedule_cfg = None
            log_info(f"[scheduler] 已加载内存中的定时配置: {cfg}")
        else:
            # 2) 从 DB 加载配置
            try:
                from app.database import async_session
                from app.models.models import ScoringSchedule
                from sqlalchemy import select
                async with async_session() as db:
                    result = await db.execute(select(ScoringSchedule).limit(1))
                    cfg = result.scalar_one_or_none()
                    if cfg:
                        recurrence = getattr(cfg, "recurrence", "daily") or "daily"
                        weekdays_raw = getattr(cfg, "weekdays", "") or ""
                        weekdays = AggregateSchedulerThread._parse_weekdays_str(weekdays_raw)
                        if weekdays is None:
                            weekdays = []
                        # weekly 但 weekdays 为空 → 回退为 daily，避免永不触发
                        if recurrence == "weekly" and not weekdays:
                            recurrence = "daily"
                        _scheduler_thread.configure(
                            enabled=cfg.enabled,
                            hour=cfg.hour,
                            minute=cfg.minute,
                            recurrence=recurrence,
                            weekdays=weekdays,
                        )
                        # 从 DB 恢复上次执行日期（跨重启/重载保持"今日已执行"状态）
                        db_last_run = getattr(cfg, "last_run_date", None)
                        if db_last_run:
                            _scheduler_thread._last_run_date = db_last_run
                            log_info(
                                f"[scheduler] 已加载 DB 定时配置: "
                                f"enabled={cfg.enabled}, recurrence={recurrence}, "
                                f"weekdays={weekdays}, time={cfg.hour:02d}:{cfg.minute:02d}, "
                                f"last_run_date={db_last_run}"
                            )
                        else:
                            log_info(
                                f"[scheduler] 已加载 DB 定时配置: "
                                f"enabled={cfg.enabled}, recurrence={recurrence}, "
                                f"weekdays={weekdays}, time={cfg.hour:02d}:{cfg.minute:02d}"
                            )
                    else:
                        log_info("[scheduler] DB 中无定时配置，使用默认值: enabled=True, daily, 03:00")
            except Exception as e:
                log_warning(f"[scheduler] 从 DB 加载定时配置失败，使用默认值: {e}")

        _scheduler_thread.start()
        log_info("[scheduler] 调度系统已就绪，将在下一个配置时间点自动触发聚合评分")

    # P0 修复 2：启动 pending 自动重试线程（每 5 分钟扫描滞留 pending 记录并重试）
    if _pending_retry_thread is None or not _pending_retry_thread.is_alive():
        _pending_retry_thread = PendingRetryThread()
        _pending_retry_thread.start()


async def shutdown_scheduler():
    """在 FastAPI lifespan shutdown 中调用"""
    global _scheduler_thread, _pending_retry_thread
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.stop()
        _scheduler_thread.join(timeout=5)
    if _pending_retry_thread and _pending_retry_thread.is_alive():
        _pending_retry_thread.stop()
        _pending_retry_thread.join(timeout=5)
    log_info("[scheduler] 调度系统已关闭")


def update_aggregate_schedule(enabled: bool, hour: int, minute: int,
                              recurrence: str = "daily", weekdays=None):
    """更新定时配置。weekdays 支持 None / list / tuple / '0,2,4' / 单数字。

    关键保障：
    1) 若调度线程不存在（如刚重启，主线程还没触发过 lifespan），也要把
       配置写入内存，否则下一次自动聚合时仍使用默认值；
    2) 不允许 recurrence='weekly' 但 weekdays 为空（自动回退为 daily）。"""
    # 统一解析 weekdays
    wd = []
    if weekdays is None:
        wd = []
    elif isinstance(weekdays, (list, tuple, set)):
        cleaned = set()
        for w in weekdays:
            try:
                v = int(str(w).strip())
                if 0 <= v <= 6:
                    cleaned.add(v)
            except (TypeError, ValueError):
                continue
        wd = sorted(cleaned)
    elif isinstance(weekdays, (int, float)):
        try:
            v = int(weekdays)
            if 0 <= v <= 6:
                wd = [v]
        except (TypeError, ValueError):
            wd = []
    elif isinstance(weekdays, str):
        normalized = weekdays.replace("，", ",").replace(" ", "").strip()
        if normalized and normalized.isdigit():
            v = int(normalized)
            if 0 <= v <= 6:
                wd = [v]
        elif normalized:
            parts = [p.strip() for p in normalized.split(",") if p.strip()]
            cleaned = set()
            for p in parts:
                try:
                    v = int(p)
                    if 0 <= v <= 6:
                        cleaned.add(v)
                except (TypeError, ValueError):
                    continue
            wd = sorted(cleaned)

    # weekly + 空 weekdays → 自动回退到 daily，避免永不触发
    if recurrence == "weekly" and not wd:
        recurrence = "daily"

    applied_cfg = None
    if _scheduler_thread is not None:
        _scheduler_thread.configure(enabled=enabled, hour=hour, minute=minute,
                                    recurrence=recurrence, weekdays=wd)
        applied_cfg = _scheduler_thread.get_config()
        log_info(
            f"[scheduler] 调度线程已更新: enabled={enabled}, "
            f"recurrence={recurrence}, weekdays={wd}, time={hour:02d}:{minute:02d}"
        )
    else:
        # 线程还没启动过，将配置写入内存，下次 init_scheduler 会用此配置
        # 构造一个"虚拟"配置结构，用一个常驻变量保存
        global _pending_schedule_cfg
        _pending_schedule_cfg = {
            "enabled": enabled,
            "hour": hour,
            "minute": minute,
            "recurrence": recurrence,
            "weekdays": wd,
        }
        applied_cfg = _pending_schedule_cfg
        log_info(
            f"[scheduler] 调度线程尚未启动，已将配置写入内存: "
            f"enabled={enabled}, recurrence={recurrence}, weekdays={wd}, "
            f"time={hour:02d}:{minute:02d}"
        )

    weekday_hint = ""
    if applied_cfg and applied_cfg.get("recurrence") == "weekly":
        labels = AggregateSchedulerThread.WEEKDAY_LABELS
        wd_list = applied_cfg.get("weekdays") or []
        if wd_list:
            weekday_hint = "（" + "、".join(labels[i] for i in wd_list) + "）"
    log_info(
        f"[scheduler] 定时聚合评分更新完成: enabled={enabled}, "
        f"recurrence={recurrence}{weekday_hint}, time={hour:02d}:{minute:02d}"
    )


def get_aggregate_schedule() -> Dict[str, Any]:
    """获取当前配置。优先级：调度线程实际配置 > 用户刚写入内存的配置 > 默认值。"""
    if _scheduler_thread:
        return _scheduler_thread.get_config()
    if _pending_schedule_cfg:
        return dict(_pending_schedule_cfg)
    return {"enabled": True, "hour": 3, "minute": 0, "recurrence": "daily", "weekdays": []}
