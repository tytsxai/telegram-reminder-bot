"""配置模块测试"""
import os
import pytest
from unittest.mock import patch


class TestSettings:
    """Settings 类测试"""
    
    def test_default_values(self):
        """测试默认值"""
        from src.config import Settings
        s = Settings()
        assert s.BOT_TOKEN == ""
        assert s.DATABASE_URL == "sqlite+aiosqlite:///./reminders.db"
        assert s.TIMEZONE == "Asia/Shanghai"
        assert s.AI_API_KEY is None
        assert s.AI_MODEL is None
        assert s.AI_BASE_URL is None
    
    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {
            "BOT_TOKEN": "test_token_123",
            "TIMEZONE": "UTC"
        }):
            from src.config import Settings
            s = Settings()
            assert s.BOT_TOKEN == "test_token_123"
            assert s.TIMEZONE == "UTC"
    
    def test_ai_config_optional(self):
        """测试 AI 配置可选"""
        with patch.dict(os.environ, {
            "AI_API_KEY": "sk-test",
            "AI_MODEL": "gpt-4"
        }):
            from src.config import Settings
            s = Settings()
            assert s.AI_API_KEY == "sk-test"
            assert s.AI_MODEL == "gpt-4"
    
    def test_database_url_custom(self):
        """测试自定义数据库 URL"""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://localhost/test"
        }):
            from src.config import Settings
            s = Settings()
            assert s.DATABASE_URL == "postgresql://localhost/test"


class TestSettingsInstance:
    """settings 实例测试"""
    
    def test_settings_singleton(self):
        """测试 settings 实例存在"""
        from src.config import settings
        assert settings is not None
        assert hasattr(settings, 'BOT_TOKEN')
        assert hasattr(settings, 'DATABASE_URL')
        assert hasattr(settings, 'TIMEZONE')
