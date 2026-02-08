"""main 模块关键启动/关闭路径测试。"""

from __future__ import annotations

import asyncio
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
        await app_main.post_shutdown(application)
    finally:
        monkeypatch.setattr(settings, "HEALTHCHECK_ENABLED", False)
