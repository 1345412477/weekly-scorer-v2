"""AI 评分引擎 - 支持数据库自定义模型 + .env 配置"""
import asyncio
import json
import logging
from typing import Optional
import httpx
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger("weekly_scorer")
settings = get_settings()
_client: Optional[AsyncOpenAI] = None
_db_model_cache: Optional[dict] = None  # 缓存数据库中的活跃模型配置

# 重试配置
MAX_RETRY_ATTEMPTS = 3  # 最大重试次数
RETRY_DELAY_SECONDS = 2  # 重试间隔（秒）


def _mask_key(key: str) -> str:
    """脱敏显示 API Key"""
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "****" + key[-4:]


async def _get_active_model_from_db(db=None) -> Optional[dict]:
    """从数据库获取当前激活的 AI 模型配置"""
    global _db_model_cache
    if _db_model_cache is not None:
        return _db_model_cache

    if db is None:
        return None

    try:
        from sqlalchemy import select
        from app.models.models import AIModel
        result = await db.execute(
            select(AIModel).where(AIModel.is_active == True).limit(1)
        )
        model = result.scalar_one_or_none()
        if model:
            _db_model_cache = {
                "id": model.id,
                "name": model.name,
                "provider": model.provider,
                "model_id": model.model_id,
                "api_key": model.api_key,
                "base_url": model.base_url,
                "is_vision": model.is_vision,
            }
            logger.info(f"[AI] 从数据库加载模型: {model.name} ({model.model_id})")
            return _db_model_cache
    except Exception as e:
        logger.debug(f"[AI] 从数据库读取模型配置失败: {e}")

    return None


def _clear_db_model_cache():
    """清除数据库模型缓存（模型配置变更时调用）"""
    global _db_model_cache, _client
    _db_model_cache = None
    _client = None


