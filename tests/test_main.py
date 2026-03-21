"""main 模块关键启动/关闭路径测试。"""

from __future__ import annotations

import asyncio
import signal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import main as app_main
from src.config import settings


@pytest.mark.asyncio
async def test_post_init_raises_when_db_init_fails(monkeypatch):
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", False)
    monkeypatch.setattr(
        app_main.db, "init_db", AsyncMock(side_effect=RuntimeError("db"))
    )
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))
    with pytest.raises(RuntimeError):
        await app_main.post_init(application)


@pytest.mark.asyncio
async def test_post_shutdown_tolerates_stop_errors(monkeypatch):
    scheduler_mock = MagicMock()
    scheduler_mock.stop.side_effect = RuntimeError("scheduler")
    health_mock = MagicMock()
    health_mock.stop = AsyncMock(side_effect=RuntimeError("health"))
    lock_mock = MagicMock()

    monkeypatch.setattr(app_main, "scheduler", scheduler_mock)
    monkeypatch.setattr(app_main, "health_server", health_mock)
    monkeypatch.setattr(app_main, "instance_lock", lock_mock)

    await app_main.post_shutdown(SimpleNamespace())

    lock_mock.release.assert_called_once()
    assert app_main.scheduler is None
    assert app_main.health_server is None
    assert app_main.instance_lock is None


@pytest.mark.asyncio
async def test_post_init_stops_scheduler_when_healthcheck_fails(monkeypatch):
    monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", True)
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", False)
    monkeypatch.setattr(app_main.db, "init_db", AsyncMock())
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))

    scheduler_mock = MagicMock()
    scheduler_mock.start = MagicMock()
    scheduler_mock.stop = MagicMock()

    class _BrokenHealthServer:
        async def start(self):
            raise RuntimeError("health")

    monkeypatch.setattr(app_main, "SchedulerService", lambda *_args: scheduler_mock)
    monkeypatch.setattr(
        app_main, "HealthCheckServer", lambda **_kwargs: _BrokenHealthServer()
    )

    try:
        with pytest.raises(RuntimeError):
            await app_main.post_init(application)
        scheduler_mock.stop.assert_called_once()
        assert app_main.scheduler is None
    finally:
        monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", False)


@pytest.mark.asyncio
async def test_post_init_raises_when_quick_check_fails(monkeypatch):
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", True)
    monkeypatch.setattr(app_main.db, "init_db", AsyncMock())
    monkeypatch.setattr(app_main.db, "quick_check", AsyncMock(return_value=False))
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))

    with pytest.raises(RuntimeError):
        await app_main.post_init(application)


@pytest.mark.asyncio
async def test_healthcheck_db_timeout_marks_unhealthy(monkeypatch):
    monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", True)
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", False)
    monkeypatch.setattr(settings, "HEALTHCHECK_CHECK_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(app_main.db, "init_db", AsyncMock())

    async def _slow_ping():
        await asyncio.sleep(0.05)
        return True

    monkeypatch.setattr(app_main.db, "ping", _slow_ping)
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))

    scheduler_mock = MagicMock()
    scheduler_mock.start = MagicMock()
    scheduler_mock.stop = MagicMock()
    scheduler_mock.is_healthy.return_value = True
    scheduler_mock.health_snapshot.return_value = {"running": True}

    class _CapturingHealthServer:
        def __init__(self, **kwargs):
            self.check = kwargs["check"]

        async def start(self):
            return None

        async def stop(self):
            return None

    created = {}

    def _server_factory(**kwargs):
        server = _CapturingHealthServer(**kwargs)
        created["server"] = server
        return server

    monkeypatch.setattr(app_main, "SchedulerService", lambda *_args: scheduler_mock)
    monkeypatch.setattr(app_main, "HealthCheckServer", _server_factory)

    try:
        await app_main.post_init(application)
        payload = await created["server"].check()
        assert payload["ok"] is False
        assert payload["status"] == "db_error"
        assert payload["db_ok"] is False
        assert payload["db_status"] == "timeout"
        await app_main.post_shutdown(application)
    finally:
        monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", False)


@pytest.mark.asyncio
async def test_healthcheck_db_ping_false_marks_unhealthy(monkeypatch):
    monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", True)
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", False)
    monkeypatch.setattr(app_main.db, "init_db", AsyncMock())
    monkeypatch.setattr(app_main.db, "ping", AsyncMock(return_value=False))
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))

    scheduler_mock = MagicMock()
    scheduler_mock.start = MagicMock()
    scheduler_mock.stop = MagicMock()
    scheduler_mock.is_healthy.return_value = True
    scheduler_mock.health_snapshot.return_value = {"running": True}

    class _CapturingHealthServer:
        def __init__(self, **kwargs):
            self.check = kwargs["check"]

        async def start(self):
            return None

        async def stop(self):
            return None

    created = {}

    def _server_factory(**kwargs):
        server = _CapturingHealthServer(**kwargs)
        created["server"] = server
        return server

    monkeypatch.setattr(app_main, "SchedulerService", lambda *_args: scheduler_mock)
    monkeypatch.setattr(app_main, "HealthCheckServer", _server_factory)

    try:
        await app_main.post_init(application)
        payload = await created["server"].check()
        assert payload["ok"] is False
        assert payload["status"] == "db_error"
        assert payload["db_status"] == "error"
        await app_main.post_shutdown(application)
    finally:
        monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", False)


