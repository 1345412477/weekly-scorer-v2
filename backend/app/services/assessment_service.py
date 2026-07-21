"""内部考核服务层 - 提供考核数据查询和项目贡献分析"""
import re
from datetime import date
from typing import List, Dict, Optional
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import WeeklyAggregate, WeeklyReport, Person


async def get_assessment_list(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    department: Optional[str] = None,
    page: int = 1,
    size: int = 20
) -> Dict:
    """
    获取考核列表 - 统计指定时间范围内每个员工的平均分和提交情况
    
    Args:
        db: 数据库会话
        start_date: 开始日期
        end_date: 结束日期
        department: 部门筛选（可选）
        page: 页码
        size: 每页数量
    
    Returns:
        包含 items、total、page、size 的字典
    """
    # 计算时间范围内的总周数
    total_weeks = (end_date - start_date).days // 7 + 1
    
    # 构建查询条件
    conditions = [
        WeeklyAggregate.week_start >= start_date,
        WeeklyAggregate.week_start <= end_date
    ]
    
    if department:
        conditions.append(WeeklyAggregate.department == department)
    
    # 按员工分组统计
    query = (
        select(
            WeeklyAggregate.person_id,
            WeeklyAggregate.author_name,
            WeeklyAggregate.department,
            func.count(WeeklyAggregate.id).label('submitted_weeks'),
            func.avg(WeeklyAggregate.composite_score).label('avg_composite_score')
        )
        .where(and_(*conditions))
        .group_by(
            WeeklyAggregate.person_id,
            WeeklyAggregate.author_name,
            WeeklyAggregate.department
        )
        .order_by(func.avg(WeeklyAggregate.composite_score).desc())
    )
    
    # 分页
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)
    
    result = await db.execute(query)
    rows = result.all()
    
    items = []
    for row in rows:
        submitted_weeks = row.submitted_weeks
        submission_rate = (submitted_weeks / total_weeks * 100) if total_weeks > 0 else 0
        
        items.append({
            'person_id': row.person_id,
            'author_name': row.author_name,
            'department': row.department,
            'avg_composite_score': round(float(row.avg_composite_score), 1) if row.avg_composite_score else 0,
            'total_weeks': total_weeks,
            'submitted_weeks': submitted_weeks,
            'submission_rate': round(submission_rate, 1)
        })
    
    # 统计总数
    count_query = (
        select(func.count(func.distinct(WeeklyAggregate.person_id)))
        .where(and_(*conditions))
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    return {
        'items': items,
        'total': total,
        'page': page,
        'size': size
    }


async def get_assessment_detail(
    db: AsyncSession,
    person_id: str,
    start_date: date,
    end_date: date
) -> Dict:
    """
    获取个人考核详情 - 包含各项平均分、每周分数、项目贡献
    
    Args:
        db: 数据库会话
        person_id: 员工ID
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        包含 person、summary、weekly_scores、projects 的字典
    """
    # 获取员工信息
    person_query = select(Person).where(Person.id == person_id)
    person_result = await db.execute(person_query)
    person = person_result.scalar_one_or_none()
    
    if not person:
        return None
    
    # 查询该时间段的所有周评记录
    agg_query = (
        select(WeeklyAggregate)
        .where(
            and_(
                WeeklyAggregate.person_id == person_id,
                WeeklyAggregate.week_start >= start_date,
                WeeklyAggregate.week_start <= end_date
            )
        )
        .order_by(WeeklyAggregate.week_start.asc())
    )
    agg_result = await db.execute(agg_query)
    aggregates = agg_result.scalars().all()
    
    if not aggregates:
        return None
    
    # 计算各项平均分
    total_weeks = (end_date - start_date).days // 7 + 1
    submitted_weeks = len(aggregates)
    
    avg_composite = sum(float(a.composite_score or 0) for a in aggregates) / submitted_weeks
    avg_report = sum(float(a.report_score or 0) for a in aggregates) / submitted_weeks
    avg_attendance = sum(float(a.attendance_score or 0) for a in aggregates) / submitted_weeks
    avg_chat = sum(float(a.chat_score or 0) for a in aggregates) / submitted_weeks
    
    # 构建每周分数列表
    weekly_scores = []
    for agg in aggregates:
        weekly_scores.append({
            'week_start': agg.week_start.isoformat(),
            'composite_score': float(agg.composite_score or 0),
            'report_score': float(agg.report_score or 0),
            'attendance_score': float(agg.attendance_score or 0),
            'chat_score': float(agg.chat_score or 0)
        })
    
    # 分析项目贡献
    projects = await analyze_project_contribution(db, person_id, start_date, end_date)
    
    return {
        'person': {
            'person_id': person.id,
            'author_name': person.name,
            'department': person.department_name
        },
        'summary': {
            'avg_composite_score': round(avg_composite, 1),
            'avg_report_score': round(avg_report, 1),
            'avg_attendance_score': round(avg_attendance, 1),
            'avg_chat_score': round(avg_chat, 1),
            'total_weeks': total_weeks,
            'submitted_weeks': submitted_weeks
        },
        'weekly_scores': weekly_scores,
        'projects': projects
    }


async def analyze_project_contribution(
    db: AsyncSession,
    person_id: str,
    start_date: date,
    end_date: date
) -> List[Dict]:
    """
    分析个人在项目上的贡献情况
    
    Args:
        db: 数据库会话
        person_id: 员工ID
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        项目列表，每个项目包含名称、参与周数、参与率、工作条目数
    """
    # 查询该时间段的所有周报记录
    report_query = (
        select(WeeklyReport)
        .where(
            and_(
                WeeklyReport.person_id == person_id,
                WeeklyReport.week_start >= start_date,
                WeeklyReport.week_start <= end_date
            )
        )
        .order_by(WeeklyReport.week_start.asc())
    )
    report_result = await db.execute(report_query)
    reports = report_result.scalars().all()
    
    if not reports:
        return []
    
    # 统计总周数（用于计算参与率）
    total_weeks = len(reports)
    
    # 解析每个周报的内容，提取项目信息
    project_stats = defaultdict(lambda: {'weeks': set(), 'work_items': 0})
    
    for report in reports:
        if not report.content:
            continue
        
        # 提取项目名称
        projects = extract_projects_from_content(report.content)
        
        for project_name in projects:
            project_stats[project_name]['weeks'].add(report.week_start)
            project_stats[project_name]['work_items'] += 1
    
    # 构建项目列表
    projects_list = []
    for project_name, stats in project_stats.items():
        participation_weeks = len(stats['weeks'])
        participation_rate = (participation_weeks / total_weeks * 100) if total_weeks > 0 else 0
        
        projects_list.append({
            'project_name': project_name,
            'participation_weeks': participation_weeks,
            'participation_rate': round(participation_rate, 1),
            'work_items_count': stats['work_items']
        })
    
    # 按参与周数降序排序
    projects_list.sort(key=lambda x: x['participation_weeks'], reverse=True)
    
    return projects_list


def extract_projects_from_content(content: str) -> List[str]:
    """
    从周报内容中提取项目名称
    
    周报内容格式：
    ## 上周工作内容
    ### 1. 项目名称
    - 工作内容：xxx
    
    Args:
        content: 周报内容文本
    
    Returns:
        项目名称列表
    """
    # 匹配 "### 1. 项目名称" 或 "### 项目名称"
    pattern = r'###\s*\d*\.?\s*(.+?)(?=\n|$)'
    matches = re.findall(pattern, content)
    
    # 清理项目名称
    projects = []
    for match in matches:
        project = match.strip()
        # 过滤掉空名称和明显的非项目名称
        if project and len(project) > 1 and not project.startswith('##'):
            projects.append(project)
    
    return projects
