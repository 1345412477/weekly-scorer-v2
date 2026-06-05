"""应用配置"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./weekly_scorer.db"

    MIMO_API_KEY: str = ""
    MIMO_BASE_URL: str = "https://token-plan-cn.xiaomimimo.com/v1"

    # Ark（豆包）- 当前使用
    ARK_API_KEY: str = "ark-59a63f24-995a-4532-bea0-1de221ef1594-59093"
    ARK_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/plan/v3"

    # DeepSeek（备用，需要时取消注释）
    # DEEPSEEK_API_KEY: str = "sk-24e2c6c1a9fd40cf9fab4af17e541bff"
    # DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"

    SCORING_MODEL: str = "doubao-seed-2.0-pro"
    SCORING_TEMPERATURE: float = 0.3
    AI_PROVIDER: str = "ark"
    
    # AI 请求超时配置（秒）
    AI_TIMEOUT: int = 60
    AI_CONNECT_TIMEOUT: int = 10

    APP_TITLE: str = "周报评分系统 v2"
    APP_VERSION: str = "2.1.0"
    DEBUG: bool = True
    TEMPLATE_DIR: str = "./templates"

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