def get_client(api_key: str = None, base_url: str = None) -> AsyncOpenAI:
    """获取 AI 客户端（支持自定义 api_key 和 base_url）

    注意：当传入自定义 api_key/base_url 时，每次都会创建新客户端（不缓存），
    确保不同服务（OCR、评分）使用各自的模型配置不会互相污染。
    .env 回退路径的客户端会被缓存以复用连接。
    """
    global _client
    # 明确区分连接超时和读取超时，关闭 SDK 默认重试
    connect_timeout = int(getattr(settings, "AI_CONNECT_TIMEOUT", 10))
    read_timeout = int(getattr(settings, "AI_TIMEOUT", 60))
    timeout = httpx.Timeout(
        connect=connect_timeout,
        read=read_timeout,
        write=30,
        pool=5,
    )

    key = api_key or ""
    url = base_url or ""

    if key and url:
        # 使用传入的自定义配置（每次创建新客户端，不缓存）
        logger.info(f"[AI] 使用自定义模型 | base_url={url} | key={_mask_key(key)}")
        return AsyncOpenAI(
            api_key=key,
            base_url=url,
            timeout=timeout,
            max_retries=0,
        )

    # 回退到 .env 配置（复用缓存的客户端）
    if _client is not None:
        return _client

    mimo_key = getattr(settings, "MIMO_API_KEY", "")
    ark_key = getattr(settings, "ARK_API_KEY", "")
    deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", "")

    if mimo_key:
        logger.info(f"[AI] 使用 MiMo | model={settings.SCORING_MODEL} | base_url={settings.MIMO_BASE_URL} | key={_mask_key(mimo_key)}")
        _client = AsyncOpenAI(
            api_key=mimo_key,
            base_url=settings.MIMO_BASE_URL,
            timeout=timeout,
            max_retries=0,
        )
    elif ark_key:
        logger.info(f"[AI] 使用 Ark(豆包) | model={settings.SCORING_MODEL} | base_url={settings.ARK_BASE_URL} | key={_mask_key(ark_key)}")
        _client = AsyncOpenAI(
            api_key=ark_key,
            base_url=settings.ARK_BASE_URL,
            timeout=timeout,
            max_retries=0,
        )
    elif deepseek_key:
        logger.info(f"[AI] 使用 DeepSeek | model={settings.SCORING_MODEL} | base_url={getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com')} | key={_mask_key(deepseek_key)}")
        _client = AsyncOpenAI(
            api_key=deepseek_key,
            base_url=getattr(settings, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout=timeout,
            max_retries=0,
        )
    else:
        raise AIScoringError("未配置任何 AI API Key，请在 .env 中配置 MIMO_API_KEY / ARK_API_KEY / DEEPSEEK_API_KEY，或在系统设置中添加自定义模型")
    return _client


class AIScoringError(Exception):
    """AI 评分失败的自定义异常"""
    pass


def _safe_get_content(response) -> str:
    """安全获取 AI 响应内容：处理 choices 为空的情况"""
    if not response.choices:
        raise AIScoringError("AI 服务返回空结果，请稍后重试")
    return response.choices[0].message.content or ""


def _is_retryable_error(error_msg: str) -> bool:
    """判断错误是否可重试（超时、网络、频率限制等）"""
    retryable_keywords = ["timeout", "timed out", "rate", "limit", "connection", "network", "temporarily", "busy"]
    error_lower = error_msg.lower()
    return any(kw in error_lower for kw in retryable_keywords)


async def _retry_on_failure(func, *args, **kwargs):
    """带重试机制的异步函数包装器，失败/超时时自动重试直至成功或达到最大次数"""
    last_error = None
    for attempt in range(MAX_RETRY_ATTEMPTS + 1):
        try:
            return await func(*args, **kwargs)
        except AIScoringError as e:
            last_error = e
            error_msg = str(e)
            # 认证错误、模型错误等不重试
            if any(kw in error_msg.lower() for kw in ["认证失败", "api key", "模型不可用", "not found"]):
                logger.error(f"[AI] 不可重试错误: {error_msg}")
                raise
            # 可重试错误
            if attempt < MAX_RETRY_ATTEMPTS:
                delay = RETRY_DELAY_SECONDS * (2 ** attempt)  # 指数退避
                logger.warning(f"[AI] 第 {attempt + 1} 次失败，{delay}秒后重试: {error_msg}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[AI] 已达最大重试次数 {MAX_RETRY_ATTEMPTS}，放弃重试")
                raise
        except Exception as e:
            last_error = e
            error_msg = str(e)
            if not _is_retryable_error(error_msg):
                logger.error(f"[AI] 不可重试错误: {error_msg}")
                raise AIScoringError(f"AI 评分失败: {error_msg}") from e
            if attempt < MAX_RETRY_ATTEMPTS:
                delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                logger.warning(f"[AI] 第 {attempt + 1} 次失败，{delay}秒后重试: {error_msg}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"[AI] 已达最大重试次数 {MAX_RETRY_ATTEMPTS}，放弃重试")
                raise AIScoringError(f"AI 评分失败（已重试 {MAX_RETRY_ATTEMPTS} 次）: {error_msg}") from e
    raise last_error or AIScoringError("AI 评分失败")


async def _get_scoring_config(db=None) -> tuple[str, Optional[dict]]:
    """获取评分配置：返回 (model_id, db_model_config)"""
    db_model = await _get_active_model_from_db(db)
    if db_model:
        return db_model["model_id"], db_model
    return settings.SCORING_MODEL, None


async def _call_score_report_api(
    system_prompt: str,
    user_prompt: str,
    db=None,
) -> tuple[dict, str]:
    """实际调用 AI API 进行评分（内部函数，供重试包装器使用）"""
    model_id, db_model = await _get_scoring_config(db)
    c = get_client(
        api_key=db_model["api_key"] if db_model else None,
        base_url=db_model["base_url"] if db_model else None,
    )
    response = await c.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=settings.SCORING_TEMPERATURE,
    )
    raw = _safe_get_content(response)
    result = _extract_json(raw)
    return result, raw


async def score_report(
    content: str,
    author_name: str,
    department: str,
    prompt_template: str = "",
    db=None,
) -> dict:
    system_prompt = prompt_template
    if not system_prompt:
        raise AIScoringError("未配置周报评分提示词，请在系统设置中填写")

    user_prompt = (
        f"## 员工信息\n- 姓名：{author_name}\n- 部门：{department or '未设置'}\n\n"
        f"## 周报内容\n{content}\n\n"
        f"## 输出格式（严格 JSON）\n"
        f'{{"total_score": 数字0-100, "grade": "优/良/一般/差", "comment": "总体评语", "suggestion": "改进建议", '
        f'"dimension_scores": [{{"name": "维度名", "score": 得分, "max": 满分, "comment": "评语"}}]}}'
    )

    try:
        result, raw = await _retry_on_failure(
            _call_score_report_api,
            system_prompt,
            user_prompt,
            db=db,
        )
        total_score = float(result.get("total_score", 0))
        # 提取维度评分（AI 可能不返回或格式不规范，需安全解析）
        dimension_scores = []
        raw_dims = result.get("dimension_scores")
        if isinstance(raw_dims, list):
            for d in raw_dims:
                if isinstance(d, dict):
                    dimension_scores.append({
                        "name": d.get("name", ""),
                        "score": float(d.get("score", 0)),
                        "max": float(d.get("max", 0)),
                        "comment": d.get("comment", ""),
                    })
        return {
            "total_score": round(max(28.0, min(total_score, 40.0)), 1),
            "grade": result.get("grade", "一般"),
            "comment": result.get("comment", ""),
            "suggestion": result.get("suggestion", ""),
            "dimension_scores": dimension_scores,
            "raw": raw,
        }
    except AIScoringError as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "auth" in error_msg.lower():
            user_message = "AI 服务认证失败：请检查 API Key 是否正确配置。"
        elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
            user_message = "AI 服务请求频率超限：请稍后再试，或联系管理员检查配额。"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            user_message = "AI 服务响应超时：已自动重试多次，请稍后再试或检查网络连接。"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            user_message = "AI 服务连接失败：已自动重试多次，请检查网络连接或确认 AI 服务地址是否正确。"
        elif "model" in error_msg.lower() or "not found" in error_msg.lower():
            user_message = "AI 模型不可用：请检查模型名称是否正确，或联系管理员。"
        else:
            user_message = f"AI 评分失败：{error_msg}"

        raise AIScoringError(user_message) from e


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        result = json.loads(text)
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                result = json.loads(text[start:end])
                return result if isinstance(result, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}





async def _call_ai_with_retry(
    system_prompt: str,
    user_prompt: str,
    db=None,
) -> tuple[dict, str]:
    """通用 AI 调用包装器：带重试机制，返回 (parsed_json, raw_text)"""
    async def _do_call():
        model_id, db_model = await _get_scoring_config(db)
        c = get_client(
            api_key=db_model["api_key"] if db_model else None,
            base_url=db_model["base_url"] if db_model else None,
        )
        response = await c.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.SCORING_TEMPERATURE,
        )
        raw = _safe_get_content(response)
        result = _extract_json(raw)
        return result, raw

    return await _retry_on_failure(_do_call)


