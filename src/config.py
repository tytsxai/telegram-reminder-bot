"""配置管理模块"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import model_validator


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

    # AI 预留配置
    AI_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    AI_BASE_URL: Optional[str] = None

    @model_validator(mode="after")
    def _normalize_database_path(self) -> "Settings":
        if self.DATABASE_URL:
            self.DATABASE_PATH = _sqlite_url_to_path(self.DATABASE_URL)
        return self


settings = Settings()
