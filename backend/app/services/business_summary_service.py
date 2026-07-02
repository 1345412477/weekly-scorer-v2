"""业务盘 AI 总结服务"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta
from typing import Optional
import json
import uuid

from app.models.models import (
    DepartmentSummary, Department, WeeklyReport, Person, ScoringConfig
)
from app.utils.logger import log_info, log_error
from app.utils.time_utils import bj_now


# 默认业务盘总结提示词
DEFAULT_BUSINESS_SUMMARY_PROMPT = """你是一个专业的业务分析助手，负责根据员工的周报内容，为部门生成工作事项总结。

## 任务要求

请根据提供的部门信息和员工周报内容，总结该部门在指定周期内的工作事项。

## 输出格式

请严格按照以下 JSON 格式输出，不要包含其他内容：

```json
{
  "last_week_summary": [
    {
      "content": "工作事项描述",
      "persons": ["负责人1", "负责人2"]
    }
  ],
  "this_week_summary": [
    {
      "content": "工作事项描述",
      "persons": ["负责人1", "负责人2"]
    }
  ]
}
```

## 总结规则

1. **上周工作回顾**：从周报的"本周工作"部分提取已完成的工作事项
2. **本周工作重点**：从周报的"下周计划"部分提取计划中的工作事项
3. 每个部门总结 3-5 条核心事项
4. 每条事项要具体明确，避免空泛描述
5. 识别跨成员的共同项目/事项进行合并
6. 标注每条事项的主要负责人（可多人）
7. 如果某个周期没有相关周报内容，返回空数组

## 部门信息

- 部门名称：{department}
- 统计周期：{week_label}

## 员工周报内容

{reports}