async def score_attendance(
    summary_text: str,
    author_name: str,
    department: str,
    prompt_template: str = "",
    db=None,
) -> dict:
    """考勤评分：将本周打卡摘要（日期+上下班+地点+状态）按 attendance_prompt 打分。

    返回：{"score": float, "comment": str, "raw": ...}
    """
    system_prompt = prompt_template
    if not system_prompt:
        raise AIScoringError("未配置考勤评分提示词，请在系统设置中填写")

    user_prompt = (
        f"## 员工信息\n- 姓名：{author_name}\n- 部门：{department or '未设置'}\n\n"
        f"## 本周考勤数据\n{summary_text}\n\n"
        f"## 输出格式（严格 JSON）\n"
        f'{{"score": 数字0-100, "comment": "简短评价"}}'
    )

    try:
        result, raw = await _call_ai_with_retry(system_prompt, user_prompt, db=db)
        if not isinstance(result, dict):
            raise AIScoringError(f"AI 返回格式异常: 期望 dict，得到 {type(result).__name__}")
        score = float(result.get("score", 0)) if result.get("score") is not None else 0.0
        return {
            # 加班分在 100 分基础上累加，不设上限
            "score": round(max(0.0, score), 1),
            "comment": result.get("comment", ""),
            "overtime_points": float(result.get("overtime_points") or 0),
            "raw": raw,
        }
    except AIScoringError:
        raise
    except Exception as e:
        raise AIScoringError(f"考勤评分失败: {str(e)}") from e


