"""OCR 服务：解析一周小结图片，提取工作会话次数等关键信息。

失败时抛出 OCRParseError，由调用方返回明确错误信息（不做兜底/启发式解析）。
"""
import re
import logging
import base64
import mimetypes
from typing import Optional, Tuple
from datetime import datetime, date
from app.utils.time_utils import bj_today

from app.services.ai_scorer import get_client, AIScoringError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OCRParseError(Exception):
    """OCR 解析失败或关键字段缺失时抛出。"""
    pass


def _mime_from_filename(filename: str) -> str:
    """根据文件名推导 MIME 类型"""
    if not filename:
        return "image/jpeg"
    mime, _ = mimetypes.guess_type(filename)
    if mime and mime.startswith("image/"):
        return mime
    ext = filename.lower()
    if ext.endswith(".png"):
        return "image/png"
    if ext.endswith(".jpg") or ext.endswith(".jpeg"):
        return "image/jpeg"
    return "image/jpeg"


async def parse_summary_image(
    image_bytes: bytes,
    filename: str,
    override_author_name: Optional[str] = None,
    db=None,
) -> dict:
    """对一周小结图片执行 OCR + 结构化解析。

    失败（AI 调用失败 / JSON 解析失败 / work_session_count 未识别）均抛出 OCRParseError。
    不提供任何兜底策略。

    参数:
      override_author_name: 可选；若提供，将直接覆盖 AI 识别到的 author_name
        （因为一周小结图片不一定包含员工姓名，可由调用方从周报文件名统一识别）
      db: 可选数据库会话；若提供，优先使用数据库中的活跃 AI 模型
    """
    if not image_bytes or len(image_bytes) < 10:
        raise OCRParseError("上传的图片内容为空或损坏，无法识别")

    mime = _mime_from_filename(filename)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    # 优先使用数据库中的活跃模型（视觉能力需模型支持）
    ocr_api_key = None
    ocr_base_url = None
    model = None
    if db is not None:
        try:
            from app.services.ai_scorer import _get_active_model_from_db
            db_model = await _get_active_model_from_db(db)
            if db_model:
                model = db_model["model_id"]
                ocr_api_key = db_model["api_key"]
                ocr_base_url = db_model["base_url"]
                logger.info(f"[OCR] 使用数据库模型: {model}")
        except Exception:
            logger.warning("[OCR] 加载数据库模型失败，回退到 .env 配置")

    if not model:
        # 选择模型：优先使用 VISION_MODEL（视觉模型）；未配置时回退到 SCORING_MODEL
        model = (getattr(settings, "VISION_MODEL", "") or "").strip()
        if not model:
            model = settings.SCORING_MODEL
            logger.info(f"[OCR] 未配置 VISION_MODEL，回退到 SCORING_MODEL=%s（若该模型不支持视觉时会失败）", model)

    # 读取数据库中的 OCR 提示词配置（必须配置）
    ocr_system_prompt = ""
    if db is not None:
        try:
            from app.models.models import ScoringConfig
            from sqlalchemy import select
            cfg_r = await db.execute(select(ScoringConfig).where(ScoringConfig.is_active == True).limit(1))
            cfg = cfg_r.scalar_one_or_none()
            if cfg and getattr(cfg, "ocr_prompt", ""):
                ocr_system_prompt = cfg.ocr_prompt
                logger.info("[OCR] 使用数据库中的 OCR 提示词配置")
        except Exception:
            pass
    if not ocr_system_prompt:
        raise OCRParseError("未配置 OCR 一周小结提示词，请在系统设置中填写")

    user_text = (
        "以下是一张一周小结图片，请先完整读取图片中的所有中文内容，"
        "并从中提取以下结构化字段。"
        "特别注意识别数字：例如「工作会话次数」「本周会话数」"
        "「本周会话数」等字段的数值。"
        "若图片中完全没有相关数字，请把对应字段返回 null。"
        "严格只输出 JSON 对象，不要说明性文字。"
    )

    try:
        c = get_client(api_key=ocr_api_key, base_url=ocr_base_url)
        response = await c.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ocr_system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0.2,
        )
    except AIScoringError as e:
        logger.warning(f"[OCR] AI 调用失败: {e}")
        raise OCRParseError(f"AI 服务调用失败，无法识别一周小结内容，请稍后重试")
    except Exception as e:
        logger.warning(f"[OCR] 请求异常: {e}")
        raise OCRParseError(f"OCR 解析请求失败: {e}")

    raw_json = response.choices[0].message.content or ""
    parsed = _safe_load_json(raw_json)
    if not parsed:
        logger.warning(f"[OCR] 返回内容无法解析为 JSON: {raw_json[:120]}")
        raise OCRParseError("图片内容无法识别，请更换清晰的一周小结图片后重试")

    # 关键字段校验
    ws = parsed.get("work_session_count")
    if ws is None:
        raise OCRParseError("未识别到工作会话次数，请确认图片内容完整或重新上传")

    # 处理 override_author_name（由周报文件名提供的统一姓名）
    if override_author_name:
        parsed["author_name"] = override_author_name

    parsed["raw_ocr_text"] = raw_json
    return parsed


def _safe_load_json(text: str) -> dict:
    """从 LLM 响应中提取 JSON 对象。"""
    import json

    if not text:
        return {}
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


def infer_week_range(target_date: Optional[date] = None) -> Tuple[date, date]:
    """推断本周的周一-周日范围（默认今天所在周）"""
    today = target_date or bj_today()
    monday = today - _timedelta(days=today.weekday())
    sunday = monday + _timedelta(days=6)
    return monday, sunday


def _timedelta(**kwargs):
    """延迟导入以避免污染模块命名空间"""
    from datetime import timedelta
    return timedelta(**kwargs)
