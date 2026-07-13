"""排行榜 API"""
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.models import WeeklyReport, ReportScore, Person, WeeklyAggregate
from app.utils.time_utils import bj_today

router = APIRouter(prefix="/api/v1/leaderboard", tags=["排行榜"])


def get_current_week():
    today = bj_today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_previous_week(current_monday, current_sunday):
    prev_monday = current_monday - timedelta(days=7)
    prev_sunday = current_sunday - timedelta(days=7)
    return prev_monday, prev_sunday


def get_current_month():
    today = bj_today()
    first = today.replace(day=1)
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return first, last


def _resolve_week_range(week_start_str=None):
    """根据 week_start 字符串解析周一/周日，未传则用当前周"""
    if week_start_str:
        try:
            target = date.fromisoformat(week_start_str)
            monday = target
            sunday = monday + timedelta(days=6)
            return monday, sunday
        except ValueError:
            pass
    return get_current_week()


def _first_submission_cte(period, department_filter=None, week_start_str=None):
    """
    生成一个 CTE：在指定周期内，每位员工每周最新一次提交且有评分的 weekly_report.id
    策略：按 author_name + week_start + week_end 分组，优先选有 ReportScore 关联的报告，
          同组内按 created_at 倒序，取最新一条，避免旧/无评分报告被选中
    """
    current_monday, current_sunday = _resolve_week_range(week_start_str)

    inner = (
        select(
            WeeklyReport.id,
            WeeklyReport.author_name,
            WeeklyReport.department,
            WeeklyReport.week_start,
            WeeklyReport.week_end,
            WeeklyReport.created_at,
            func.row_number()
            .over(
                partition_by=[WeeklyReport.author_name, WeeklyReport.week_start, WeeklyReport.week_end],
                # 1. 优先有 ReportScore 的报告 (NotNull < Null)
                # 2. 同组内按 created_at 倒序，取最新一份
                order_by=[ReportScore.id.is_(None).asc(), WeeklyReport.created_at.desc()],
            )
            .label("rn"),
        )
        .join(ReportScore, ReportScore.report_id == WeeklyReport.id, isouter=True)
        .where(WeeklyReport.status.in_(["scored", "submitted"]))
    )

    if period == "week":
        inner = inner.where(WeeklyReport.week_start >= current_monday).where(
            WeeklyReport.week_end <= current_sunday
        )
    elif period == "month":
        first, last = get_current_month()
        inner = inner.where(WeeklyReport.week_start >= first).where(WeeklyReport.week_end <= last)

    if department_filter:
        inner = inner.where(WeeklyReport.department == department_filter)

    inner_cte = inner.cte("inner_candidates")

    first_cte = (
        select(
            inner_cte.c.id,
            inner_cte.c.author_name,
            inner_cte.c.department,
            inner_cte.c.week_start,
            inner_cte.c.week_end,
        )
        .where(inner_cte.c.rn == 1)
        .cte("first_submissions")
    )
    return first_cte


