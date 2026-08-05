"""业务盘 AI 总结服务"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta
from typing import Optional
import asyncio
import json
import re
import uuid

from app.models.models import (
    DepartmentSummary, Department, WeeklyReport, Person, ScoringConfig
)
from app.utils.logger import log_info, log_error, log_warning
from app.utils.time_utils import bj_now, bj_today

# 全局锁，防止并发生成
_generation_lock = asyncio.Lock()


# 默认业务盘总结提示词
DEFAULT_BUSINESS_SUMMARY_PROMPT = """你是一位资深的项目管理分析师，擅长从周报中提炼项目全景、归并子任务、识别重点项目并评估进度。

## 任务目标

根据部门员工提交的周报内容，按**项目维度**进行高度归并，将零散的子任务/功能点/工作项聚类为完整的项目，区分**上周已完成**与**本周进行中**的项目。

## 核心原则：先归并，再输出

周报中的 `### N. xxx` 标题通常是**子任务或功能模块**，不是项目名。你必须将这些子任务归并到所属项目下。

### 归并规则（必须严格遵守）

1. **同一系统的子模块 → 归并为一个项目**
   - 例：「AI评分引擎」「系统监控」「安全加固」「性能优化」→ 归并为「考勤评分系统」
   - 例：「赢筑小程序」「消息推送」「性能优化」「单元测试」→ 归并为「赢筑小程序」
   - 例：「前端开发」「代码优化」「Bug修复」→ 归并为所属项目名（如「考勤评分系统」或「赢筑小程序」）

2. **同一客户/产品的不同工作 → 归并为一个项目**
   - 例：「YY客户上线实施」「YY客户操作培训」「客户响应机制建设」→ 归并为「YY客户上线项目」
   - 例：「XX客户运维支持」→ 归并为「XX客户运维项目」

3. **同一产品生命周期的工作 → 归并为一个项目**
   - 例：「产品规划」「用户调研」「原型设计」「需求文档」→ 归并为「产品规划与调研」

4. **通用/杂项工作 → 归并为「基础建设与优化」**
   - 例：「文档整理」「学习培训」「技术文档」「代码评审」→ 归并为「基础建设与优化」
   - 这类工作通常不涉及具体项目交付，作为兜底分类

5. **跨人员协作 → 必须合并为一条**
   - 不同员工参与同一项目的不同模块，必须合并为一条项目记录，persons 列出所有参与者

### 归并示例

假设研发部有以下周报内容：
- 员工A：### 1. AI评分引擎 / ### 2. 系统监控 / ### 3. 安全加固
- 员工B：### 1. 考勤评分系统 / ### 2. 业务盘功能 / ### 3. 技术文档
- 员工C：### 1. 前端开发 / ### 2. 代码优化 / ### 3. Bug修复

正确归并结果（2个项目）：
- 「考勤评分系统」：包含AI评分引擎、系统监控、安全加固、业务盘功能、前端开发、代码优化、Bug修复（A+B+C参与）
- 「基础建设与优化」：包含技术文档（B参与）

错误做法（7个独立项目）：
- AI评分引擎、系统监控、安全加固、考勤评分系统、业务盘功能、前端开发、代码优化... ← 这是把子任务当项目

## 输出格式

请严格按照以下 JSON 格式输出，不要包含其他内容：

```json
{
  "last_week_projects": [
    {
      "name": "项目名称",
      "progress": 100,
      "highlight": true,
      "summary": "精炼描述",
      "persons": ["张三", "李四"]
    }
  ],
  "this_week_projects": [
    {
      "name": "项目名称",
      "progress": 60,
      "highlight": false,
      "summary": "精炼描述",
      "persons": ["张三"]
    }
  ]
}
```

## 字段定义

| 字段 | 说明 |
|------|------|
| **name** | 归并后的项目名称（不超过15字）。不是子任务名，是所属的系统/产品/客户项目名 |
| **progress** | 进度百分比（0-100）。评估标准：已完成/已上线/已交付=100；联调/测试中=70-90；开发中=40-70；设计/调研中=10-30；未启动=0 |
| **highlight** | 是否重点项目（true/false）。满足任一条件即为重点：①跨人员协作（≥2人）②核心业务/营收相关系统 ③涉及架构升级或技术攻坚 ④有明确里程碑交付 |
| **summary** | 精炼描述（30-80字），必须包含：①做了什么 ②关键成果/数据 ③当前状态。避免空泛描述 |
| **persons** | 参与该项目的所有人员姓名（去重） |

