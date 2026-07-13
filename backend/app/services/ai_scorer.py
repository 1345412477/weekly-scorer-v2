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
    """获取 AI 客户端（支持自定义 api_key 和 base_url）"""
    global _client
    if _client is None:
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
            # 使用传入的自定义配置
            logger.info(f"[AI] 使用自定义模型 | base_url={url} | key={_mask_key(key)}")
            _client = AsyncOpenAI(
                api_key=key,
                base_url=url,
                timeout=timeout,
                max_retries=0,
            )
        else:
            # 回退到 .env 配置
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
                logger.info(f"[AI] 使用 DeepSeek | model={settings.SCORING_MODEL} | base_url={settings.DEEPSEEK_BASE_URL} | key={_mask_key(deepseek_key)}")
                _client = AsyncOpenAI(
                    api_key=deepseek_key,
                    base_url=settings.DEEPSEEK_BASE_URL,
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
    dimensions: list,
    db=None,
) -> dict:
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
    return normalize_result(result, dimensions)


async def score_report(
    content: str,
    author_name: str,
    department: str,
    dimensions: list,
    prompt_template: str = "",
    grade_thresholds: dict = None,
    db=None,
) -> dict:
    # 计算总满分
    total_full_score = sum(d.get("full_score", 0) for d in dimensions)

    def _dim_line(d):
        parts = [f"- {d['name']}（满分{d['full_score']}分"]
        if d.get('highest_score') is not None:
            parts.append(f"，最高分{d['highest_score']}分")
        if d.get('lowest_score') is not None:
            parts.append(f"，最低分{d['lowest_score']}分")
        parts.append(f"，考核内容：{d.get('evaluation_content', '无')}）")
        return "".join(parts)

    dimensions_text = "\n".join([_dim_line(d) for d in dimensions])

    dim_example = [
        {"name": d["name"], "score": 0, "max": d["full_score"], "comment": "评价"} for d in dimensions
    ]
    dim_json_example = json.dumps(dim_example, ensure_ascii=False)

    # 从配置的等级阈值生成等级标准文本
    thresholds = grade_thresholds or {"优": 45, "良": 38, "一般": 33, "差": 28}
    grade_text = "、".join(
        f"{k}(≥{v})" for k, v in sorted(thresholds.items(), key=lambda x: -x[1])
    )

    system_prompt = prompt_template or (
        "你是一位专业的工作报告评审专家。请根据评分维度对周报进行客观、公正的评分。\n\n"
        "评分规则：\n"
        f"1. 每个维度按指定满分评分（各维度满分之和={total_full_score}分）\n"
        f"2. 总分 = 各维度分数直接相加（范围0-{total_full_score}分）\n"
        "3. 每个维度的分数不得超过该维度的满分\n"
        "4. 每个维度必须给出具体分数和简短评价\n"
        "5. 总体评语需指出优点和待改进点\n"
        "6. 评分要客观，鼓励高质量、有量化数据的周报\n"
        f"7. 等级标准：{grade_text}\n"
        "8. 严格按 JSON 格式返回结果"
    )

    user_prompt = (
        f"## 员工信息\n- 姓名：{author_name}\n- 部门：{department or '未设置'}\n\n"
        f"## 周报内容\n{content}\n\n"
        f"## 评分维度（满分{total_full_score}分制）\n{dimensions_text}\n\n"
        f"## 输出格式（严格 JSON）\n"
        f'{{\n  "dimension_scores": {dim_json_example},\n'
        f'  "total_score": 0-{total_full_score},\n  "grade": "优/良/一般/差",\n'
        f'  "comment": "总体评语",\n  "suggestion": "改进建议"\n}}'
    )

    try:
        # 使用重试机制调用 API
        return await _retry_on_failure(
            _call_score_report_api,
            system_prompt,
            user_prompt,
            dimensions,
            db=db,
        )
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
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return {}
        return {}


MAX_DIM_DIFF = 22


def normalize_result(result: dict, dimensions: list) -> dict:
    dim_scores = result.get("dimension_scores", [])
    if not dim_scores:
        dim_scores = result.get("scores", result.get("breakdown", []))

    normalized = []
    for d in dimensions:
        found = None
        for ds in dim_scores:
            if isinstance(ds, dict) and ds.get("name") == d["name"]:
                found = ds
                break
        max_score = d["full_score"]
        raw_score = float(found.get("score", max_score * 0.7)) if found else max_score * 0.7
        
        ai_max = float(found.get("max", max_score)) if found else max_score
        if ai_max != max_score:
            raw_score = raw_score * max_score / ai_max
        raw_score = max(0, min(raw_score, max_score))
        
        normalized.append(
            {
                "name": d["name"],
                "score": round(raw_score, 1),
                "max": max_score,
                "comment": found.get("comment", "") if found else "",
            }
        )

    normalized = apply_score_constraints(normalized)
    total = calculate_total_score(normalized)

    return {
        "dimension_scores": normalized,
        "total_score": round(float(total), 1),
        "grade": result.get("grade", "一般"),
        "comment": result.get("comment", result.get("ai_comment", "")),
        "suggestion": result.get("suggestion", result.get("ai_suggestion", "")),
    }


