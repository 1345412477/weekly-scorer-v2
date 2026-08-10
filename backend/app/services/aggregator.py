"""周评自动聚合服务：三项得分统一聚合 + 每周仅评一次 + 空数据=0分."""
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal

from sqlalchemy import select, and_, func, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.time_utils import bj_now, bj_today
from app.models.models import (
    WeeklyAggregate,
    WeeklyReport,
    ReportScore,
    AttendanceRecord,
    ChatRecord,
    WeeklySummary,
    Person,
    ScoringConfig,
)
from app.services.ai_scorer import score_attendance, score_chat, AIScoringError
from app.services.wechat_parser import summarize_attendance_for_person, summarize_chat_for_person

logger = logging.getLogger(__name__)


# ============================================================
# 工具函数
# ============================================================

def _get_week_range_for_date(target_date: date):
    """给定日期，返回(周一, 周日)"""
    start = target_date - timedelta(days=target_date.weekday())
    end = start + timedelta(days=6)
    return start, end


# ============================================================
# 配置与人员
# ============================================================

async def get_active_config_safe(db: AsyncSession) -> Optional[ScoringConfig]:
    """获取激活的评分配置（含三项提示词与权重）"""
    try:
        result = await db.execute(select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1))
        return result.scalar_one_or_none()
    except Exception as e:
        logger.warning(f"[聚合] 读取配置失败: {e}")
        return None


def get_weights(config: Optional[ScoringConfig]) -> Dict[str, float]:
    """解析权重字段，默认三项均为 1."""
    default = {"report": 1.0, "attendance": 1.0, "chat": 1.0}
    if not config:
        return default
    weights = getattr(config, "weights", None) or {}
    if isinstance(weights, dict):
        return {
            "report": float(weights.get("report", 1.0) or 1.0),
            "attendance": float(weights.get("attendance", 1.0) or 1.0),
            "chat": float(weights.get("chat", 1.0) or 1.0),
        }
    return default


async def match_person(db: AsyncSession, name: str) -> Optional[Person]:
    """通过姓名匹配人员库"""
    if not name:
        return None
    result = await db.execute(select(Person).where(Person.name == name).limit(1))
    return result.scalar_one_or_none()


# ============================================================
# 单项评分：空数据 = 0 分
# ============================================================

async def _get_report_score(db: AsyncSession, author_name: str,
                            week_start: date, week_end: date):
    """返回 (score, report, score_id) 三元组。
    - 优先选择：author_name + week_start 匹配 + 有 ReportScore 关联的报告
    - 同组内按 created_at 倒序，取最新提交的一份
    - 无周报或未评分 → (None, None, None)
    """
    try:
        # 先查询：作者+week_start 匹配，优先选有 ReportScore 的报告
        inner = (
            select(
                WeeklyReport.id,
                func.row_number()
                .over(
                    order_by=[ReportScore.id.is_(None).asc(), WeeklyReport.created_at.desc()],
                )
                .label("rn"),
            )
            .join(ReportScore, ReportScore.report_id == WeeklyReport.id, isouter=True)
            .where(WeeklyReport.author_name == author_name)
            .where(WeeklyReport.week_start == week_start)
        ).cte("inner")

        best_id_q = select(inner.c.id).where(inner.c.rn == 1).limit(1)
        best_id_r = await db.execute(best_id_q)
        best_id = best_id_r.scalar_one_or_none()
        if not best_id:
            logger.info(f"[聚合] {author_name} 该周无周报 → 周报分=None")
            return None, None, None

        # 读取报告对象
        rep_r = await db.execute(select(WeeklyReport).where(WeeklyReport.id == best_id))
        report = rep_r.scalar_one_or_none()

        # 读取评分
        sr = await db.execute(select(ReportScore).where(ReportScore.report_id == best_id).limit(1))
        score_row = sr.scalar_one_or_none()
        if score_row is None or score_row.total_score is None:
            logger.info(f"[聚合] {author_name} 该周周报尚未评分 → 周报分=None")
            return None, report, None
        return float(score_row.total_score), report, score_row.id
    except Exception as e:
        logger.warning(f"[聚合] 获取周报分数异常 {author_name}: {e}")
        return None, None, None


