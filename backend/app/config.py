"""应用配置"""
import os
import secrets
import warnings
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict

# 内部标记值：用于检测用户是否尚未在 .env 中覆盖关键凭据
_SENTINEL_AUTH_SECRET = "__UNSET_WEEKLY_SCORER_AUTH_SECRET__"
_SENTINEL_ADMIN_PASSWORD = "__UNSET_WEEKLY_SCORER_ADMIN_PASSWORD__"
# 未配置时的安全运行时默认值（仅用于开发/测试，生产必须覆盖）
_DEV_AUTH_SECRET_FALLBACK = "weekly-scorer-v2-dev-fallback-secret-" + secrets.token_hex(8)
_DEV_ADMIN_PASSWORD_FALLBACK = "admin123"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./weekly_scorer.db"

    MIMO_API_KEY: str = ""
    MIMO_BASE_URL: str = "https://token-plan-cn.xiaomimimo.com/v1"

    # Ark（豆包）- 当前使用
    ARK_API_KEY: str = ""
    ARK_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/plan/v3"

    # DeepSeek（备用，需要时取消注释）
    # DEEPSEEK_API_KEY: str = ""
    # DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    SCORING_MODEL: str = "doubao-seed-2.0-pro"
    # 视觉模型：用于解析一周小结图片。留空则回退到 SCORING_MODEL（仅支持视觉模型时才能解析图片）
    # 可配置如 "doubao-pro-vision-250615" / "gpt-4o-mini" / 或 Ark/OpenAI 兼容的视觉模型 endpoint
    VISION_MODEL: str = ""
    SCORING_TEMPERATURE: float = 0.3
    AI_PROVIDER: str = "ark"

    # AI 请求超时配置（秒）
    AI_TIMEOUT: int = 60
    AI_CONNECT_TIMEOUT: int = 10

    APP_TITLE: str = "智友辰周任务汇总系统"
    APP_VERSION: str = "2.11.0"
    TEMPLATE_DIR: str = "./templates"

    # ⚠ 生产环境必须在 .env 中覆盖以下三项
    AUTH_SECRET_KEY: str = _SENTINEL_AUTH_SECRET
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = _SENTINEL_ADMIN_PASSWORD
    CORS_ALLOW_ORIGINS: str = "http://localhost:3001,http://127.0.0.1:3001,http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # 忽略 .env 中未定义的字段，方便自由注释/启用配置
    )


_settings = None


def _resolve_sensitive_defaults(settings: Settings) -> None:
    """
    若检测到使用默认标记值：
    1. 回退到一个安全的运行时默认值（避免空值让应用崩溃）
    2. 通过 logger + warnings 警告开发者在 .env 中覆盖
    """
    logger = logging.getLogger("weekly_scorer")
    is_sentinel_auth = settings.AUTH_SECRET_KEY in (_SENTINEL_AUTH_SECRET, "")
    is_sentinel_admin = settings.ADMIN_PASSWORD in (_SENTINEL_ADMIN_PASSWORD, "", "admin123")

    if is_sentinel_auth:
        settings.AUTH_SECRET_KEY = _DEV_AUTH_SECRET_FALLBACK
        msg = (
            "[config] AUTH_SECRET_KEY 使用运行时默认值（仅供开发/测试）。"
            "生产环境请在 .env 中设置 AUTH_SECRET_KEY=<强随机密钥>"
        )
        logger.warning(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)

    if is_sentinel_admin:
        settings.ADMIN_PASSWORD = _DEV_ADMIN_PASSWORD_FALLBACK
        msg = (
            "[config] ADMIN_PASSWORD 使用运行时默认值（仅供开发/测试）。"
            "生产环境请在 .env 中设置 ADMIN_PASSWORD=<强密码>"
        )
        logger.warning(msg)
        warnings.warn(msg, RuntimeWarning, stacklevel=2)


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _resolve_sensitive_defaults(_settings)
    return _settings
