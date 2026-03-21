"""Preflight script tests."""

from __future__ import annotations

import subprocess
import sys
import socket
from pathlib import Path

import pytest

from scripts.preflight import run_preflight


def test_load_config_defaults_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("BOT_TOKEN=abc\nDATABASE_PATH=tmp.db\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from scripts import preflight

    (
        bot_token,
        db_path,
        lock_enabled,
        lock_path,
        health_enabled,
        health_host,
        health_port,
        quick_check,
        log_level,
        warnings,
        errors,
    ) = preflight._load_config_defaults()
    assert bot_token == "abc"
    assert db_path == "tmp.db"
    assert lock_enabled is True
    assert lock_path == "reminder-bot.lock"
    assert health_enabled is True
    assert health_host == "127.0.0.1"
    assert health_port == 8080
    assert quick_check is True
    assert log_level == "INFO"
    assert warnings == []
    assert errors == []


@pytest.mark.asyncio
async def test_preflight_fails_when_token_missing(tmp_path):
    db_path = tmp_path / "test.db"
    result = await run_preflight(bot_token="", db_path=str(db_path))
    assert result.ok is False
    assert any("BOT_TOKEN" in err for err in result.errors)


@pytest.mark.asyncio
async def test_preflight_fails_when_token_format_invalid(tmp_path):
    db_path = tmp_path / "test.db"
    result = await run_preflight(bot_token="token", db_path=str(db_path))
    assert result.ok is False
    assert any("BOT_TOKEN format is invalid" in err for err in result.errors)


@pytest.mark.asyncio
async def test_preflight_fails_when_db_path_is_directory(tmp_path):
    db_dir = tmp_path / "dbdir"
    db_dir.mkdir()
    result = await run_preflight(bot_token="token", db_path=str(db_dir))
    assert result.ok is False
    assert any("directory" in err.lower() for err in result.errors)


@pytest.mark.asyncio
async def test_preflight_passes_with_valid_inputs(tmp_path):
    db_path = tmp_path / "ok.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        healthcheck_enabled=True,
    )
    assert result.ok is True
    assert result.errors == []


@pytest.mark.asyncio
async def test_preflight_skip_runtime_check(tmp_path):
    db_path = tmp_path / "skip.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        skip_db_runtime_check=True,
        healthcheck_enabled=True,
    )
    assert result.ok is True
    assert result.errors == []


@pytest.mark.asyncio
async def test_preflight_reports_instance_lock_error(tmp_path):
    db_path = tmp_path / "ok.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        skip_db_runtime_check=True,
        instance_lock_enabled=True,
        instance_lock_path="   ",
    )
    assert result.ok is False
    assert any("INSTANCE_LOCK_PATH" in err for err in result.errors)


@pytest.mark.asyncio
async def test_preflight_security_warnings_include_env_permissions(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOT_TOKEN=123456:abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8"
    )
    env_file.chmod(0o644)

    db_path = tmp_path / "ok.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        skip_db_runtime_check=True,
        healthcheck_enabled=True,
    )
    assert result.ok is True
    assert any(".env permissions" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_preflight_security_warnings_include_duplicate_env_keys(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOT_TOKEN=123456:abcdefghijklmnopqrstuvwxyz\n"
        "HEALTHCHECK_ENABLED=true\n"
        "HEALTHCHECK_ENABLED=false\n",
        encoding="utf-8",
    )

    db_path = tmp_path / "ok.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        skip_db_runtime_check=True,
        healthcheck_enabled=True,
    )
    assert result.ok is True
    assert any("duplicate keys" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_preflight_config_errors_are_hard_fail(tmp_path):
    db_path = tmp_path / "ok.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        skip_db_runtime_check=True,
        config_errors=["Settings validation failed: Invalid TIMEZONE"],
    )
    assert result.ok is False
    assert any("Settings validation failed" in err for err in result.errors)


@pytest.mark.asyncio
async def test_preflight_runtime_warnings(tmp_path):
    db_path = tmp_path / "ok.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        skip_db_runtime_check=True,
        healthcheck_enabled=False,
        db_quick_check_on_startup=False,
        instance_lock_enabled=False,
        log_level="DEBUG",
    )
    assert result.ok is True
    assert any("HEALTHCHECK_ENABLED=false" in w for w in result.warnings)
    assert any("DB_QUICK_CHECK_ON_STARTUP=false" in w for w in result.warnings)
    assert any("INSTANCE_LOCK_ENABLED=false" in w for w in result.warnings)
    assert any("LOG_LEVEL=DEBUG" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_preflight_fails_when_healthcheck_port_is_in_use(tmp_path):
    db_path = tmp_path / "ok.db"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    busy_port = sock.getsockname()[1]
    try:
        result = await run_preflight(
            bot_token="123456:abcdefghijklmnopqrstuvwxyz",
            db_path=str(db_path),
            skip_db_runtime_check=True,
            healthcheck_enabled=True,
            healthcheck_host="127.0.0.1",
            healthcheck_port=busy_port,
        )
    finally:
        sock.close()
    assert result.ok is False
    assert any("Healthcheck bind failed" in err for err in result.errors)


@pytest.mark.asyncio
async def test_preflight_fails_when_healthcheck_port_invalid(tmp_path):
    db_path = tmp_path / "ok.db"
    result = await run_preflight(
        bot_token="123456:abcdefghijklmnopqrstuvwxyz",
        db_path=str(db_path),
        skip_db_runtime_check=True,
        healthcheck_enabled=True,
        healthcheck_port=0,
    )
    assert result.ok is False
    assert any("HEALTHCHECK_PORT must be between 1 and 65535" in err for err in result.errors)


def test_preflight_cli_strict_warnings_fails(tmp_path):
    db_path = tmp_path / "cli-strict.db"
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "preflight.py"),
            "--bot-token",
            "123456:abcdefghijklmnopqrstuvwxyz",
            "--db-path",
            str(db_path),
            "--skip-db-runtime-check",
            "--healthcheck-enabled",
            "false",
            "--strict-warnings",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert completed.returncode == 1
    assert "strict warnings enabled" in completed.stdout


def test_preflight_cli_entrypoint(tmp_path):
    db_path = tmp_path / "cli.db"
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "preflight.py"),
            "--bot-token",
            "123456:abcdefghijklmnopqrstuvwxyz",
            "--db-path",
            str(db_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert completed.returncode == 0
    assert '"ok": true' in completed.stdout