async def _get_attendance_score(db: AsyncSession, author_name: str, week_start: date, week_end: date, prompt: str) -> Optional[float]:
    """考勤分：无考勤记录 → None；有记录 → AI 评分（0-100）。

    注意：项目策略为"不做规则兜底"，AI 评分失败时记录错误日志并返回 None，
    由上层/前端提示用户检查 AI 服务与提示词配置。
    """
    try:
        q = select(AttendanceRecord).where(
            AttendanceRecord.author_name == author_name,
            AttendanceRecord.week_start == week_start,
        )
        result = await db.execute(q)
        records = list(result.scalars().all())
        if not records:
            logger.info(f"[聚合] {author_name} 该周无考勤记录 → 考勤分=None")
            return None

        rec_dicts = [
            {
                "author_name": author_name,
                "record_date": r.record_date,
                "check_in_time": r.check_in_time,
                "check_out_time": r.check_out_time,
                "check_in_location": r.check_in_location,
                "check_out_location": r.check_out_location,
                "work_duration_hours": float(r.work_duration_hours) if r.work_duration_hours is not None else None,
                "attendance_status": r.attendance_status,
                "notes": r.notes,
            }
            for r in records
        ]
        summary = summarize_attendance_for_person(rec_dicts, author_name)
        try:
            ai_result = await score_attendance(summary, author_name, "", prompt, db=db)
            score = float(ai_result["score"])
            # 加班分在 100 分基础上累加，不设上限
            return max(0.0, score)
        except AIScoringError as e:
            logger.error(
                f"[聚合] 考勤 AI 评分失败 {author_name}（无规则兜底，"
                f"请检查 AI 服务连接与考勤评分提示词）: {e}"
            )
            return None
    except Exception as e:
        logger.error(f"[聚合] 考勤分获取异常 {author_name}（无规则兜底）: {e}")
        return None


async def _get_chat_score(db: AsyncSession, author_name: str, week_start: date, week_end: date, prompt: str) -> Optional[float]:
    """沟通分：一周小结(满分20) + 会话记录(满分80)，独立评分后相加。
    
    新规则：
    - 一周小结满分20分（按工作会话次数和最晚时间扣分）
    - 会话记录满分80分（按敏感词和响应时间扣分）
    - 两部分独立评分，缺失部分计0分（不显示"/"）
    - 两部分相加=沟通总分（0-100）
    """
    try:
        cr = await db.execute(
            select(ChatRecord).where(
                ChatRecord.author_name == author_name,
                ChatRecord.week_start == week_start,
            )
        )
        chat_records = list(cr.scalars().all())

        sr = await db.execute(
            select(WeeklySummary).where(
                WeeklySummary.author_name == author_name,
                WeeklySummary.week_start == week_start,
            )
        )
        summaries = list(sr.scalars().all())

        has_chat = bool(chat_records)
        has_summary = bool(summaries)
        
        if not has_chat and not has_summary:
            logger.info(f"[聚合] {author_name} 该周无一周小结和聊天记录 → 沟通分=0")
            return 0.0

        chat_dicts = [
            {
                "author_name": r.author_name,
                "message_date": r.message_date,
                "conversation_topic": r.conversation_topic,
                "counterparty": r.counterparty,
                "message_count": r.message_count or 0,
                "response_minutes": float(r.response_minutes) if r.response_minutes is not None else None,
                "content_summary": r.content_summary,
                "raw_messages": r.raw_messages,
            }
            for r in chat_records
        ] if has_chat else []
        
        summary_dicts = [
            {
                "author_name": s.author_name,
                "work_session_count": s.work_session_count,
                "total_minutes": s.total_minutes,
                "latest_time": s.latest_time,
            }
            for s in summaries
        ] if has_summary else []

        # 合并所有原始消息
        all_raw_messages = []
        for r in chat_dicts:
            msgs = r.get("raw_messages") or []
            if isinstance(msgs, list):
                all_raw_messages.extend(msgs)

        # 读取敏感词配置和 summary_prompt
        config = await get_active_config_safe(db)
        sensitive_words = None
        summary_prompt = ""
        if config:
            sw = getattr(config, "sensitive_words", None)
            if sw and isinstance(sw, list):
                sensitive_words = sw
            summary_prompt = getattr(config, "summary_prompt", "") or ""

        # 分别构建两段摘要，明确传递是否有数据的标志
        summary_text = summarize_chat_for_person(chat_dicts, author_name, summary_dicts)

        # 使用新版沟通评分提示词
        ai_result = await score_chat(
            summary_text, author_name, "", prompt,
            sensitive_words=sensitive_words,
            raw_messages=all_raw_messages,
            has_summary=has_summary,
            has_chat=has_chat,
            summary_prompt=summary_prompt,
            db=db,
        )
        score = float(ai_result["score"])
        return max(0.0, min(100.0, score))
    except AIScoringError as e:
        logger.warning(f"[聚合] 沟通 AI 评分失败 {author_name}: {e}")
        return None
    except Exception as e:
        logger.warning(f"[聚合] 沟通分异常 {author_name}: {e}")
        return None


