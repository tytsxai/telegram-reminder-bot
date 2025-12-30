"""配置模块测试"""

import os
from unittest.mock import patch

import pytest


class TestSettings:
    """Settings 类测试"""

    def test_default_values(self):
        """测试默认值"""
        # 清除可能存在的环境变量以测试真正的默认值
        env_keys = [
            "BOT_TOKEN", "DATABASE_PATH", "DATABASE_URL", "TIMEZONE",
            "AI_API_KEY", "AI_MODEL", "AI_BASE_URL", "AI_PROVIDER",
            "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
            "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL",
            "LOG_LEVEL", "SCHEDULER_INTERVAL_SECONDS",
            "HEALTHCHECK_ENABLED", "HEALTHCHECK_HOST", "HEALTHCHECK_PORT", "HEALTHCHECK_PATH",
        ]
        clean_env = {k: "" for k in env_keys if k in os.environ}
        with patch.dict(os.environ, clean_env, clear=False):
            # 移除环境变量
            for k in env_keys:
                os.environ.pop(k, None)
            from src.config import Settings

            s = Settings()
        assert s.BOT_TOKEN == ""
        assert s.DATABASE_PATH == "reminders.db"
        assert s.DATABASE_URL is None
        assert s.TIMEZONE == "Asia/Shanghai"
        assert s.AI_API_KEY is None
        assert s.AI_MODEL is None
        assert s.AI_BASE_URL is None
        assert s.AI_PROVIDER is None
        assert s.OPENAI_API_KEY is None
        assert s.OPENAI_MODEL is None
        assert s.OPENAI_BASE_URL is None
        assert s.ANTHROPIC_API_KEY is None
        assert s.ANTHROPIC_MODEL is None
        assert s.ANTHROPIC_BASE_URL is None
        assert s.LOG_LEVEL == "INFO"
        assert s.SCHEDULER_INTERVAL_SECONDS == 30
        assert s.HEALTHCHECK_ENABLED is False
        assert s.HEALTHCHECK_HOST == "127.0.0.1"
        assert s.HEALTHCHECK_PORT == 8080
        assert s.HEALTHCHECK_PATH == "/healthz"

    def test_env_override(self):
        """测试环境变量覆盖"""
        with patch.dict(os.environ, {"BOT_TOKEN": "test_token_123", "TIMEZONE": "UTC"}):
            from src.config import Settings

            s = Settings()
            assert s.BOT_TOKEN == "test_token_123"
            assert s.TIMEZONE == "UTC"

    def test_ai_config_optional(self):
        """测试 AI 配置可选"""
        with patch.dict(os.environ, {"AI_API_KEY": "sk-test", "AI_MODEL": "gpt-4"}):
            from src.config import Settings

            s = Settings()
            assert s.AI_API_KEY == "sk-test"
            assert s.AI_MODEL == "gpt-4"

    def test_validation_timezone_invalid(self):
        """测试非法时区校验"""
        with patch.dict(os.environ, {"TIMEZONE": "Invalid/Timezone"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "Invalid TIMEZONE" in str(excinfo.value)

    def test_database_path_custom(self):
        """测试自定义数据库路径"""
        with patch.dict(os.environ, {"DATABASE_PATH": "/tmp/test.db"}):
            from src.config import Settings

            s = Settings()
            assert s.DATABASE_PATH == "/tmp/test.db"

    def test_database_url_compat(self):
        """测试 DATABASE_URL 兼容"""
        with patch.dict(
            os.environ, {"DATABASE_URL": "sqlite+aiosqlite:///./reminders.db"}
        ):
            from src.config import Settings

            s = Settings()
            assert s.DATABASE_PATH == "./reminders.db"


class TestSettingsInstance:
    """settings 实例测试"""

    def test_settings_singleton(self):
        """测试 settings 实例存在"""
        from src.config import settings

        assert settings is not None
        assert hasattr(settings, "BOT_TOKEN")
        assert hasattr(settings, "DATABASE_PATH")
        assert hasattr(settings, "TIMEZONE")
