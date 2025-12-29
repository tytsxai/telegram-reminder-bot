"""配置管理模块"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    # Telegram Bot
    BOT_TOKEN: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./reminders.db"
    
    # Timezone
    TIMEZONE: str = "Asia/Shanghai"
    
    # AI 预留配置
    AI_API_KEY: Optional[str] = None
    AI_MODEL: Optional[str] = None
    AI_BASE_URL: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
