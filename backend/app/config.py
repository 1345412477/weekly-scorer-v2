"""应用配置"""
import os
from pydantic_settings import BaseSettings


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

    APP_TITLE: str = "周报评分系统 v2"
    APP_VERSION: str = "2.1.0"
    DEBUG: bool = True
    TEMPLATE_DIR: str = "./templates"

    AUTH_SECRET_KEY: str = "weekly-scorer-v2-default-secret-please-override-in-dot-env"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    CORS_ALLOW_ORIGINS: str = "http://localhost:3001,http://127.0.0.1:3001,http://localhost:5173,http://127.0.0.1:5173"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略 .env 中未定义的字段，方便自由注释/启用配置


_settings = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
