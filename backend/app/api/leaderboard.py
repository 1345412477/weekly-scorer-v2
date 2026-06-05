"""排行榜 API"""
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text

from app.database import get_db
from app.models.models import WeeklyReport, ReportScore

router = APIRouter(prefix="/api/v1/leaderboard", tags=["排行榜"])


def get_current_week():
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def get_current_month():
    today = date.today()
    first = today.replace(day=1)
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return first, last


@router.get("")
async def get_leaderboard(
    period: str = Query("week", regex="^(week|month|all)$"),
    department: Optional[str] = None,
    sort_by: str = Query("total_score", regex="^(total_score|avg_score|report_count)$"),
    db: AsyncSession = Depends(get_db),
):
    """获取排行榜数据"""
    # 构建时间过滤
    period_filter = ""
    params = {}
    if period == "week":
        monday, sunday = get_current_week()
        period_filter = "AND r.week_start >= :start AND r.week_end <= :end"
        params["start"] = monday.isoformat()
        params["end"] = sunday.isoformat()
    elif period == "month":
        first, last = get_current_month()
        period_filter = "AND r.week_start >= :start AND r.week_end <= :end"
        params["start"] = first.isoformat()
        params["end"] = last.isoformat()

    dept_filter = ""
    if department and department != "all":
        dept_filter = "AND r.department = :dept"
        params["dept"] = department

    sort_field = {
        "total_score": "total_score",
        "avg_score": "avg_score",
        "report_count": "report_count",
    }.get(sort_by, "total_score")

    sql = text(f"""
        SELECT 
            r.author_name,
            r.department,
            COALESCE(SUM(s.total_score), 0) as total_score,
            COALESCE(AVG(s.total_score), 0) as avg_score,
            COUNT(r.id) as report_count,
            MAX(s.grade) as latest_grade
        FROM weekly_reports r
        LEFT JOIN report_scores s ON s.report_id = r.id
        WHERE r.status IN ('scored', 'submitted') {period_filter} {dept_filter}
        GROUP BY r.author_name, r.department
        ORDER BY {sort_field} DESC
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    rankings = []
    for idx, row in enumerate(rows):
        rankings.append({
            "rank": idx + 1,
            "author_name": row[0],
            "department": row[1] or "",
            "total_score": round(float(row[2]), 1),
            "avg_score": round(float(row[3]), 1),
            "report_count": int(row[4]),
            "latest_grade": row[5] or "",
        })

    # 统计总报告数
    count_sql = text(f"""
        SELECT COUNT(*) FROM weekly_reports r
        WHERE r.status IN ('scored', 'submitted') {period_filter} {dept_filter}
    """)
    count_r = await db.execute(count_sql, params)
    total_reports = count_r.scalar() or 0

    return {
        "rankings": rankings,
        "period": period,
        "total_reports": total_reports,
    }


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取总览统计数据"""
    # 总报告数
    total_r = await db.execute(
        select(func.count()).select_from(WeeklyReport)
        .where(WeeklyReport.status.in_(["scored", "submitted"]))
    )
    total_reports = total_r.scalar() or 0

    # 已评分数
    scored_r = await db.execute(
        select(func.count()).select_from(WeeklyReport)
        .where(WeeklyReport.status == "scored")
    )
    scored_reports = scored_r.scalar() or 0

    # 平均分
    avg_r = await db.execute(
        select(func.avg(ReportScore.total_score))
    )
    avg_score = round(float(avg_r.scalar() or 0), 1)

    # 等级分布
    grade_r = await db.execute(
        select(ReportScore.grade, func.count())
        .group_by(ReportScore.grade)
    )
    grade_distribution = {row[0]: row[1] for row in grade_r.fetchall() if row[0]}

    # 最近 12 周趋势
    trend_sql = text("""
        SELECT r.week_start, r.week_end, AVG(s.total_score) as avg_score
        FROM weekly_reports r
        JOIN report_scores s ON s.report_id = r.id
        WHERE r.status = 'scored'
        GROUP BY r.week_start, r.week_end
        ORDER BY r.week_start DESC
        LIMIT 12
    """)
    trend_r = await db.execute(trend_sql)
    trend = [
        {
            "week_start": str(row[0]),
            "week_end": str(row[1]),
            "avg_score": round(float(row[2]), 1),
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
