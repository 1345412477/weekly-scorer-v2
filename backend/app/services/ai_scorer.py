"""AI 评分引擎 - 支持小米 MiMo / 豆包 / DeepSeek"""
import json
import logging
from typing import Optional
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger("weekly_scorer")
settings = get_settings()
_client: Optional[AsyncOpenAI] = None


def _mask_key(key: str) -> str:
    """脱敏显示 API Key"""
    if not key:
        return "(empty)"
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "****" + key[-4:]


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        # 使用 getattr 安全读取，避免用户注释配置项时报错
        mimo_key = getattr(settings, "MIMO_API_KEY", "")
        ark_key = getattr(settings, "ARK_API_KEY", "")
        deepseek_key = getattr(settings, "DEEPSEEK_API_KEY", "")
        
        # 获取超时配置 - 使用 httpx.Timeout 格式
        timeout = getattr(settings, "AI_TIMEOUT", 60)

        if mimo_key:
            logger.info(f"[AI] 使用 MiMo | model={settings.SCORING_MODEL} | base_url={settings.MIMO_BASE_URL} | key={_mask_key(mimo_key)} | timeout={timeout}s")
            _client = AsyncOpenAI(
                api_key=mimo_key,
                base_url=settings.MIMO_BASE_URL,
                timeout=timeout,
            )
        elif ark_key:
            logger.info(f"[AI] 使用 Ark(豆包) | model={settings.SCORING_MODEL} | base_url={settings.ARK_BASE_URL} | key={_mask_key(ark_key)} | timeout={timeout}s")
            _client = AsyncOpenAI(
                api_key=ark_key,
                base_url=settings.ARK_BASE_URL,
                timeout=timeout,
            )
        elif deepseek_key:
            logger.info(f"[AI] 使用 DeepSeek | model={settings.SCORING_MODEL} | base_url={settings.DEEPSEEK_BASE_URL} | key={_mask_key(deepseek_key)} | timeout={timeout}s")
            _client = AsyncOpenAI(
                api_key=deepseek_key,
                base_url=settings.DEEPSEEK_BASE_URL,
                timeout=timeout,
            )
        else:
            raise AIScoringError("未配置任何 AI API Key，请在 .env 中配置 MIMO_API_KEY / ARK_API_KEY / DEEPSEEK_API_KEY")
    return _client


class AIScoringError(Exception):
    """AI 评分失败的自定义异常"""
    pass


async def score_report(
    content: str,
    author_name: str,
    department: str,
    dimensions: list,
    prompt_template: str = "",
    grade_thresholds: dict = None,
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
        c = get_client()
        response = await c.chat.completions.create(
            model=settings.SCORING_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=settings.SCORING_TEMPERATURE,
        )
        raw = response.choices[0].message.content
        result = _extract_json(raw)
        return normalize_result(result, dimensions)
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "authentication" in error_msg.lower() or "auth" in error_msg.lower():
            user_message = "AI 服务认证失败：请检查 API Key 是否正确配置。"
        elif "rate" in error_msg.lower() or "limit" in error_msg.lower():
            user_message = "AI 服务请求频率超限：请稍后再试，或联系管理员检查配额。"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            user_message = "AI 服务响应超时：请稍后再试，或检查网络连接。"
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            user_message = "AI 服务连接失败：请检查网络连接，或确认 AI 服务地址是否正确。"
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
            return json.loads(text[start:end])
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


async def test_connection() -> dict:
    try:
        c = get_client()
        logger.info(f"[AI] test_connection: model={settings.SCORING_MODEL}, base_url={c.base_url}")
        response = await c.chat.completions.create(
            model=settings.SCORING_MODEL,
            messages=[{"role": "user", "content": "回复OK"}],
            max_tokens=10,
        )
        logger.info(f"[AI] test_connection 成功: response={response.choices[0].message.content}")
        return {
            "success": True,
            "provider": settings.AI_PROVIDER,
            "model": settings.SCORING_MODEL,
        }
    except Exception as e:
        logger.error(f"[AI] test_connection 失败: {e}")
        if hasattr(e, 'response'):
            logger.error(f"[AI] HTTP status: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}")
            try:
                logger.error(f"[AI] Response body: {e.response.text if hasattr(e.response, 'text') else 'N/A'}")
            except:
                pass
        return {
            "success": False,
            "provider": settings.AI_PROVIDER,
            "model": settings.SCORING_MODEL,
            "error": str(e),
        }
