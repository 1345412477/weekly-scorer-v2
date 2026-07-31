"""排行榜 API"""
from datetime import date, timedelta, datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.models import WeeklyReport, ReportScore, Person, WeeklyAggregate, ScoringConfig, DepartmentSummary
from app.utils.time_utils import bj_today, bj_now

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
    """获取 Dashboard 聚合数据：异常人员（未提交+迟交）/ 公司项目 / 历史项目"""
    # 本周（用于"本周项目任务"）
    this_monday, this_sunday = get_current_week()
    # 上周（用于异常人员、已提交统计）
    last_monday, last_sunday = get_previous_week(this_monday, this_sunday)
    now = bj_now()

    # 读取提交期限配置
    config_result = await db.execute(
        select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1)
    )
    config = config_result.scalar_one_or_none()
    submission_deadline_hours = getattr(config, "submission_deadline_hours", 168) or 168
    late_deadline_hours = getattr(config, "late_deadline_hours", 336) or 336

    # 计算截止时间点（基于上周）
    deadline_time = datetime(last_monday.year, last_monday.month, last_monday.day) + timedelta(hours=submission_deadline_hours)
    late_deadline_time = datetime(last_monday.year, last_monday.month, last_monday.day) + timedelta(hours=late_deadline_hours)

    # 1. 上周已提交人员（含提交时间）
    submitted_q = (
        select(WeeklyReport.author_name, WeeklyReport.submit_time)
        .select_from(WeeklyReport)
        .where(WeeklyReport.status.in_(["scored", "submitted"]))
        .where(WeeklyReport.week_start >= last_monday)
        .where(WeeklyReport.week_end <= last_sunday)
    )
    submitted_r = await db.execute(submitted_q)
    submitted_rows = submitted_r.fetchall()
    submitted_names = {row[0] for row in submitted_rows}
    # 记录每人的最早提交时间
    submit_times = {}
    for row in submitted_rows:
        if row[0] not in submit_times or (row[1] and row[1] < submit_times[row[0]]):
            submit_times[row[0]] = row[1]

    # 2. 获取所有在职人员
    persons_q = select(Person).where(Person.is_active == True)
    persons_r = await db.execute(persons_q)
    persons = persons_r.scalars().all()

    not_submitted = []  # 过了补交期限仍未提交
    late_submitted = []  # 过了迟交期限但提交了（迟交）

    for p in persons:
        if p.name not in submitted_names:
            # 未提交：始终计入异常列表
            not_submitted.append({
                "name": p.name,
                "department": p.department_name or "",
                "position": p.position or "",
                "status": "未提交",
            })
        else:
            # 已提交：判断是否迟交
            st = submit_times.get(p.name)
            if st and st >= deadline_time:
                late_submitted.append({
                    "name": p.name,
                    "department": p.department_name or "",
                    "position": p.position or "",
                    "status": "迟交",
                })

    # 合并异常人员：未提交在前，迟交在后
    abnormal_persons = not_submitted + late_submitted

    # 已提交人员列表（含正常+迟交）
    submitted_persons = []
    for p in persons:
        if p.name in submitted_names:
            submitted_persons.append({
                "name": p.name,
                "department_name": p.department_name or "",
                "position": p.position or "",
            })

    # 3. 本周项目任务（本周各部门 this_week_projects 汇总去重）
    dept_summaries_q = (
        select(DepartmentSummary)
        .where(DepartmentSummary.week_start >= this_monday)
        .where(DepartmentSummary.week_end <= this_sunday)
        .where(DepartmentSummary.status == "done")
    )
    dept_r = await db.execute(dept_summaries_q)
    dept_summaries = dept_r.scalars().all()

    # 汇总所有部门的项目，按项目名去重合并
    project_map = {}
    for ds in dept_summaries:
        projects = ds.this_week_projects or []
        for proj in projects:
            pname = proj.get("name", "")
            if not pname:
                continue
            if pname not in project_map:
                project_map[pname] = {
                    "name": pname,
                    "progress": proj.get("progress", 0),
                    "highlight": proj.get("highlight", False),
                    "summary": proj.get("summary", ""),
                    "persons": list(proj.get("persons", [])),
                    "departments": set(),
                }
            else:
                # 合并参与人员（去重）
                existing = set(project_map[pname]["persons"])
                for pn in proj.get("persons", []):
                    if pn not in existing:
                        project_map[pname]["persons"].append(pn)
                        existing.add(pn)
                # 取最高进度
                project_map[pname]["progress"] = max(project_map[pname]["progress"], proj.get("progress", 0))
                # 任一部门标记重点则为重点
                if proj.get("highlight"):
                    project_map[pname]["highlight"] = True
            project_map[pname]["departments"].add(ds.department_name)

    current_projects = []
    for pname, pdata in project_map.items():
        current_projects.append({
            "name": pdata["name"],
            "progress": pdata["progress"],
            "highlight": pdata["highlight"],
            "summary": pdata["summary"],
            "persons": pdata["persons"],
            "departments": list(pdata["departments"]),
        })
    # 重点项目排前，其次按进度降序
    current_projects.sort(key=lambda x: (not x["highlight"], -x["progress"]))

    # 4. 历史项目（过去 4 周的项目，按周分组，从上周开始往前推）
    history_weeks = []
    for week_offset in range(0, 4):
        w_monday = last_monday - timedelta(days=7 * week_offset)
        w_sunday = w_monday + timedelta(days=6)
        week_label = f"{w_monday.month}/{w_monday.day} - {w_sunday.month}/{w_sunday.day}"

        h_dept_q = (
            select(DepartmentSummary)
            .where(DepartmentSummary.week_start >= w_monday)
            .where(DepartmentSummary.week_end <= w_sunday)
            .where(DepartmentSummary.status == "done")
        )
        h_dept_r = await db.execute(h_dept_q)
        h_depts = h_dept_r.scalars().all()

        h_projects = []
        h_project_map = {}
        for ds in h_depts:
            projects = ds.this_week_projects or []
            for proj in projects:
                pname = proj.get("name", "")
                if not pname:
                    continue
                if pname not in h_project_map:
                    h_project_map[pname] = {
                        "name": pname,
                        "progress": proj.get("progress", 0),
                        "highlight": proj.get("highlight", False),
                        "summary": proj.get("summary", ""),
                        "persons": list(proj.get("persons", [])),
                    }
                else:
                    existing = set(h_project_map[pname]["persons"])
                    for pn in proj.get("persons", []):
                        if pn not in existing:
                            h_project_map[pname]["persons"].append(pn)
                            existing.add(pn)
                    h_project_map[pname]["progress"] = max(h_project_map[pname]["progress"], proj.get("progress", 0))
                    if proj.get("highlight"):
                        h_project_map[pname]["highlight"] = True

        for pname, pdata in h_project_map.items():
            h_projects.append(pdata)
        h_projects.sort(key=lambda x: (not x["highlight"], -x["progress"]))

        if h_projects:
            history_weeks.append({
                "week_label": week_label,
                "week_start": str(w_monday),
                "projects": h_projects,
            })

    # 返回完整人员列表（用于前端弹窗展示）
    all_persons_list = [
        {
            "name": p.name,
            "department_name": p.department_name or "",
            "position": p.position or "",
        }
        for p in persons
    ]

    return {
        "week_start": str(this_monday),
        "week_end": str(this_sunday),
        "abnormal_persons": abnormal_persons,
        "not_submitted_count": len(not_submitted),
        "late_submitted_count": len(late_submitted),
        "current_projects": current_projects,
        "history_weeks": history_weeks,
        "total_persons": len(persons),
        "submitted_count": len(submitted_names),
        "submitted_persons": submitted_persons,
        "all_persons": all_persons_list,
    }