def apply_score_constraints(dim_scores: list) -> list:
    """应用评分约束：维度分差不超过22分"""
    if not dim_scores:
        return dim_scores

    scores = [ds["score"] for ds in dim_scores]
    score_min = min(scores)
    score_max = max(scores)
    diff = score_max - score_min

    # 压缩分差：若最高分与最低分之差超过22，向均值方向压缩
    if diff > MAX_DIM_DIFF:
        mean = sum(scores) / len(scores)
        ratio = MAX_DIM_DIFF / diff
        for i, ds in enumerate(dim_scores):
            ds["score"] = round(mean + (ds["score"] - mean) * ratio, 1)

    return dim_scores


def calculate_total_score(dim_scores: list) -> float:
    """计算总分：各维度分数之和"""
    total = sum(ds["score"] for ds in dim_scores)
    return round(total, 1)


def get_grade(total_score: float, thresholds: dict) -> str:
    sorted_thresholds = sorted(thresholds.items(), key=lambda x: -x[1])
    for grade, threshold in sorted_thresholds:
        if total_score >= threshold:
            return grade
    if sorted_thresholds and all(str(grade).isascii() for grade, _ in sorted_thresholds):
        return "D"
    return "差"


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
    system_prompt = prompt_template or (
        """# èå¤è¯åæç¤ºè¯

è¯·æ ¹æ®åå·¥æ¬å¨çèå¤æå¡æ°æ®ï¼å¨ 0-100 åèå´åè¿è¡å®¢è§è¯åã

## è¯ååèç»´åº¦
1. åºå¤å®æ´æ§ï¼æ¯å¦å¨å¤ï¼ææ è¿å°ãæ©éãç¼ºå¡
2. å·¥ä½æ¶é¿ï¼æ¯æ¥å·¥ä½æ¶é¿æ¯å¦è¾¾æ 
3. å¼å¸¸æåµï¼æ¯å¦ææªè¯´æçå¼å¸¸èå¤
4. å ç­æåµï¼åçå ç­è§ä¸ºç§¯æè¡¨ç°ï¼æ éé¢å¤å åä¸éï¼

## è¾åºè¦æ±
è¯·ä»¥ JSON æ ¼å¼è¿åï¼
- scoreï¼0-100 çæ°å¼ï¼
- commentï¼ç®ç­ç¹è¯ï¼"""
    )

    user_prompt = (
        f"## 员工信息\n- 姓名：{author_name}\n- 部门：{department or '未设置'}\n\n"
        f"## 本周考勤数据\n{summary_text}\n\n"
        f"## 输出格式（严格 JSON）\n"
        f'{{"score": 数字0-100, "comment": "简短评价"}}'
    )

    try:
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
        score = float(result.get("score", 0)) if result.get("score") is not None else 0.0
        return {
            "score": round(max(0.0, min(score, 100.0)), 1),
            "comment": result.get("comment", ""),
            "raw": raw,
        }
    except Exception as e:
        raise AIScoringError(f"考勤评分失败: {str(e)}") from e


async def score_chat(
    summary_text: str,
    author_name: str,
    department: str,
    prompt_template: str = "",
    db=None,
) -> dict:
    """沟通评分：聊天记录摘要 + 一周小结 OCR 摘要，统一按 chat_prompt 打分。

    返回：{"score": float, "comment": str, "raw": ...}
    """
    system_prompt = prompt_template or (
        """# æ²éä¸ä¸å¨å°ç»è¯åæç¤ºè¯

è¯·æ ¹æ®åå·¥æ¬å¨çå·¥ä½æ²éè®°å½ï¼ä¼ä¸å¾®ä¿¡å¯¹è¯è®°å½ï¼ä»¥åä¸å¨å°ç»åå®¹ï¼å¨ 0-100 åèå´åå¯¹å¶æ²éè´¨éåååºæçè¿è¡è¯åã

## è¯ååèç»´åº¦
1. å·¥ä½ä¼è¯æ°éï¼å¤ççå·¥ä½ç¸å³å¯¹è¯æ°ï¼ä½ç°å¨ä¸å¨å°ç»ä¸­ï¼
2. ååºæçï¼åå¤æ¯å¦åæ¶ï¼é»å¡æ¶é¿å¦ä½
3. æ²éè´¨éï¼è¡¨è¾¾æ¸æ°ãæå±æ¬¡ãæä¾å¿è¦ä¿¡æ¯
4. ä¸å¨å°ç»å®æ´æ§ï¼æ¯å¦å®æ´åæ æ¬å¨å·¥ä½

## è¾åºè¦æ±
è¯·ä»¥ JSON æ ¼å¼è¿åï¼
- scoreï¼0-100 çæ°å¼ï¼
- commentï¼ç®ç­ç¹è¯ï¼"""
    )

    user_prompt = (
        f"## 员工信息\n- 姓名：{author_name}\n- 部门：{department or '未设置'}\n\n"
        f"## 本周沟通数据（聊天记录 + 一周小结）\n{summary_text}\n\n"
        f"## 输出格式（严格 JSON）\n"
        f'{{"score": 数字0-100, "comment": "简短评价"}}'
    )

    try:
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
        score = float(result.get("score", 0)) if result.get("score") is not None else 0.0
        return {
            "score": round(max(0.0, min(score, 100.0)), 1),
            "comment": result.get("comment", ""),
            "raw": raw,
        }
    except Exception as e:
        raise AIScoringError(f"沟通评分失败: {str(e)}") from e


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
            "model": model_id if 'model_id' in dir() else settings.SCORING_MODEL,
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
