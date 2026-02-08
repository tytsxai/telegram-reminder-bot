"""配置管理模块

使用 pydantic-settings 从环境变量和 .env 文件加载配置。
"""

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

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
    SCHEDULER_BATCH_SIZE: int = 200
    SCHEDULER_LOCK_SECONDS: int = 120
    SCHEDULER_SEND_CONCURRENCY: int = 5
    DROP_PENDING_UPDATES: bool = False
    IMAGE_TAG: Optional[str] = None
    DB_QUICK_CHECK_ON_STARTUP: bool = True
    HEALTHCHECK_ENABLED: bool = False
    HEALTHCHECK_HOST: str = "127.0.0.1"
    HEALTHCHECK_PORT: int = 8080
    HEALTHCHECK_PATH: str = "/healthz"
    HEALTHCHECK_CHECK_TIMEOUT_SECONDS: float = 3.0

    # 运行实例锁
    INSTANCE_LOCK_ENABLED: bool = True
    INSTANCE_LOCK_PATH: str = "reminder-bot.lock"

    @model_validator(mode="after")
    def _normalize_database_path(self) -> "Settings":
        if self.DATABASE_URL:
            self.DATABASE_PATH = _sqlite_url_to_path(self.DATABASE_URL)
        if (self.DATABASE_PATH or "").strip() == "":
            raise ValueError("DATABASE_PATH must not be empty")
        self.LOG_LEVEL = (self.LOG_LEVEL or "INFO").strip().upper()
        try:
            pytz.timezone(self.TIMEZONE)
        except Exception as exc:
            raise ValueError(f"Invalid TIMEZONE: {self.TIMEZONE}") from exc
        if self.LOG_LEVEL not in {
            "CRITICAL",
            "ERROR",
            "WARNING",
            "INFO",
            "DEBUG",
            "NOTSET",
        }:
            raise ValueError(
                "LOG_LEVEL must be one of: "
                "CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET"
            )
        if self.SCHEDULER_INTERVAL_SECONDS <= 0:
            raise ValueError("SCHEDULER_INTERVAL_SECONDS must be > 0")
        if self.SCHEDULER_BATCH_SIZE <= 0:
            raise ValueError("SCHEDULER_BATCH_SIZE must be > 0")
        if self.SCHEDULER_LOCK_SECONDS <= 0:
            raise ValueError("SCHEDULER_LOCK_SECONDS must be > 0")
        if self.SCHEDULER_SEND_CONCURRENCY <= 0:
            raise ValueError("SCHEDULER_SEND_CONCURRENCY must be > 0")
        if self.SCHEDULER_SEND_CONCURRENCY > 50:
            raise ValueError("SCHEDULER_SEND_CONCURRENCY must be <= 50")
        if not (1 <= self.HEALTHCHECK_PORT <= 65535):
            raise ValueError("HEALTHCHECK_PORT must be between 1 and 65535")
        if not self.HEALTHCHECK_PATH.startswith("/"):
            raise ValueError("HEALTHCHECK_PATH must start with '/'")
        if " " in self.HEALTHCHECK_PATH:
            raise ValueError("HEALTHCHECK_PATH must not contain spaces")
        if self.HEALTHCHECK_CHECK_TIMEOUT_SECONDS <= 0:
            raise ValueError("HEALTHCHECK_CHECK_TIMEOUT_SECONDS must be > 0")
        if self.HEALTHCHECK_CHECK_TIMEOUT_SECONDS > 30:
            raise ValueError("HEALTHCHECK_CHECK_TIMEOUT_SECONDS must be <= 30")
        if self.INSTANCE_LOCK_PATH.strip() == "":
            raise ValueError("INSTANCE_LOCK_PATH must not be empty")
        return self


settings = Settings()
