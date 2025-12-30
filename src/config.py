"""配置管理模块"""

from typing import Optional

import pytz
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _sqlite_url_to_path(url: str) -> str:
    """将常见 sqlite URL 转为路径"""
    prefixes = (
        "sqlite+aiosqlite:////",
        "sqlite:////",
        "sqlite+aiosqlite:///",
        "sqlite:///",
    )
    for prefix in prefixes:
        if url.startswith(prefix):
            return url[len(prefix) :]
    return url


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Telegram Bot
    BOT_TOKEN: str = ""

    # Database
    DATABASE_PATH: str = "reminders.db"
    DATABASE_URL: Optional[str] = None

    # Timezone
    TIMEZONE: str = "Asia/Shanghai"

    # AI 配置 (SiliconFlow / DeepSeek)
    AI_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    AI_BASE_URL: Optional[str] = None

    # 可选 AI 提供商配置
    AI_PROVIDER: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: Optional[str] = None
    ANTHROPIC_BASE_URL: Optional[str] = None

    # 运行与监控配置
    LOG_LEVEL: str = "INFO"
    SCHEDULER_INTERVAL_SECONDS: int = 30
    HEALTHCHECK_ENABLED: bool = False
    HEALTHCHECK_HOST: str = "127.0.0.1"
    HEALTHCHECK_PORT: int = 8080
    HEALTHCHECK_PATH: str = "/healthz"

    # 运行实例锁
    INSTANCE_LOCK_ENABLED: bool = True
    INSTANCE_LOCK_PATH: str = "reminder-bot.lock"

    @model_validator(mode="after")
    def _normalize_database_path(self) -> "Settings":
        if self.DATABASE_URL:
            self.DATABASE_PATH = _sqlite_url_to_path(self.DATABASE_URL)
        try:
            pytz.timezone(self.TIMEZONE)
        except Exception as exc:
            raise ValueError(f"Invalid TIMEZONE: {self.TIMEZONE}") from exc
        if self.SCHEDULER_INTERVAL_SECONDS <= 0:
            raise ValueError("SCHEDULER_INTERVAL_SECONDS must be > 0")
        if not (1 <= self.HEALTHCHECK_PORT <= 65535):
            raise ValueError("HEALTHCHECK_PORT must be between 1 and 65535")
        if not self.HEALTHCHECK_PATH.startswith("/"):
            raise ValueError("HEALTHCHECK_PATH must start with '/'")
        if self.INSTANCE_LOCK_PATH.strip() == "":
            raise ValueError("INSTANCE_LOCK_PATH must not be empty")
        return self


settings = Settings()
