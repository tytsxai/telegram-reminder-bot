"""Preflight script tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.preflight import run_preflight


def test_load_config_defaults_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("BOT_TOKEN=abc\nDATABASE_PATH=tmp.db\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    from scripts import preflight

    bot_token, db_path, warnings = preflight._load_config_defaults()
    assert bot_token == "abc"
    assert db_path == "tmp.db"
    assert warnings == []


@pytest.mark.asyncio
async def test_preflight_fails_when_token_missing(tmp_path):
    db_path = tmp_path / "test.db"
    result = await run_preflight(bot_token="", db_path=str(db_path))
    assert result.ok is False
    assert any("BOT_TOKEN" in err for err in result.errors)


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
    result = await run_preflight(bot_token="token", db_path=str(db_path))
    assert result.ok is True
    assert result.errors == []


@pytest.mark.asyncio
async def test_preflight_skip_runtime_check(tmp_path):
    db_path = tmp_path / "skip.db"
    result = await run_preflight(
        bot_token="token",
        db_path=str(db_path),
        skip_db_runtime_check=True,
    )
    assert result.ok is True
    assert result.errors == []


def test_preflight_cli_entrypoint(tmp_path):
    db_path = tmp_path / "cli.db"
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "preflight.py"),
            "--bot-token",
            "token",
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
