"""Production preflight checks.

在上线前执行基础自检，快速发现会导致启动失败或运行不稳定的问题。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import Database


@dataclass
class PreflightResult:
    ok: bool
    errors: list[str]


def _load_config_defaults() -> tuple[str, str, list[str]]:
    """Load default BOT_TOKEN and DATABASE_PATH from app config/.env."""
    warnings: list[str] = []
    try:
        from src.config import Settings

        loaded = Settings()
        return loaded.BOT_TOKEN, loaded.DATABASE_PATH, warnings
    except Exception as exc:
        warnings.append(f"Failed to load settings defaults: {exc}")
        return os.getenv("BOT_TOKEN", ""), os.getenv("DATABASE_PATH", "reminders.db"), warnings


def _validate_token(bot_token: str) -> list[str]:
    errors: list[str] = []
    if not (bot_token or "").strip():
        errors.append("BOT_TOKEN is empty")
    return errors


def _validate_db_path(db_path: str) -> list[str]:
    errors: list[str] = []
    text = (db_path or "").strip()
    if text == "":
        errors.append("DATABASE_PATH is empty")
        return errors
    if text == ":memory:":
        return errors

    path = Path(text).expanduser()
    if path.exists() and path.is_dir():
        errors.append(f"DATABASE_PATH points to directory: {path}")
        return errors

    parent = path.parent if str(path.parent) not in ("", ".") else Path(".")
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        errors.append(f"Failed to create database directory {parent}: {exc}")
        return errors

    if not os.access(parent, os.W_OK):
        errors.append(f"Database directory not writable: {parent}")
    return errors


async def _validate_db_runtime(db_path: str) -> list[str]:
    errors: list[str] = []
    db = Database(db_path)
    try:
        await db.init_db()
    except Exception as exc:
        errors.append(f"Database init failed: {exc}")
        return errors

    ping_ok = await db.ping()
    if not ping_ok:
        errors.append("Database ping failed")

    quick_check_ok = await db.quick_check()
    if not quick_check_ok:
        errors.append("Database quick_check failed")
    return errors


async def run_preflight(
    bot_token: str,
    db_path: str,
    *,
    skip_db_runtime_check: bool = False,
) -> PreflightResult:
    errors: list[str] = []
    errors.extend(_validate_token(bot_token))
    errors.extend(_validate_db_path(db_path))

    if not skip_db_runtime_check and not errors:
        errors.extend(await _validate_db_runtime(db_path))

    return PreflightResult(ok=(len(errors) == 0), errors=errors)


def _parse_args() -> argparse.Namespace:
    default_bot_token, default_db_path, load_warnings = _load_config_defaults()
    parser = argparse.ArgumentParser(description="Run production preflight checks")
    parser.add_argument(
        "--bot-token",
        default=default_bot_token,
        help="Telegram bot token (defaults to config/.env BOT_TOKEN)",
    )
    parser.add_argument(
        "--db-path",
        default=default_db_path,
        help="SQLite database path (defaults to config/.env DATABASE_PATH)",
    )
    parser.add_argument(
        "--skip-db-runtime-check",
        action="store_true",
        help="Skip DB init/ping/quick_check runtime checks",
    )
    args = parser.parse_args()
    args._load_warnings = load_warnings
    return args


def main() -> int:
    args = _parse_args()
    warnings = list(getattr(args, "_load_warnings", []))
    result = asyncio.run(
        run_preflight(
            bot_token=args.bot_token,
            db_path=args.db_path,
            skip_db_runtime_check=args.skip_db_runtime_check,
        )
    )
    payload = {"ok": result.ok, "errors": result.errors, "warnings": warnings}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