async def score_weekly_summary(
    summary_text: str,
    author_name: str,
    department: str,
    prompt_template: str = "",
    db=None,
) -> dict:
    """一周小结独立评分（满分20分）。

    扣分规则由提示词定义。

    参数:
      prompt_template: 提示词模板（必填，从系统设置读取）
    """
    system_prompt = prompt_template
    if not system_prompt:
        raise AIScoringError("未配置会话评分提示词，请在系统设置中填写")

    user_prompt = (
        f"## 员工信息\n- 姓名：{author_name}\n- 部门：{department or '未设置'}\n\n"
        f"## 一周小结数据\n{summary_text}\n\n"
        f"## 输出格式（严格 JSON）\n"
        f'{{"score": 数字0-20, "comment": "简短评价"}}'
    )

    try:
        result, raw = await _call_ai_with_retry(system_prompt, user_prompt, db=db)
        if not isinstance(result, dict):
            raise AIScoringError(f"AI 返回格式异常: 期望 dict，得到 {type(result).__name__}")
        score = float(result.get("score", 0)) if result.get("score") is not None else 0.0
        return {
            "score": round(max(0.0, min(score, 20.0)), 1),
            "comment": result.get("comment", ""),
            "raw": raw,
        }
    except AIScoringError:
        raise
    except Exception as e:
        raise AIScoringError(f"一周小结评分失败: {str(e)}") from e


async def score_chat_records(
    summary_text: str,
    author_name: str,
    department: str,
    prompt_template: str = "",
    sensitive_words: list = None,
    raw_messages: list = None,
    db=None,
) -> dict:
    """会话记录独立评分（满分80分）。

    扣分规则由提示词定义。

    参数:
      prompt_template: 提示词模板（必填，从系统设置读取）
    """
    # 构建会话记录明细文本（含发送时间和内容，供 AI 判断响应时间和敏感词）
    records_detail = ""
    if raw_messages:
        # 过滤非 dict 元素，防止 'str' object has no attribute 'get'
        valid_msgs = [m for m in raw_messages if isinstance(m, dict)]
        msgs = sorted(valid_msgs, key=lambda m: m.get("send_time", "") or "")
        for idx, m in enumerate(msgs):
            st = m.get("send_time", "")
            ct = (m.get("content", "") or "")[:120]
            records_detail += f"  消息{idx+1}: 时间={st} 内容={ct}\n"

    system_prompt = prompt_template
    if not system_prompt:
        raise AIScoringError("未配置会话评分提示词，请在系统设置中填写")

    user_prompt = (
        f"## 员工信息\n- 姓名：{author_name}\n- 部门：{department or '未设置'}\n\n"
        f"## 会话记录数据\n{summary_text}\n"
    )

    if records_detail:
        user_prompt += f"\n## 消息明细（用于敏感词和响应时间判断）\n{records_detail}\n"

    user_prompt += (
        f"\n## 输出格式（严格 JSON）\n"
        f'{{"score": 数字0-80, "comment": "简短评价"}}'
    )

    try:
        result, raw = await _call_ai_with_retry(system_prompt, user_prompt, db=db)
        if not isinstance(result, dict):
            raise AIScoringError(f"AI 返回格式异常: 期望 dict，得到 {type(result).__name__}")
        score = float(result.get("score", 0)) if result.get("score") is not None else 0.0
        return {
            "score": round(max(0.0, min(score, 80.0)), 1),
            "comment": result.get("comment", ""),
            "raw": raw,
        }
    except AIScoringError:
        raise
    except Exception as e:
        raise AIScoringError(f"会话记录评分失败: {str(e)}") from e