# ============================================================
# 核心：auto_aggregate（每周只评一次）
# ============================================================

async def auto_aggregate(
    db: AsyncSession,
    person_id: Optional[str],
    author_name: str,
    department: Optional[str] = None,
    department_id: Optional[str] = None,
    week_start: Optional[date] = None,
    week_end: Optional[date] = None,
    preserve_manual: bool = True,
    force: bool = False,
) -> Optional[WeeklyAggregate]:
    """
    聚合某员工某周的三项得分。
    - 每周只评一次：若已存在 WeeklyAggregate 且 status="done"/"manual" → 直接返回不再评分
    - force=True：忽略 status 保护，强制重新评分（管理员恢复 AI 时使用）
    - 缺失数据=None：无数据的维度返回 None（前端显示 /），总分按 0 参与计算
    """
    if not author_name:
        return None

    if week_start is None or week_end is None:
        today = bj_today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
    else:
        # 归一化 week_end = week_start + 6 天，保证各表周范围一致
        # （避免周报文件 week_end=周五 vs 考勤/聊天 week_end=周日 导致重复 aggregate）
        expected_week_end = week_start + timedelta(days=6)
        if week_end != expected_week_end:
            week_end = expected_week_end

    # 补齐 person_id / department
    if not person_id or not department:
        person = await match_person(db, author_name)
        if person:
            person_id = person_id or person.id
            department = department or person.department_name or ""
            department_id = department_id or person.department_id

    # === 查现有 aggregate（只按 author_name + week_start 匹配）===
    result = await db.execute(
        select(WeeklyAggregate).where(
            WeeklyAggregate.author_name == author_name,
            WeeklyAggregate.week_start == week_start,
        ).limit(1)
    )
    agg = result.scalar_one_or_none()

    # 若已存在且已完成评分 → 同步 report_score + 重新计算考勤/沟通分（OCR 可能刚完成），
    # 但始终尊重 manual_override 保护。
    if agg and not force:
        status = getattr(agg, "status", "done") or "done"
        if status in ("done", "manual", "pending"):
            new_report_score, new_report_obj, new_report_score_id = await _get_report_score(
                db, author_name, week_start, week_end
            )
            old_report_score_val = float(agg.report_score) if agg.report_score is not None else None
            needs_update = False

            # 始终同步 report_score（即使分数相同，ID 也可能因删除重建而改变）
            if new_report_score is not None and abs((old_report_score_val or 0) - new_report_score) > 0.1:
                agg.report_score = Decimal(str(round(new_report_score, 1)))
                needs_update = True
            if new_report_score_id and agg.report_score_id != new_report_score_id:
                agg.report_score_id = new_report_score_id
                needs_update = True
            elif not new_report_score_id and agg.report_score_id is not None:
                agg.report_score_id = None
                needs_update = True

            # 读取 manual_override 和配置
            manual_override = {}
            if getattr(agg, "manual_override", None):
                manual_override = dict(agg.manual_override) if isinstance(agg.manual_override, dict) else {}
            config = await get_active_config_safe(db)
            attendance_prompt = getattr(config, "attendance_prompt", "") or ""
            chat_prompt = getattr(config, "chat_prompt", "") or ""

            # 重新计算考勤分（除非 manual_override 保护）
            old_attendance = float(agg.attendance_score) if agg.attendance_score is not None else None
            if not manual_override.get("attendance_score"):
                new_attendance = await _get_attendance_score(db, author_name, week_start, week_end, attendance_prompt)
                if new_attendance is not None and (old_attendance is None or abs(old_attendance - new_attendance) > 0.1):
                    agg.attendance_score = Decimal(str(round(new_attendance, 1)))
                    needs_update = True

            # 重新计算沟通分（除非 manual_override 保护）— 解决 OCR 完成后沟通分未更新的问题
            old_chat = float(agg.chat_score) if agg.chat_score is not None else None
            if not manual_override.get("chat_score"):
                new_chat = await _get_chat_score(db, author_name, week_start, week_end, chat_prompt)
                if new_chat is not None and (old_chat is None or abs(old_chat - new_chat) > 0.1):
                    agg.chat_score = Decimal(str(round(new_chat, 1)))
                    needs_update = True

            if needs_update:
                total = (
                    float(agg.report_score or 0)
                    + float(agg.attendance_score or 0)
                    + float(agg.chat_score or 0)
                )
                agg.composite_score = Decimal(str(round(total, 2)))

            # 评分完成后更新状态
            if status == "pending" and new_report_score is not None:
                agg.status = "done"
            elif status == "pending" and new_report_score is None:
                # 有周报对象但未评分 → 主动重试 AI 评分（修复"评分中"卡住）
                if new_report_obj is not None:
                    from app.services.scoring import trigger_scoring
                    try:
                        logger.info(
                            f"[聚合] {author_name} 该周状态=pending 且无评分，"
                            f"主动重试 AI 评分（report_id={new_report_obj.id}）"
                        )
                        await trigger_scoring(new_report_obj.id, db)
                        # 评分成功后，重新读取 report_score
                        retry_score, retry_rep, retry_sid = await _get_report_score(
                            db, author_name, week_start, week_end
                        )
                        if retry_score is not None:
                            agg.report_score = Decimal(str(round(retry_score, 1)))
                            if retry_sid:
                                agg.report_score_id = retry_sid
                            needs_update = True
                            # 重算总分（之前的 needs_update 分支已执行过，此处补算）
                            total = (
                                float(agg.report_score or 0)
                                + float(agg.attendance_score or 0)
                                + float(agg.chat_score or 0)
                            )
                            agg.composite_score = Decimal(str(round(total, 2)))
                            agg.status = "done"
                            logger.info(
                                f"[聚合] {author_name} 该周重试 AI 评分成功，report_score={retry_score}，"
                                f"composite={float(agg.composite_score)}，状态 pending→done"
                            )
                        else:
                            # 重试评分完成但仍无分数（如 trigger_scoring 未报错但 ReportScore 未写入）
                            # → 累加 retry_count 并转 failed
                            current_retry = int(getattr(agg, "retry_count", 0) or 0) + 1
                            agg.retry_count = current_retry
                            agg.error_message = (
                                "AI 评分执行完成但未生成分数记录（请检查 ReportScore 写入逻辑、"
                                "或 AI 返回内容不符合评分格式）"
                            )
                            if current_retry >= 2:
                                agg.status = "failed"
                                logger.warning(
                                    f"[聚合] {author_name} 该周重试 AI 评分 {current_retry} 次后仍无分数，"
                                    f"状态 pending→failed"
                                )
                            else:
                                logger.warning(
                                    f"[聚合] {author_name} 该周第 {current_retry} 次重试 AI 评分后仍无分数，"
                                    f"状态保持 pending"
                                )
                            needs_update = True
                    except Exception as e:
                        err_msg = str(e)[:500]
                        # 累加 retry_count，持久化错误消息；超过 3 次转 failed
                        current_retry = int(getattr(agg, "retry_count", 0) or 0) + 1
                        agg.retry_count = current_retry
                        agg.error_message = err_msg
                        if current_retry >= 3:
                            agg.status = "failed"
                            logger.warning(
                                f"[聚合] {author_name} 该周重试 AI 评分已达 {current_retry} 次，"
                                f"状态 pending→failed，错误：{err_msg}"
                            )
                        else:
                            logger.warning(
                                f"[聚合] {author_name} 该周第 {current_retry} 次重试 AI 评分失败：{err_msg}，"
                                f"状态保持 pending（下一次聚合继续重试，上限 3 次）"
                            )
                        needs_update = True
                else:
                    # 连周报对象都没有，pending 不合理 → 降级为 done
                    agg.status = "done"
                    logger.warning(
                        f"[聚合] {author_name} 该周状态=pending 但无任何周报对象，"
                        f"降级为 done（避免前端永远显示评分中）"
                    )

            agg.updated_at = bj_now()
            await db.commit()
            await db.refresh(agg)
            logger.info(
                f"[聚合] {author_name} 该周状态={status}，"
                f"{'已同步分数' if needs_update else '分数无变化'}（report={new_report_score}, "
                f"attendance={old_attendance}→{float(agg.attendance_score) if agg.attendance_score else None}, "
                f"chat={old_chat}→{float(agg.chat_score) if agg.chat_score else None}）"
            )
            return agg

    # === 读配置 ===
    config = await get_active_config_safe(db)
    weights = get_weights(config)
    attendance_prompt = getattr(config, "attendance_prompt", "") or ""
    chat_prompt = getattr(config, "chat_prompt", "") or ""

    # === 读取 manual_override 保护逻辑（未被覆盖的维度才重新计算 AI） ===
    manual_override = {}
    if agg and getattr(agg, "manual_override", None):
        manual_override = dict(agg.manual_override) if isinstance(agg.manual_override, dict) else {}

    # 周报分
    report_obj = None
    report_score_id = None
    if preserve_manual and manual_override.get("report_score") and agg and agg.report_score is not None:
        report_score = float(agg.report_score)
    else:
        report_score, report_obj, report_score_id = await _get_report_score(db, author_name, week_start, week_end)

    # 考勤分
    if preserve_manual and manual_override.get("attendance_score") and agg and agg.attendance_score is not None:
        attendance_score = float(agg.attendance_score)
    else:
        attendance_score = await _get_attendance_score(db, author_name, week_start, week_end, attendance_prompt)

    # 沟通分
    if preserve_manual and manual_override.get("chat_score") and agg and agg.chat_score is not None:
        chat_score = float(agg.chat_score)
    else:
        chat_score = await _get_chat_score(db, author_name, week_start, week_end, chat_prompt)

    # === 总分（三项相加，缺失项按 0 计算）===
    total = (
        (report_score or 0) * weights["report"]
        + (attendance_score or 0) * weights["attendance"]
        + (chat_score or 0) * weights["chat"]
    )

    # === 写入 / 更新 WeeklyAggregate ===
    if agg:
        agg.person_id = person_id or agg.person_id
        agg.department = department or agg.department or ""
        agg.department_id = department_id or agg.department_id
        # 单项分数：None 保持 None（前端显示 /），非 None 才更新
        if report_score is not None:
            agg.report_score = Decimal(str(round(report_score, 1)))
        if attendance_score is not None:
            agg.attendance_score = Decimal(str(round(attendance_score, 1)))
        if chat_score is not None:
            agg.chat_score = Decimal(str(round(chat_score, 1)))
        agg.composite_score = Decimal(str(round(total, 2)))
        if report_score_id:
            agg.report_score_id = report_score_id
        # 只有当尚未被手动覆盖时才标记状态；
        # 如果原本是 manual，则保留 manual
        if getattr(agg, "status", None) != "manual":
            has_report_but_no_score = (report_obj is not None) and (report_score is None)
            agg.status = "pending" if has_report_but_no_score else "done"
        agg.updated_at = bj_now()
    else:
        has_report_but_no_score = (report_obj is not None) and (report_score is None)
        agg = WeeklyAggregate(
            person_id=person_id,
            author_name=author_name,
            department=department or "",
            department_id=department_id,
            week_start=week_start,
            week_end=week_end,
            report_score=Decimal(str(round(report_score, 1))) if report_score is not None else None,
            attendance_score=Decimal(str(round(attendance_score, 1))) if attendance_score is not None else None,
            chat_score=Decimal(str(round(chat_score, 1))) if chat_score is not None else None,
            composite_score=Decimal(str(round(total, 2))),
            report_score_id=report_score_id,
            manual_override={},
            status="pending" if has_report_but_no_score else "done",
        )
        db.add(agg)

    logger.info(
        f"[聚合] {author_name} {week_start}~{week_end} -> "
        f"周报={report_score}, 考勤={attendance_score}, 沟通={chat_score}, 总分={total}"
    )
    await db.commit()
    await db.refresh(agg)
    return agg