请输出 JSON 格式的总结："""


def _get_week_range(target_date: Optional[date] = None) -> tuple[date, date]:
    """获取指定日期所在周的周一和周日"""
    if target_date is None:
        target_date = date.today()
    weekday = target_date.weekday()
    week_start = target_date - timedelta(days=weekday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _get_previous_week(week_start: date) -> tuple[date, date]:
    """获取上一周的日期范围"""
    prev_start = week_start - timedelta(days=7)
    prev_end = prev_start + timedelta(days=6)
    return prev_start, prev_end


async def collect_department_reports(
    db: AsyncSession,
    department_id: str,
    week_start: date,
    week_end: date,
) -> list[dict]:
    """收集部门在指定周期内的周报数据"""
    # 查询该部门所有员工的周报
    result = await db.execute(
        select(WeeklyReport).where(
            WeeklyReport.department_id == department_id,
            WeeklyReport.week_start >= week_start,
            WeeklyReport.week_start <= week_end,
            WeeklyReport.status == "scored",
        ).order_by(WeeklyReport.author_name)
    )
    reports = result.scalars().all()
    
    return [
        {
            "author_name": r.author_name,
            "week_start": r.week_start.isoformat(),
            "content": r.content,
        }
        for r in reports
    ]


async def get_business_summary_prompt(db: AsyncSession) -> str:
    """获取业务盘总结提示词"""
    result = await db.execute(select(ScoringConfig).limit(1))
    config = result.scalar_one_or_none()
    if config and config.business_summary_prompt:
        return config.business_summary_prompt
    return DEFAULT_BUSINESS_SUMMARY_PROMPT


async def call_ai_summary(
    db: AsyncSession,
    department_name: str,
    reports: list[dict],
    week_label: str,
) -> dict:
    """调用 AI 进行总结"""
    # 构建周报内容汇总
    if not reports:
        return {"last_week_summary": [], "this_week_summary": []}
    
    reports_text = ""
    for r in reports:
        reports_text += f"\n### {r['author_name']}（{r['week_start']}）\n{r['content']}\n"
    
    # 获取提示词
    prompt_template = await get_business_summary_prompt(db)
    prompt = prompt_template.format(
        department=department_name,
        week_label=week_label,
        reports=reports_text,
    )
    
    # 调用 AI
    try:
        from app.services.ai_scorer import get_client, _safe_get_content, AIScoringError, _get_scoring_config
        from app.config import get_settings
        settings = get_settings()
        
        model_id, db_model = await _get_scoring_config(db)
        client = get_client(
            api_key=db_model["api_key"] if db_model else None,
            base_url=db_model["base_url"] if db_model else None,
        )
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是一个专业的业务分析助手。"},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.SCORING_TEMPERATURE,
            max_tokens=2000,
        )
        raw_text = _safe_get_content(response)
        
        # 解析 JSON 响应
        result = parse_ai_summary(raw_text)
        return result
    except AIScoringError:
        raise
    except Exception as e:
        log_error(f"AI 总结调用失败: {e}")
        raise


def parse_ai_summary(raw_text: str) -> dict:
    """解析 AI 返回的 JSON 总结"""
    # 提取 JSON 部分
    text = raw_text.strip()
    
    # 尝试提取 ```json ... ``` 中的内容
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    
    # 解析 JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # 尝试找到第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end+1]
            data = json.loads(text)
        else:
            raise ValueError(f"无法解析 AI 返回的 JSON: {raw_text[:200]}")
    
    # 标准化输出格式
    result = {
        "last_week_summary": [],
        "this_week_summary": [],
    }
    
    for key in ["last_week_summary", "this_week_summary"]:
        items = data.get(key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    content = item.get("content", "")
                    persons = item.get("persons", [])
                    if content:
                        result[key].append({
                            "content": content,
                            "highlight": False,
                            "persons": persons if isinstance(persons, list) else [],
                        })
    
    return result


async def generate_department_summary(
    db: AsyncSession,
    department_id: str,
    department_name: str,
    week_start: date,
    week_end: date,
) -> dict:
    """生成单个部门的总结"""
    log_info(f"开始生成部门总结: {department_name} ({week_start})")
    
    # 查找或创建总结记录
    result = await db.execute(
        select(DepartmentSummary).where(
            DepartmentSummary.department_id == department_id,
            DepartmentSummary.week_start == week_start,
        )
    )
    summary = result.scalar_one_or_none()
    
    if not summary:
        summary = DepartmentSummary(
            id=str(uuid.uuid4()),
            department_id=department_id,
            department_name=department_name,
            week_start=week_start,
            week_end=week_end,
            status="generating",
        )
        db.add(summary)
    else:
        summary.status = "generating"
        summary.error_message = None
    
    await db.flush()
    
    try:
        # 收集本周周报
        this_week_reports = await collect_department_reports(
            db, department_id, week_start, week_end
        )
        
        # 收集上周周报
        prev_start, prev_end = _get_previous_week(week_start)
        last_week_reports = await collect_department_reports(
            db, department_id, prev_start, prev_end
        )
        
        # 生成周标签
        week_label = f"{week_start.strftime('%Y年%m月%d日')} - {week_end.strftime('%m月%d日')}"
        
        # 调用 AI 总结
        ai_result = await call_ai_summary(
            db, department_name, this_week_reports + last_week_reports, week_label
        )
        
        # 更新总结记录
        summary.last_week_summary = ai_result.get("last_week_summary", [])
        summary.this_week_summary = ai_result.get("this_week_summary", [])
        summary.status = "done"
        summary.generated_at = bj_now()
        
        await db.commit()
        
        log_info(f"部门总结生成完成: {department_name} ({week_start})")
        
        return {
            "success": True,
            "department_id": department_id,
            "department_name": department_name,
            "status": "done",
        }
    except Exception as e:
        log_error(f"部门总结生成失败: {department_name} - {e}")
        summary.status = "failed"
        summary.error_message = str(e)
        await db.commit()
        
        return {
            "success": False,
            "department_id": department_id,
            "department_name": department_name,
            "status": "failed",
            "error": str(e),
        }


async def generate_all_department_summaries(
    db: AsyncSession,
    week_start: date,
    week_end: date,
) -> list[dict]:
    """生成所有部门的总结"""
    # 查询所有部门
    result = await db.execute(
        select(Department).order_by(Department.name)
    )
    departments = result.scalars().all()
    
    results = []
    for dept in departments:
        result = await generate_department_summary(
            db, dept.id, dept.name, week_start, week_end
        )
        results.append(result)
    
    return results