# 保留旧接口兼容
async def score_chat(
    summary_text: str,
    author_name: str,
    department: str,
    prompt_template: str = "",
    sensitive_words: list = None,
    raw_messages: list = None,
    has_summary: bool = True,
    has_chat: bool = True,
    summary_prompt: str = "",
    db=None,
) -> dict:
    """沟通评分（两段式）：一周小结(满分20) + 会话记录(满分80)，独立评分后相加。

    一周小结缺失计0分；会话记录缺失默认满分80（有数据则从满分按规则扣分）。

    返回：{"score": float (0-100), "summary_part": float (0-20), "records_part": float (0-80), "comment": str, "raw": ...}
    """
    summary_part = 0.0
    records_part = 80.0  # 无会话记录时默认满分80
    comments = []

    # 分割摘要文本：找到"一周小结"部分
    weekly_summary_section = ""
    chat_records_section = summary_text

    if "一周小结" in summary_text:
        idx = summary_text.find("一周小结")
        line_start = summary_text.rfind("\n", 0, idx) + 1
        weekly_summary_section = summary_text[line_start:]
        chat_records_section = summary_text[:line_start]

    # 一周小结评分（仅当有数据时）— 使用独立的 summary_prompt（20分制）
    if has_summary and weekly_summary_section and ("工作会话" in weekly_summary_section or "一周小结" in weekly_summary_section):
        if summary_prompt:
            try:
                result = await score_weekly_summary(weekly_summary_section, author_name, department,
                                                      prompt_template=summary_prompt, db=db)
                summary_part = result["score"]
                if result.get("comment"):
                    comments.append(f"小结:{result['comment']}")
            except AIScoringError as e:
                logger.warning(f"[沟通评分] 一周小结评分失败: {e}")
        else:
            logger.warning("[沟通评分] summary_prompt 未配置，一周小结评分跳过（计0分）")

    # 会话记录评分（仅当有数据时）
    if has_chat and chat_records_section and ("会话记录" in chat_records_section or "聊天记录" in chat_records_section or "消息明细" in chat_records_section):
        try:
            result = await score_chat_records(
                chat_records_section, author_name, department,
                prompt_template=prompt_template,
                sensitive_words=sensitive_words,
                raw_messages=raw_messages,
                db=db,
            )
            records_part = result["score"]
            # 严格限制会话记录分不超过80
            records_part = min(records_part, 80.0)
            if result.get("comment"):
                comments.append(f"会话:{result['comment']}")
        except AIScoringError as e:
            logger.warning(f"[沟通评分] 会话记录评分失败: {e}")

    # 严格限制各子项分数范围
    summary_part = max(0.0, min(summary_part, 20.0))
    records_part = max(0.0, min(records_part, 80.0))
    total = summary_part + records_part

    return {
        "score": round(total, 1),
        "summary_part": round(summary_part, 1),
        "records_part": round(records_part, 1),
        "comment": " | ".join(comments) if comments else "",
        "raw": f"summary={summary_part}, records={records_part}",
    }


AI_CONNECTION_CACHE_TTL_SECONDS = 30 * 60  # 30 分钟，避免频繁检测产生 token 消耗