@router.get("")
async def get_leaderboard(
    period: str = Query("week", pattern="^(week|month|all)$"),
    department: Optional[str] = None,
    sort_by: str = Query("total_score", pattern="^(total_score|avg_score|report_count)$"),
    week_start: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """获取排行榜数据：每位员工每周只算首次提交的分数"""
    dep_filter = department if department and department != "all" else None
    first_cte = _first_submission_cte(period, dep_filter, week_start)

    total_score = func.coalesce(func.sum(ReportScore.total_score), 0).label("total_score")
    avg_score = func.coalesce(func.avg(ReportScore.total_score), 0).label("avg_score")
    report_count = func.count(first_cte.c.id).label("report_count")
    latest_grade = func.max(ReportScore.grade).label("latest_grade")
    latest_report_id = func.max(first_cte.c.id).label("latest_report_id")

    # 子查询：获取每位员工在周期内的平均 chat_score（从 weekly_aggregates 表）
    chat_subq = (
        select(
            WeeklyAggregate.author_name,
            func.coalesce(func.avg(WeeklyAggregate.chat_score), 0).label("avg_chat_score"),
        )
        .where(WeeklyAggregate.author_name.isnot(None))
    )
    if period == "week":
        current_monday, current_sunday = _resolve_week_range(week_start)
        chat_subq = chat_subq.where(
            WeeklyAggregate.week_start >= current_monday,
            WeeklyAggregate.week_end <= current_sunday,
        )
    elif period == "month":
        first, last = get_current_month()
        chat_subq = chat_subq.where(
            WeeklyAggregate.week_start >= first,
            WeeklyAggregate.week_end <= last,
        )
    chat_subq = chat_subq.group_by(WeeklyAggregate.author_name).subquery("chat_scores")

    query = (
        select(
            first_cte.c.author_name,
            first_cte.c.department,
            total_score,
            avg_score,
            report_count,
            latest_grade,
            latest_report_id,
            chat_subq.c.avg_chat_score,
        )
        .select_from(first_cte)
        .join(ReportScore, ReportScore.report_id == first_cte.c.id, isouter=True)
        .outerjoin(chat_subq, chat_subq.c.author_name == first_cte.c.author_name)
        .group_by(first_cte.c.author_name, first_cte.c.department, chat_subq.c.avg_chat_score)
    )

    sort_column = {
        "total_score": total_score,
        "avg_score": avg_score,
        "report_count": report_count,
    }.get(sort_by, total_score)
    query = query.order_by(desc(sort_column))

    result = await db.execute(query)
    rows = result.fetchall()

    # 计算趋势（与上一周「首条提交」分数对比）
    current_monday, current_sunday = _resolve_week_range(week_start)
    prev_monday, prev_sunday = get_previous_week(current_monday, current_sunday)

    prev_scores = {}
    if period == "week":
        # 上周周期内每位员工的有效报告（优先取有 ReportScore 的那条）
        prev_inner = (
            select(
                WeeklyReport.id,
                WeeklyReport.author_name,
                func.row_number()
                .over(
                    partition_by=[WeeklyReport.author_name, WeeklyReport.week_start, WeeklyReport.week_end],
                    order_by=[ReportScore.id.is_(None).asc(), WeeklyReport.created_at.desc()],
                )
                .label("rn"),
            )
            .join(ReportScore, ReportScore.report_id == WeeklyReport.id, isouter=True)
            .where(WeeklyReport.status.in_(["scored", "submitted"]))
            .where(WeeklyReport.week_start >= prev_monday)
            .where(WeeklyReport.week_end <= prev_sunday)
        )
        if dep_filter:
            prev_inner = prev_inner.where(WeeklyReport.department == dep_filter)
        prev_inner_cte = prev_inner.cte("prev_inner")

        prev_query = (
            select(
                prev_inner_cte.c.author_name,
                func.coalesce(func.avg(ReportScore.total_score), 0).label("prev_avg"),
            )
            .select_from(prev_inner_cte)
            .join(ReportScore, ReportScore.report_id == prev_inner_cte.c.id, isouter=True)
            .where(prev_inner_cte.c.rn == 1)
            .group_by(prev_inner_cte.c.author_name)
        )
        prev_result = await db.execute(prev_query)
        for row in prev_result.fetchall():
            prev_scores[row.author_name] = float(row.prev_avg or 0)

    rankings = []
    for idx, row in enumerate(rows):
        name = row.author_name
        cur_avg = round(float(row.avg_score or 0), 1)
        prev_avg = prev_scores.get(name, 0)
        trend = round(cur_avg - prev_avg, 1) if prev_avg > 0 else None
        rankings.append({
            "rank": idx + 1,
            "author_name": name,
            "department": row.department or "",
            "total_score": round(float(row.total_score or 0), 1),
            "avg_score": cur_avg,
            "report_count": int(row.report_count or 0),
            "latest_grade": row.latest_grade or "",
            "chat_score": round(float(row.avg_chat_score or 0), 1) if row.avg_chat_score is not None else None,
            "trend": trend,
        })

    # 总报告数（仍然按「首条」口径统计，避免重复提交影响）
    count_query = select(func.count()).select_from(first_cte)
    count_r = await db.execute(count_query)
    total_reports = count_r.scalar() or 0

    return {
        "rankings": rankings,
        "period": period,
        "total_reports": total_reports,
    }


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取总览统计数据"""
    total_r = await db.execute(
        select(func.count()).select_from(WeeklyReport)
        .where(WeeklyReport.status.in_(["scored", "submitted"]))
    )
    total_reports = total_r.scalar() or 0

    scored_r = await db.execute(
        select(func.count()).select_from(WeeklyReport)
        .where(WeeklyReport.status == "scored")
    )
    scored_reports = scored_r.scalar() or 0

    avg_r = await db.execute(
        select(func.avg(ReportScore.total_score))
    )
    avg_score = round(float(avg_r.scalar() or 0), 1)

    grade_r = await db.execute(
        select(ReportScore.grade, func.count())
        .group_by(ReportScore.grade)
    )
    grade_distribution = {row[0]: row[1] for row in grade_r.fetchall() if row[0]}

    avg_score_label = func.avg(ReportScore.total_score).label("avg_score")
    trend_query = (
        select(WeeklyReport.week_start, WeeklyReport.week_end, avg_score_label)
        .select_from(WeeklyReport)
        .join(ReportScore, ReportScore.report_id == WeeklyReport.id)
        .where(WeeklyReport.status == "scored")
        .group_by(WeeklyReport.week_start, WeeklyReport.week_end)
        .order_by(desc(WeeklyReport.week_start))
        .limit(12)
    )
    trend_r = await db.execute(trend_query)
    trend = [
        {
            "week_start": str(row.week_start),
            "week_end": str(row.week_end),
            "avg_score": round(float(row.avg_score or 0), 1),
        }
        for row in trend_r.fetchall()
    ]

    return {
        "total_reports": total_reports,
        "scored_reports": scored_reports,
        "avg_score": avg_score,
        "grade_distribution": grade_distribution,
        "weekly_trend": trend,
    }


@router.get("/dashboard")
async def get_dashboard_overview(db: AsyncSession = Depends(get_db)):
    """获取 Dashboard 聚合数据：未提交人员 / 评级较低 / 进步较大"""
    current_monday, current_sunday = get_current_week()
    prev_monday, prev_sunday = get_previous_week(current_monday, current_sunday)

    # 1. 本周已提交人员
    submitted_q = (
        select(WeeklyReport.author_name)
        .where(WeeklyReport.status.in_(["scored", "submitted"]))
        .where(WeeklyReport.week_start >= current_monday)
        .where(WeeklyReport.week_end <= current_sunday)
    )
    submitted_r = await db.execute(submitted_q)
    submitted_names = {row[0] for row in submitted_r.fetchall()}

    # 2. 未提交人员（persons 表中 - 已提交）
    persons_q = select(Person).where(Person.is_active == True)
    persons_r = await db.execute(persons_q)
    persons = persons_r.scalars().all()

    not_submitted = []
    for p in persons:
        if p.name not in submitted_names:
            not_submitted.append({
                "name": p.name,
                "department": p.department_name or "",
                "position": p.position or "",
            })

    # 3. 本周已评分记录（每人取最新一份报告，优先有 ReportScore 关联的）
    cur_inner = (
        select(
            WeeklyReport.id,
            WeeklyReport.author_name,
            WeeklyReport.department,
            func.row_number()
            .over(
                partition_by=[WeeklyReport.author_name, WeeklyReport.week_start, WeeklyReport.week_end],
                order_by=[ReportScore.id.is_(None).asc(), WeeklyReport.created_at.desc()],
            )
            .label("rn"),
        )
        .join(ReportScore, ReportScore.report_id == WeeklyReport.id, isouter=True)
        .where(WeeklyReport.status.in_(["scored", "submitted"]))
        .where(WeeklyReport.week_start >= current_monday)
        .where(WeeklyReport.week_end <= current_sunday)
    ).cte("cur_inner")

    scored_q = (
        select(
            cur_inner.c.author_name,
            cur_inner.c.department,
            ReportScore.total_score,
            ReportScore.grade,
            ReportScore.ai_comment,
        )
        .select_from(cur_inner)
        .join(ReportScore, ReportScore.report_id == cur_inner.c.id)
        .where(cur_inner.c.rn == 1)
    )
    scored_r = await db.execute(scored_q)
    scored_rows = scored_r.fetchall()

    # 本周低分人员（排名后 30%）
    if scored_rows:
        sorted_by_score = sorted(scored_rows, key=lambda r: float(r.total_score or 0))
        low_count = max(1, len(sorted_by_score) // 3)
        low_scorers = []
        for r in sorted_by_score[:low_count]:
            low_scorers.append({
                "name": r.author_name,
                "department": r.department or "",
                "total_score": round(float(r.total_score or 0), 1),
                "grade": r.grade or "",
                "comment": r.ai_comment or "",
            })
    else:
        low_scorers = []

    # 4. 进步较大人员（本周 vs 上周分数差 > 0，均取每人最新有评分的报告）
    # 统一工具函数：在给定 [mon, sun] 内，取每人每周最新且有评分的报告的 avg_score
    def _score_map(monday, sunday):
        inner = (
            select(
                WeeklyReport.id,
                WeeklyReport.author_name,
                func.row_number()
                .over(
                    partition_by=[WeeklyReport.author_name, WeeklyReport.week_start, WeeklyReport.week_end],
                    order_by=[ReportScore.id.is_(None).asc(), WeeklyReport.created_at.desc()],
                )
                .label("rn"),
            )
            .join(ReportScore, ReportScore.report_id == WeeklyReport.id, isouter=True)
            .where(WeeklyReport.status.in_(["scored", "submitted"]))
            .where(WeeklyReport.week_start >= monday)
            .where(WeeklyReport.week_end <= sunday)
        ).cte("prev_inner")

        q = (
            select(
                inner.c.author_name,
                func.coalesce(func.avg(ReportScore.total_score), 0).label("avg_score"),
            )
            .select_from(inner)
            .join(ReportScore, ReportScore.report_id == inner.c.id, isouter=True)
            .where(inner.c.rn == 1)
            .group_by(inner.c.author_name)
        )
        return q

    prev_avg_q = _score_map(prev_monday, prev_sunday)
    prev_avg_r = await db.execute(prev_avg_q)
    prev_avg_map = {}
    for row in prev_avg_r.fetchall():
        prev_avg_map[row.author_name] = float(row.avg_score or 0)

    # 获取本周（每人首次提交）分数
    cur_avg_q = _score_map(current_monday, current_sunday)
    cur_avg_r = await db.execute(cur_avg_q)
    improvements = []
    for row in cur_avg_r.fetchall():
        name = row.author_name
        cur_avg = float(row.avg_score or 0)
        prev_avg = prev_avg_map.get(name, 0)
        if cur_avg > 0 and prev_avg > 0:
            diff = round(cur_avg - prev_avg, 1)
            if diff > 0:
                improvements.append({
                    "name": name,
                    "current_avg": cur_avg,
                    "previous_avg": prev_avg,
                    "improvement": diff,
                })

    improvements.sort(key=lambda x: x["improvement"], reverse=True)
    top_improvers = improvements[:5]

    return {
        "week_start": str(current_monday),
        "week_end": str(current_sunday),
        "not_submitted": not_submitted,
        "low_scorers": low_scorers,
        "top_improvers": top_improvers,
        "total_persons": len(persons),
        "submitted_count": len(submitted_names),
    }
