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
            "BOT_TOKEN",
            "DATABASE_PATH",
            "DATABASE_URL",
            "TIMEZONE",
            "AI_API_KEY",
            "AI_MODEL",
            "AI_BASE_URL",
            "AI_PROVIDER",
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
            "OPENAI_BASE_URL",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_MODEL",
            "ANTHROPIC_BASE_URL",
            "LOG_LEVEL",
            "SCHEDULER_INTERVAL_SECONDS",
            "IMAGE_TAG",
            "SCHEDULER_BATCH_SIZE",
            "SCHEDULER_LOCK_SECONDS",
            "SCHEDULER_SEND_CONCURRENCY",
            "SCHEDULER_SEND_TIMEOUT_SECONDS",
            "DROP_PENDING_UPDATES",
            "DB_QUICK_CHECK_ON_STARTUP",
            "HEALTHCHECK_ENABLED",
            "HEALTHCHECK_HOST",
            "HEALTHCHECK_PORT",
            "HEALTHCHECK_PATH",
            "HEALTHCHECK_CHECK_TIMEOUT_SECONDS",
        ]
        clean_env = {k: "" for k in env_keys if k in os.environ}
        with patch.dict(os.environ, clean_env, clear=False):
            # 移除环境变量
            for k in env_keys:
                os.environ.pop(k, None)
            from src.config import Settings

            s = Settings(_env_file=None)
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
        assert s.SCHEDULER_BATCH_SIZE == 200
        assert s.SCHEDULER_LOCK_SECONDS == 120
        assert s.SCHEDULER_SEND_CONCURRENCY == 5
        assert s.SCHEDULER_SEND_TIMEOUT_SECONDS == 30
        assert s.DROP_PENDING_UPDATES is False
        assert s.DB_QUICK_CHECK_ON_STARTUP is True
        assert s.IMAGE_TAG is None
        assert s.HEALTHCHECK_ENABLED is True
        assert s.HEALTHCHECK_HOST == "127.0.0.1"
        assert s.HEALTHCHECK_PORT == 8080
        assert s.HEALTHCHECK_PATH == "/healthz"
        assert s.HEALTHCHECK_CHECK_TIMEOUT_SECONDS == 3.0

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

    def test_log_level_normalize(self):
        """测试日志级别标准化"""
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}):
            from src.config import Settings

            s = Settings()
            assert s.LOG_LEVEL == "DEBUG"

    def test_log_level_invalid(self):
        """测试非法日志级别"""
        with patch.dict(os.environ, {"LOG_LEVEL": "VERBOSE"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "LOG_LEVEL" in str(excinfo.value)


class TestSettingsInstance:
    """settings 实例测试"""

    def test_settings_singleton(self):
        """测试 settings 实例存在"""
        from src.config import settings

        assert settings is not None
        assert hasattr(settings, "BOT_TOKEN")
        assert hasattr(settings, "DATABASE_PATH")
        assert hasattr(settings, "TIMEZONE")

    def test_scheduler_interval_invalid(self):
        """测试非法调度间隔"""
        with patch.dict(os.environ, {"SCHEDULER_INTERVAL_SECONDS": "0"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_INTERVAL_SECONDS" in str(excinfo.value)

    def test_scheduler_batch_size_invalid(self):
        """测试非法调度批量大小"""
        with patch.dict(os.environ, {"SCHEDULER_BATCH_SIZE": "0"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_BATCH_SIZE" in str(excinfo.value)

    def test_scheduler_lock_seconds_invalid(self):
        """测试非法调度锁定时长"""
        with patch.dict(os.environ, {"SCHEDULER_LOCK_SECONDS": "0"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_LOCK_SECONDS" in str(excinfo.value)

    def test_scheduler_send_concurrency_invalid(self):
        """测试非法发送并发数"""
        with patch.dict(os.environ, {"SCHEDULER_SEND_CONCURRENCY": "0"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_SEND_CONCURRENCY" in str(excinfo.value)

    def test_scheduler_send_timeout_invalid(self):
        """测试非法发送超时"""
        with patch.dict(os.environ, {"SCHEDULER_SEND_TIMEOUT_SECONDS": "0"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_SEND_TIMEOUT_SECONDS" in str(excinfo.value)

    def test_scheduler_send_timeout_too_large(self):
        """测试发送超时上限"""
        with patch.dict(os.environ, {"SCHEDULER_SEND_TIMEOUT_SECONDS": "301"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_SEND_TIMEOUT_SECONDS" in str(excinfo.value)

    def test_scheduler_lock_less_than_send_timeout(self):
        """测试锁时间必须覆盖发送超时"""
        with patch.dict(
            os.environ,
            {
                "SCHEDULER_LOCK_SECONDS": "20",
                "SCHEDULER_SEND_TIMEOUT_SECONDS": "30",
            },
        ):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_LOCK_SECONDS" in str(excinfo.value)

    def test_healthcheck_port_invalid_low(self):
        """测试非法端口号（过低）"""
        with patch.dict(os.environ, {"HEALTHCHECK_PORT": "0"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "HEALTHCHECK_PORT" in str(excinfo.value)

    def test_healthcheck_port_invalid_high(self):
        """测试非法端口号（过高）"""
        with patch.dict(os.environ, {"HEALTHCHECK_PORT": "70000"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "HEALTHCHECK_PORT" in str(excinfo.value)

    def test_healthcheck_path_invalid(self):
        """测试非法健康检查路径"""
        with patch.dict(os.environ, {"HEALTHCHECK_PATH": "healthz"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "HEALTHCHECK_PATH" in str(excinfo.value)

    def test_healthcheck_path_with_space(self):
        """测试健康检查路径包含空格"""
        with patch.dict(os.environ, {"HEALTHCHECK_PATH": "/health z"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "HEALTHCHECK_PATH" in str(excinfo.value)

    def test_healthcheck_check_timeout_invalid(self):
        """测试非法健康检查超时"""
        with patch.dict(os.environ, {"HEALTHCHECK_CHECK_TIMEOUT_SECONDS": "0"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "HEALTHCHECK_CHECK_TIMEOUT_SECONDS" in str(excinfo.value)

    def test_database_path_empty(self):
        """测试空数据库路径"""
        with patch.dict(os.environ, {"DATABASE_PATH": "   "}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "DATABASE_PATH" in str(excinfo.value)

    def test_instance_lock_path_empty(self):
        """测试空实例锁路径"""
        with patch.dict(os.environ, {"INSTANCE_LOCK_PATH": "   "}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "INSTANCE_LOCK_PATH" in str(excinfo.value)

    def test_scheduler_send_concurrency_too_large(self):
        """测试发送并发数过大"""
        with patch.dict(os.environ, {"SCHEDULER_SEND_CONCURRENCY": "51"}):
            from src.config import Settings

            with pytest.raises(Exception) as excinfo:
                Settings()
            assert "SCHEDULER_SEND_CONCURRENCY" in str(excinfo.value)