# ============================================================
# 对最新一周的所有员工进行聚合（定时任务入口）
# ============================================================

async def auto_aggregate_for_latest_week(db: AsyncSession) -> int:
    """
    对本周（以今天为参照）的所有启用员工进行一次聚合评分。
    - 已完成评分的跳过（status=done/manual）
    - 空数据=0分也会写入（保证每人每周一条完整记录）
    - 返回处理的人数
    """
    week_start, week_end = _get_week_range_for_date(bj_today())

    # 获取所有启用员工
    result = await db.execute(select(Person).where(Person.is_active == True))
    persons = list(result.scalars().all())
    if not persons:
        logger.info("[聚合] 无启用员工，跳过")
        return 0

    count = 0
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
                preserve_manual=True,
                force=False,
            )
            count += 1
        except Exception as e:
            logger.warning(f"[聚合] 处理 {p.name} 失败: {e}")
            continue

    logger.info(f"[聚合] 本周已完成 {count}/{len(persons)} 位员工的评分聚合")
    return count


# ============================================================
# 管理员手动改分 / 恢复 AI
# ============================================================

async def update_aggregate_scores(
    db: AsyncSession,
    aggregate_id: str,
    report_score: Optional[float] = None,
    attendance_score: Optional[float] = None,
    chat_score: Optional[float] = None,
    modified_by: str = "admin",
) -> Optional[WeeklyAggregate]:
    """管理员手动修改分数 → 标记为 status=manual，自动重新计算 composite"""
    result = await db.execute(select(WeeklyAggregate).where(WeeklyAggregate.id == aggregate_id).limit(1))
    agg = result.scalar_one_or_none()
    if not agg:
        return None

    manual = dict(agg.manual_override) if isinstance(agg.manual_override, dict) else {}

    if report_score is not None:
        agg.report_score = Decimal(str(round(float(report_score), 1)))
        manual["report_score"] = True
    if attendance_score is not None:
        agg.attendance_score = Decimal(str(round(float(attendance_score), 1)))
        manual["attendance_score"] = True
    if chat_score is not None:
        agg.chat_score = Decimal(str(round(float(chat_score), 1)))
        manual["chat_score"] = True

    composite = 0.0
    if agg.report_score is not None:
        composite += float(agg.report_score)
    if agg.attendance_score is not None:
        composite += float(agg.attendance_score)
    if agg.chat_score is not None:
        composite += float(agg.chat_score)
    agg.composite_score = Decimal(str(round(composite, 2)))

    agg.manual_override = manual
    agg.modified_by = modified_by
    agg.modified_at = bj_now()
    agg.updated_at = bj_now()
    agg.status = "manual"  # 已被管理员手动覆盖

    await db.commit()
    await db.refresh(agg)
    return agg