## 输出约束

1. 每个周期的项目数量控制在 **2-5个**，超过说明归并不够
2. 禁止将子任务/功能模块作为独立项目输出
3. 通用/杂项工作统一归入「基础建设与优化」
4. 若某周期无有效项目信息，对应数组返回空数组 `[]`

## 上下文信息

- 部门名称：{department}
- 统计周期：{week_label}

## 员工周报内容

{reports}

请输出 JSON 格式的项目总结（先归并，再输出）："""


def _get_week_range(target_date: Optional[date] = None) -> tuple[date, date]:
    """获取指定日期所在周的周一和周日"""
    if target_date is None:
        target_date = bj_today()
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
    log_info(f"[业务盘] 收集周报: 部门ID={department_id[:8]}..., 周期={week_start}~{week_end}")
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
    log_info(f"[业务盘] 找到 {len(reports)} 份周报")
    
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

    # 获取提示词（用 replace 而非 format，避免 JSON 花括号冲突）
    prompt_template = await get_business_summary_prompt(db)
    prompt = (prompt_template
              .replace("{department}", department_name)
              .replace("{week_label}", week_label)
              .replace("{reports}", reports_text))

    # 调用 AI
    try:
        from app.services.ai_scorer import get_client, _safe_get_content, AIScoringError, _get_scoring_config
        from app.config import get_settings
        import httpx
        settings = get_settings()

        model_id, db_model = await _get_scoring_config(db)
        # 业务盘需要更长超时时间（300秒），因为数据量大
        timeout = httpx.Timeout(connect=10, read=300, write=30, pool=5)
        client = get_client(
            api_key=db_model["api_key"] if db_model else None,
            base_url=db_model["base_url"] if db_model else None,
        )
        # 覆盖 client 的超时设置
        client.timeout = timeout
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "你是一个专业的业务分析助手，请严格输出 JSON 格式。"},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.SCORING_TEMPERATURE,
            max_tokens=4000,
            timeout=timeout,
        )
        raw_text = _safe_get_content(response)
        log_info(f"[业务盘] AI 原始响应 (前2000字符): {raw_text[:2000]}")

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
        data = {"last_week_summary": [], "this_week_summary": [], "projects": []}

    # 标准化输出格式
    result = {
        "last_week_summary": [],
        "this_week_summary": [],
        "last_week_projects": [],
        "this_week_projects": [],
    }

    if data and isinstance(data, dict):
        # 规范化 key：AI 可能返回带空白/引号的 key（如 '\n  "last_week_summary"'）
        normalized = {}
        for dk, dv in data.items():
            clean_key = re.sub(r'[\s"\']+', '', str(dk))
            normalized[clean_key] = dv

        log_info(f"[业务盘] 原始 data keys: {list(data.keys())}")
        log_info(f"[业务盘] 规范化后 keys: {list(normalized.keys())}")

        # 解析上周项目（last_week_projects）
        last_week_projects = normalized.get("last_week_projects", [])
        if isinstance(last_week_projects, list):
            for item in last_week_projects:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    if name:
                        result["last_week_projects"].append({
                            "name": name,
                            "progress": int(item.get("progress", 0)),
                            "highlight": bool(item.get("highlight", False)),
                            "summary": item.get("summary", ""),
                            "persons": item.get("persons", []) if isinstance(item.get("persons"), list) else [],
                        })

        # 解析本周项目（this_week_projects）
        this_week_projects = normalized.get("this_week_projects", [])
        if isinstance(this_week_projects, list):
            for item in this_week_projects:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    if name:
                        result["this_week_projects"].append({
                            "name": name,
                            "progress": int(item.get("progress", 0)),
                            "highlight": bool(item.get("highlight", False)),
                            "summary": item.get("summary", ""),
                            "persons": item.get("persons", []) if isinstance(item.get("persons"), list) else [],
                        })

        # 兼容旧格式：projects 字段（未分上周/本周）
        projects = normalized.get("projects", [])
        if isinstance(projects, list) and not last_week_projects and not this_week_projects:
            for item in projects:
                if isinstance(item, dict):
                    name = item.get("name", "")
                    if name:
                        result["last_week_projects"].append({
                            "name": name,
                            "progress": int(item.get("progress", 0)),
                            "highlight": bool(item.get("highlight", False)),
                            "summary": item.get("summary", ""),
                            "persons": item.get("persons", []) if isinstance(item.get("persons"), list) else [],
                        })

        # 兼容旧格式：last_week_summary 和 this_week_summary
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
    if _generation_lock.locked():
        log_warning(f"生成任务进行中，跳过: {department_name}")
        return {
            "success": False,
            "department_id": department_id,
            "department_name": department_name,
            "status": "skipped",
            "error": "上一轮生成尚未完成，请勿重复点击",
        }
    async with _generation_lock:
        return await _do_generate_department_summary(
            db, department_id, department_name, week_start, week_end
        )


async def _do_generate_department_summary(
    db: AsyncSession,
    department_id: str,
    department_name: str,
    week_start: date,
    week_end: date,
) -> dict:
    """生成单个部门的总结（内部实现，由锁保护）"""
    log_info(f"开始生成部门总结: {department_name} ({week_start})")
    
    # 检查本周是否有该部门的周报数据
    report_count_result = await db.execute(
        select(WeeklyReport.id).where(
            WeeklyReport.department_id == department_id,
            WeeklyReport.week_start >= week_start,
            WeeklyReport.week_start <= week_end,
            WeeklyReport.status == "scored",
        )
    )
    has_reports = report_count_result.first() is not None
    
    if not has_reports:
        log_info(f"[业务盘] 部门本周无周报数据，跳过生成: {department_name} ({week_start})")
        return {
            "success": True,
            "department_id": department_id,
            "department_name": department_name,
            "status": "skipped",
            "error": None,
        }
    
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
        summary.last_week_projects = ai_result.get("last_week_projects", [])
        summary.this_week_projects = ai_result.get("this_week_projects", [])
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
        import traceback
        log_warning(f"部门总结数据异常，使用空结果: {department_name} - {type(e).__name__}: {e}")
        log_warning(f"完整堆栈: {traceback.format_exc()}")
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
    """生成所有部门的总结（带并发锁保护）"""
    log_info(f"[业务盘] 尝试获取生成锁...")
    try:
        await asyncio.wait_for(_generation_lock.acquire(), timeout=300)
    except asyncio.TimeoutError:
        log_warning("生成任务超时，拒绝新的全量生成请求")
        return [{
            "success": False,
            "department_id": None,
            "department_name": "ALL",
            "status": "skipped",
            "error": "上一轮生成尚未完成，请勿重复点击",
        }]
    
    log_info(f"[业务盘] 已获取生成锁，开始生成...")
    try:
        result = await _do_generate_all_department_summaries(db, week_start, week_end)
        return result
    finally:
        _generation_lock.release()
        log_info(f"[业务盘] 已释放生成锁")


async def _do_generate_all_department_summaries(
    db: AsyncSession,
    week_start: date,
    week_end: date,
) -> list[dict]:
    """生成所有部门的总结（内部实现，由锁保护）"""
    # 检查本周是否有周报数据
    report_count_result = await db.execute(
        select(WeeklyReport.id).where(
            WeeklyReport.week_start >= week_start,
            WeeklyReport.week_start <= week_end,
            WeeklyReport.status == "scored",
        )
    )
    has_reports = report_count_result.first() is not None
    
    if not has_reports:
        log_info(f"[业务盘] 本周无周报数据，跳过生成: {week_start}~{week_end}")
        return [{
            "success": True,
            "department_id": None,
            "department_name": "ALL",
            "status": "skipped",
            "error": None,
        }]
    
    # 查询所有部门（过滤掉名称为空的部门）
    result = await db.execute(
        select(Department)
        .where(Department.name.isnot(None))
        .where(Department.name != '')
        .order_by(Department.name)
    )
    departments = result.scalars().all()

    results = []
    for dept in departments:
        # 安全检查：确保部门名称有效
        if not dept.name:
            log_warning(f"跳过无效部门记录: ID={dept.id}")
            continue

        result = await _do_generate_department_summary(
            db, dept.id, dept.name, week_start, week_end
        )
        results.append(result)

    return results
