"""业务盘 AI 总结服务"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta
from typing import Optional
import json
import re
import uuid

from app.models.models import (
    DepartmentSummary, Department, WeeklyReport, Person, ScoringConfig
)
from app.utils.logger import log_info, log_error, log_warning
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
                {"role": "system", "content": "你是一个专业的业务分析助手，请严格输出 JSON 格式。"},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.SCORING_TEMPERATURE,
            max_tokens=4000,  # 增加 token 上限防止截断
        )
        raw_text = _safe_get_content(response)
        log_info(f"[业务盘] AI 原始响应 (前500字符): {raw_text[:500]}")

        # 解析 JSON 响应
        result = parse_ai_summary(raw_text)
        log_info(f"[业务盘] 解析结果: last_week={len(result.get('last_week_summary', []))}条, this_week={len(result.get('this_week_summary', []))}条")
        return result
    except AIScoringError:
        raise
    except Exception as e:
        import traceback
        log_error(f"AI 总结调用失败: {type(e).__name__}: {e}")
        log_error(f"完整堆栈: {traceback.format_exc()}")
        raise


def _repair_truncated_json(text: str) -> str:
    """尝试修复被截断的 JSON（AI 输出 token 超限常见）。
    策略：
    1. 补全缺失的闭合括号
    2. 如果仍失败，逐步回退到最后一个完整的 key-value 对
    """
    # 第一步：补全缺失的闭合括号
    stack = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            stack.append(ch)
        elif ch == '}':
            if stack and stack[-1] == '{':
                stack.pop()
        elif ch == ']':
            if stack and stack[-1] == '[':
                stack.pop()
    close_map = {'{': '}', '[': ']'}
    for bracket in reversed(stack):
        text += close_map[bracket]

    # 第二步：如果仍无法解析，逐步截断到最后一个完整结构
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # 找到最后一个完整的 "key": value 对的位置
    # 策略：从后往前找最后一个 }, 或 ], 或 "value" 的结束位置
    for cut_pos in range(len(text) - 1, 0, -1):
        candidate = text[:cut_pos].rstrip().rstrip(',').rstrip()
        # 补全括号
        s2 = []
        in_s = False
        esc = False
        for ch in candidate:
            if esc:
                esc = False
                continue
            if ch == '\\':
                esc = True
                continue
            if ch == '"':
                in_s = not in_s
                continue
            if in_s:
                continue
            if ch in ('{', '['):
                s2.append(ch)
            elif ch == '}':
                if s2 and s2[-1] == '{':
                    s2.pop()
            elif ch == ']':
                if s2 and s2[-1] == '[':
                    s2.pop()
        for bracket in reversed(s2):
            candidate += close_map[bracket]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    return text


def parse_ai_summary(raw_text: str) -> dict:
    """解析 AI 返回的 JSON 总结，兼容截断/格式不完整的输出"""
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

    # 提取 { ... } 范围
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]

    # 解析 JSON，失败则尝试修复截断
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            repaired = _repair_truncated_json(text)
            data = json.loads(repaired)
        except json.JSONDecodeError:
            # 使用 regex 提取 last_week_summary 和 this_week_summary 数组
            log_warning(f"JSON 解析失败，尝试 regex 提取: {raw_text[:100]}")
            data = _extract_summary_by_regex(raw_text)
        except Exception as e2:
            log_warning(f"JSON 修复失败 ({type(e2).__name__}): {e2}")
            data = _extract_summary_by_regex(raw_text)
    except Exception as e:
        # 兜底：任何异常都返回空结果
        log_warning(f"JSON 解析异常 ({type(e).__name__}): {e}")
        data = {"last_week_summary": [], "this_week_summary": []}

    # 标准化输出格式
    result = {
        "last_week_summary": [],
        "this_week_summary": [],
    }

    if data and isinstance(data, dict):
        # 规范化 key：AI 可能返回带空白/引号的 key（如 '\n  "last_week_summary"'）
        normalized = {}
        for dk, dv in data.items():
            clean_key = re.sub(r'[\s"\']+', '', str(dk))
            normalized[clean_key] = dv

        for key in ["last_week_summary", "this_week_summary"]:
            items = normalized.get(key, [])
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


def _extract_summary_by_regex(text: str) -> dict:
    """使用 regex 从 AI 响应中提取 last_week_summary 和 this_week_summary 数组"""
    result = {"last_week_summary": [], "this_week_summary": []}

    for key in ["last_week_summary", "this_week_summary"]:
        # 匹配 "last_week_summary": [...] 或 "last_week_summary" : [...]
        pattern = rf'"{re.escape(key)}"\s*:\s*\[(.*?)\](?:\s*,|\s*\}})'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            array_text = match.group(1).strip()
            if array_text:
                # 尝试解析数组中的每个对象
                items = re.findall(r'\{[^}]*\}', array_text)
                for item_text in items:
                    try:
                        item = json.loads(item_text)
                        content = item.get("content", "")
                        persons = item.get("persons", [])
                        if content:
                            result[key].append({
                                "content": content,
                                "highlight": False,
                                "persons": persons if isinstance(persons, list) else [],
                            })
                    except json.JSONDecodeError:
                        continue

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

        # 更新总结记录（即使 AI 返回空结果也标记为 done）
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
    except (ValueError, KeyError, TypeError) as e:
        # JSON 解析失败或数据结构异常：记录空结果，标记为 done（不阻塞其他部门）
        log_warning(f"部门总结数据异常，使用空结果: {department_name} - {type(e).__name__}: {e}")
        summary.last_week_summary = []
        summary.this_week_summary = []
        summary.status = "done"
        summary.error_message = None
        summary.generated_at = bj_now()
        await db.commit()

        return {
            "success": True,
            "department_id": department_id,
            "department_name": department_name,
            "status": "done",
        }
    except Exception as e:
        log_error(f"部门总结生成失败: {department_name} - {type(e).__name__}: {e}")
        import traceback
        log_error(f"完整堆栈: {traceback.format_exc()}")
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