async def restore_ai_scores(db: AsyncSession, aggregate_id: str) -> Optional[WeeklyAggregate]:
    """恢复 AI 评分：清空 manual_override → force=True 重跑聚合"""
    result = await db.execute(select(WeeklyAggregate).where(WeeklyAggregate.id == aggregate_id).limit(1))
    agg = result.scalar_one_or_none()
    if not agg:
        return None

    agg.manual_override = {}
    agg.modified_by = None
    agg.modified_at = None
    agg.status = "pending"
    await db.commit()

    return await auto_aggregate(
        db,
        person_id=agg.person_id,
        author_name=agg.author_name,
        department=agg.department,
        department_id=agg.department_id,
        week_start=agg.week_start,
        week_end=agg.week_end,
        preserve_manual=False,
        force=True,
    )


# ============================================================
# 列表查询 & report_id 映射
# ============================================================

async def _get_report_ids_for_aggregates(db: AsyncSession, aggregates: List[WeeklyAggregate]) -> Dict[str, str]:
    if not aggregates:
        return {}
    pairs = [(a.author_name, a.week_start) for a in aggregates if a.author_name and a.week_start]
    if not pairs:
        return {}
    id_map = {}
    try:
        q = select(WeeklyReport).where(
            tuple_(WeeklyReport.author_name, WeeklyReport.week_start).in_(pairs)
        ).order_by(WeeklyReport.created_at.asc())
        res = await db.execute(q)
        reports_by_key = {}
        for r in res.scalars().all():
            key = (r.author_name, r.week_start)
            if key not in reports_by_key:
                reports_by_key[key] = r.id
        for a in aggregates:
            key = (a.author_name, a.week_start)
            if key in reports_by_key:
                id_map[a.id] = reports_by_key[key]
    except Exception as e:
        logger.warning(f"[聚合] 批量查找周报id失败: {e}")
    return id_map