@pytest.mark.asyncio
async def test_healthcheck_scheduler_claim_failure_marks_unhealthy(monkeypatch):
    monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", True)
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", False)
    monkeypatch.setattr(app_main.db, "init_db", AsyncMock())
    monkeypatch.setattr(app_main.db, "ping", AsyncMock(return_value=True))
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))

    scheduler_mock = MagicMock()
    scheduler_mock.start = MagicMock()
    scheduler_mock.stop = MagicMock()
    scheduler_mock.is_healthy.return_value = False
    scheduler_mock.health_snapshot.return_value = {
        "running": True,
        "consecutive_claim_failures": 3,
    }

    class _CapturingHealthServer:
        def __init__(self, **kwargs):
            self.check = kwargs["check"]

        async def start(self):
            return None

        async def stop(self):
            return None

    created = {}

    def _server_factory(**kwargs):
        server = _CapturingHealthServer(**kwargs)
        created["server"] = server
        return server

    monkeypatch.setattr(app_main, "SchedulerService", lambda *_args: scheduler_mock)
    monkeypatch.setattr(app_main, "HealthCheckServer", _server_factory)

    try:
        await app_main.post_init(application)
        payload = await created["server"].check()
        assert payload["ok"] is False
        assert payload["status"] == "scheduler_unhealthy"
        assert payload["scheduler_status"] == "claim_failed"
        await app_main.post_shutdown(application)
    finally:
        monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", False)


@pytest.mark.asyncio
async def test_healthcheck_scheduler_processing_failure_marks_unhealthy(monkeypatch):
    monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", True)
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", False)
    monkeypatch.setattr(app_main.db, "init_db", AsyncMock())
    monkeypatch.setattr(app_main.db, "ping", AsyncMock(return_value=True))
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))

    scheduler_mock = MagicMock()
    scheduler_mock.start = MagicMock()
    scheduler_mock.stop = MagicMock()
    scheduler_mock.is_healthy.return_value = False
    scheduler_mock.health_snapshot.return_value = {
        "running": True,
        "consecutive_claim_failures": 0,
        "consecutive_process_failures": 10,
    }

    class _CapturingHealthServer:
        def __init__(self, **kwargs):
            self.check = kwargs["check"]

        async def start(self):
            return None

        async def stop(self):
            return None

    created = {}

    def _server_factory(**kwargs):
        server = _CapturingHealthServer(**kwargs)
        created["server"] = server
        return server

    monkeypatch.setattr(app_main, "SchedulerService", lambda *_args: scheduler_mock)
    monkeypatch.setattr(app_main, "HealthCheckServer", _server_factory)

    try:
        await app_main.post_init(application)
        payload = await created["server"].check()
        assert payload["ok"] is False
        assert payload["status"] == "scheduler_unhealthy"
        assert payload["scheduler_status"] == "processing_failed"
        await app_main.post_shutdown(application)
    finally:
        monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", False)


@pytest.mark.asyncio
async def test_healthcheck_db_error_marks_unhealthy(monkeypatch):
    monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", True)
    monkeypatch.setattr(settings, "DB_QUICK_CHECK_ON_STARTUP", False)
    monkeypatch.setattr(app_main.db, "init_db", AsyncMock())

    async def _broken_ping():
        raise RuntimeError("db connection lost")

    monkeypatch.setattr(app_main.db, "ping", _broken_ping)
    application = SimpleNamespace(bot=SimpleNamespace(set_my_commands=AsyncMock()))

    scheduler_mock = MagicMock()
    scheduler_mock.start = MagicMock()
    scheduler_mock.stop = MagicMock()
    scheduler_mock.is_healthy.return_value = True
    scheduler_mock.health_snapshot.return_value = {"running": True}

    class _CapturingHealthServer:
        def __init__(self, **kwargs):
            self.check = kwargs["check"]

        async def start(self):
            return None

        async def stop(self):
            return None

    created = {}

    def _server_factory(**kwargs):
        server = _CapturingHealthServer(**kwargs)
        created["server"] = server
        return server

    monkeypatch.setattr(app_main, "SchedulerService", lambda *_args: scheduler_mock)
    monkeypatch.setattr(app_main, "HealthCheckServer", _server_factory)

    try:
        await app_main.post_init(application)
        payload = await created["server"].check()
        assert payload["ok"] is False
        assert payload["status"] == "db_error"
        assert payload["db_status"] == "error"
        await app_main.post_shutdown(application)
    finally:
        monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", False)


def test_main_run_polling_uses_stop_signals(monkeypatch):
    old_app = getattr(app_main, "app", None)
    monkeypatch.setattr(settings, "BOT_TOKEN", "123456:abcdefghijklmnopqrstuvwxyz")
    monkeypatch.setattr(settings, "INSTANCE_LOCK_ENABLED", False)
    monkeypatch.setattr(app_main, "validate_db_path", lambda: None)
    monkeypatch.setattr(app_main, "log_startup_settings", lambda: None)
    monkeypatch.setattr(app_main, "register_handlers", lambda *_args: None)

    builder = MagicMock()
    app = MagicMock()
    builder.token.return_value = builder
    builder.post_init.return_value = builder
    builder.post_shutdown.return_value = builder
    builder.build.return_value = app

    application_cls = MagicMock()
    application_cls.builder.return_value = builder
    monkeypatch.setattr(app_main, "Application", application_cls)

    try:
        app_main.main()

        app.run_polling.assert_called_once()
        kwargs = app.run_polling.call_args.kwargs
        assert kwargs["drop_pending_updates"] is settings.DROP_PENDING_UPDATES
        assert signal.SIGINT in kwargs["stop_signals"]
        assert signal.SIGTERM in kwargs["stop_signals"]
    finally:
        app_main.app = old_app