async def test_connection(db=None, force_refresh: bool = False) -> dict:
    """测试 AI 模型连接。

    - 优先使用数据库中的自定义模型配置
    - 若数据库无配置，回退到 .env 配置
    - force_refresh=False 时返回缓存状态（30 分钟有效）
    - force_refresh=True 时强制重新检测
    """
    from datetime import timedelta
    from app.utils.time_utils import bj_now

    # 如果不强制刷新，先尝试返回缓存状态
    if not force_refresh and db:
        try:
            from sqlalchemy import select
            from app.models.models import ScoringConfig
            result = await db.execute(select(ScoringConfig).limit(1))
            cfg = result.scalar_one_or_none()
            if cfg and cfg.ai_connection_checked_at:
                if (bj_now() - cfg.ai_connection_checked_at) < timedelta(minutes=30):
                    logger.info(f"[AI] 使用缓存状态 (checked_at={cfg.ai_connection_checked_at})")
                    return {
                        "success": cfg.ai_connection_status,
                        "provider": cfg.ai_connection_provider or "unknown",
                        "model": cfg.ai_connection_model or "unknown",
                        "model_name": "缓存状态",
                        "checked_at": cfg.ai_connection_checked_at.isoformat(),
                        "cached": True,
                    }
        except Exception as e:
            logger.debug(f"[AI] 读取缓存状态失败: {e}")

    # 强制刷新或无缓存，进行真实检测
    try:
        model_id, db_model = await _get_scoring_config(db)
        c = get_client(
            api_key=db_model["api_key"] if db_model else None,
            base_url=db_model["base_url"] if db_model else None,
        )
        logger.info(f"[AI] test_connection 真实检测: model={model_id}, base_url={c.base_url}")
        response = await c.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "回复OK"}],
            max_tokens=10,
        )
        logger.info(f"[AI] test_connection 成功: response={_safe_get_content(response)}")

        result = {
            "success": True,
            "provider": db_model["provider"] if db_model else settings.AI_PROVIDER,
            "model": model_id,
            "model_name": db_model["name"] if db_model else "默认配置",
            "checked_at": bj_now().isoformat(),
            "cached": False,
        }

        if db:
            try:
                from sqlalchemy import select
                from app.models.models import ScoringConfig
                cfg_result = await db.execute(select(ScoringConfig).limit(1))
                cfg = cfg_result.scalar_one_or_none()
                if cfg:
                    cfg.ai_connection_status = True
                    cfg.ai_connection_provider = result["provider"]
                    cfg.ai_connection_model = model_id
                    cfg.ai_connection_checked_at = bj_now()
                    await db.commit()
            except Exception as e:
                logger.debug(f"[AI] 更新缓存状态失败: {e}")

        return result
    except Exception as e:
        logger.error(f"[AI] test_connection 失败: {e}")
        if hasattr(e, 'response'):
            logger.error(f"[AI] HTTP status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
            try:
                logger.error(f"[AI] Response body: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
            except Exception as log_err:
                logger.debug(f"[AI] 读取响应体时出错(可忽略): {log_err}")

        result = {
            "success": False,
            "provider": db_model["provider"] if db_model else settings.AI_PROVIDER,
            "model": locals().get('model_id', settings.SCORING_MODEL),
            "error": str(e),
            "checked_at": bj_now().isoformat(),
            "cached": False,
        }

        if db:
            try:
                from sqlalchemy import select
                from app.models.models import ScoringConfig
                cfg_result = await db.execute(select(ScoringConfig).limit(1))
                cfg = cfg_result.scalar_one_or_none()
                if cfg:
                    cfg.ai_connection_status = False
                    cfg.ai_connection_provider = result["provider"]
                    cfg.ai_connection_model = result["model"]
                    cfg.ai_connection_checked_at = bj_now()
                    await db.commit()
            except Exception as e2:
                logger.debug(f"[AI] 更新失败状态缓存失败: {e2}")

        return result