async def list_aggregates(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    author_name: Optional[str] = None,
    department: Optional[str] = None,
    week_start: Optional[date] = None,
) -> Dict[str, Any]:
    # 同一人同一周可能有多条记录（并发创建），只取最新的一条
    # 使用 row_number 窗口函数去重
    inner_q = (
        select(
            WeeklyAggregate.id,
            func.row_number()
            .over(
                partition_by=[WeeklyAggregate.author_name, WeeklyAggregate.week_start],
                order_by=WeeklyAggregate.created_at.desc(),
            )
            .label("rn"),
        )
    ).cte("dedup")

    q = select(WeeklyAggregate).join(
        inner_q, WeeklyAggregate.id == inner_q.c.id
    ).where(inner_q.c.rn == 1)

    conditions = []
    if author_name:
        conditions.append(WeeklyAggregate.author_name.contains(author_name))
    if department:
        conditions.append(WeeklyAggregate.department.contains(department))
    if week_start:
        conditions.append(WeeklyAggregate.week_start == week_start)
    if conditions:
        q = q.where(and_(*conditions))

    q = q.order_by(WeeklyAggregate.updated_at.desc())

    # 计数也要去重
    count_q = select(WeeklyAggregate).join(
        inner_q, WeeklyAggregate.id == inner_q.c.id
    ).where(inner_q.c.rn == 1)
    if conditions:
        count_q = count_q.where(and_(*conditions))

    total_result = await db.execute(select(func.count()).select_from(count_q.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(q.offset((page - 1) * size).limit(size))
    items = list(result.scalars().all())
    report_id_map = await _get_report_ids_for_aggregates(db, items)

    # 获取有数据的周列表（用于前端筛选）
    weeks_q = select(WeeklyAggregate.week_start).distinct()
    weeks_result = await db.execute(weeks_q)
    available_weeks = [str(row[0]) for row in weeks_result.fetchall() if row[0]]

    return {
        "items": [aggregate_to_dict(a, report_id_map.get(a.id)) for a in items],
        "total": total,
        "page": page,
        "size": size,
        "available_weeks": sorted(available_weeks, reverse=True),
    }


def aggregate_to_dict(a: WeeklyAggregate, report_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": a.id,
        "author_name": a.author_name,
        "department": a.department or "",
        "person_id": a.person_id,
        "week_start": a.week_start.isoformat() if a.week_start else None,
        "week_end": a.week_end.isoformat() if a.week_end else None,
        "report_score": float(a.report_score) if a.report_score is not None else None,
        "attendance_score": float(a.attendance_score) if a.attendance_score is not None else None,
        "chat_score": float(a.chat_score) if a.chat_score is not None else None,
        "composite_score": float(a.composite_score) if a.composite_score is not None else None,
        "report_id": report_id,
        "manual_override": a.manual_override or {},
        "modified_by": a.modified_by,
        "modified_at": a.modified_at.isoformat() if a.modified_at else None,
        "created_at": a.created_at.isoformat() if hasattr(a, "created_at") and a.created_at else None,
        "updated_at": a.updated_at.isoformat() if hasattr(a, "updated_at") and a.updated_at else None,
        "status": getattr(a, "status", "done"),
        "error_message": getattr(a, "error_message", "") or "",
        "retry_count": int(getattr(a, "retry_count", 0) or 0),
    }
