"""Production preflight checks.

在上线前执行基础自检，快速发现会导致启动失败或运行不稳定的问题。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.db import Database
from src.utils.instance_lock import InstanceLock

_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]{20,}$")


@dataclass
class PreflightResult:
    ok: bool
    errors: list[str]
    warnings: list[str] = field(default_factory=list)


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_bool_arg(value: str) -> bool:
    normalized = (value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(
        "boolean value expected: true/false/1/0/yes/no/on/off"
    )


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def _load_config_defaults() -> tuple[
    str,
    str,
    bool,
    str,
    bool,
    str,
    int,
    bool,
    str,
    list[str],
    list[str],
]:
    """Load default BOT_TOKEN and DATABASE_PATH from app config/.env."""
    warnings: list[str] = []
    errors: list[str] = []
    try:
        from src.config import Settings

        loaded = Settings()
        return (
            loaded.BOT_TOKEN,
            loaded.DATABASE_PATH,
            loaded.INSTANCE_LOCK_ENABLED,
            loaded.INSTANCE_LOCK_PATH,
            loaded.HEALTHCHECK_ENABLED,
            loaded.HEALTHCHECK_HOST,
            loaded.HEALTHCHECK_PORT,
            loaded.DB_QUICK_CHECK_ON_STARTUP,
            loaded.LOG_LEVEL,
            warnings,
            errors,
        )
    except Exception as exc:
        errors.append(f"Settings validation failed: {exc}")
        return (
            os.getenv("BOT_TOKEN", ""),
            os.getenv("DATABASE_PATH", "reminders.db"),
            _parse_bool_env("INSTANCE_LOCK_ENABLED", True),
            os.getenv("INSTANCE_LOCK_PATH", "reminder-bot.lock"),
            _parse_bool_env("HEALTHCHECK_ENABLED", True),
            os.getenv("HEALTHCHECK_HOST", "127.0.0.1"),
            _parse_int_env("HEALTHCHECK_PORT", 8080),
            _parse_bool_env("DB_QUICK_CHECK_ON_STARTUP", True),
            os.getenv("LOG_LEVEL", "INFO"),
            warnings,
            errors,
        )


def _validate_token(bot_token: str) -> list[str]:
    errors: list[str] = []
    token = (bot_token or "").strip()
    if token == "":
        errors.append("BOT_TOKEN is empty")
        return errors
    # Telegram token usually matches: digits:Base64URL-like chars
    if not _TOKEN_PATTERN.match(token):
        errors.append("BOT_TOKEN format is invalid")
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


def _validate_instance_lock(enabled: bool, lock_path: str) -> list[str]:
    errors: list[str] = []
    if not enabled:
        return errors
    if not (lock_path or "").strip():
        errors.append("INSTANCE_LOCK_PATH is empty")
        return errors
    lock = InstanceLock(lock_path)
    if not lock.acquire():
        errors.append(f"Instance lock check failed: {lock_path}")
        return errors
    lock.release()
    return errors


def _warn_if_open_permissions(path: Path, label: str) -> list[str]:
    warnings: list[str] = []
    if not path.exists() or path.is_dir():
        return warnings
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        warnings.append(f"Cannot read permissions for {label} ({path}): {exc}")
        return warnings
    if mode & 0o077:
        warnings.append(
            f"{label} permissions are too broad ({oct(mode)}); recommend 0o600"
        )
    return warnings


def _warn_if_duplicate_env_keys(path: Path) -> list[str]:
    warnings: list[str] = []
    if not path.exists() or path.is_dir():
        return warnings
    seen: set[str] = set()
    duplicates: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        warnings.append(f"Cannot read env file for duplicate-key check ({path}): {exc}")
        return warnings
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        if not key:
            continue
        if key in seen:
            duplicates.add(key)
        else:
            seen.add(key)
    if duplicates:
        keys = ", ".join(sorted(duplicates))
        warnings.append(
            f".env contains duplicate keys ({keys}); later values override earlier ones"
        )
    return warnings


def _collect_security_warnings(db_path: str) -> list[str]:
    warnings: list[str] = []
    env_path = Path(".env")
    warnings.extend(_warn_if_open_permissions(env_path, ".env"))
    warnings.extend(_warn_if_duplicate_env_keys(env_path))
    db_file = Path((db_path or "").strip()).expanduser()
    if db_file.exists() and db_file.is_file():
        warnings.extend(_warn_if_open_permissions(db_file, "database file"))
    return warnings


def _collect_runtime_warnings(
    *,
    healthcheck_enabled: bool,
    db_quick_check_on_startup: bool,
    instance_lock_enabled: bool,
    log_level: str,
) -> list[str]:
    warnings: list[str] = []
    if not healthcheck_enabled:
        warnings.append(
            "HEALTHCHECK_ENABLED=false; production probes and alerting visibility are reduced"
        )
    if not db_quick_check_on_startup:
        warnings.append(
            "DB_QUICK_CHECK_ON_STARTUP=false; startup may miss SQLite corruption"
        )
    if not instance_lock_enabled:
        warnings.append(
            "INSTANCE_LOCK_ENABLED=false; duplicate instances may cause repeated reminders"
        )
    if (log_level or "").strip().upper() == "DEBUG":
        warnings.append("LOG_LEVEL=DEBUG in production may leak sensitive context")
    return warnings


def _validate_healthcheck_config(*, enabled: bool, host: str, port: int) -> list[str]:
    errors: list[str] = []
    if not enabled:
        return errors
    if not (host or "").strip():
        errors.append("HEALTHCHECK_HOST is empty")
    try:
        port_value = int(port)
    except (TypeError, ValueError):
        errors.append("HEALTHCHECK_PORT must be an integer")
        return errors
    if not (1 <= port_value <= 65535):
        errors.append("HEALTHCHECK_PORT must be between 1 and 65535")
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


async def _validate_healthcheck_bind(
    *, enabled: bool, host: str, port: int
) -> list[str]:
    errors: list[str] = []
    if not enabled:
        return errors
    try:
        server = await asyncio.start_server(lambda _r, _w: None, host, port)
    except Exception as exc:
        errors.append(f"Healthcheck bind failed on {host}:{port}: {exc}")
        return errors
    server.close()
    await server.wait_closed()
    return errors


async def run_preflight(
    bot_token: str,
    db_path: str,
    *,
    skip_db_runtime_check: bool = False,
    instance_lock_enabled: bool = True,
    instance_lock_path: str = "reminder-bot.lock",
    healthcheck_enabled: bool = True,
    healthcheck_host: str = "127.0.0.1",
    healthcheck_port: int = 8080,
    db_quick_check_on_startup: bool = True,
    log_level: str = "INFO",
    config_errors: list[str] | None = None,
) -> PreflightResult:
    errors: list[str] = []
    warnings: list[str] = []
    if config_errors:
        errors.extend(config_errors)
    errors.extend(_validate_token(bot_token))
    errors.extend(_validate_db_path(db_path))
    errors.extend(_validate_instance_lock(instance_lock_enabled, instance_lock_path))
    warnings.extend(
        _collect_runtime_warnings(
            healthcheck_enabled=healthcheck_enabled,
            db_quick_check_on_startup=db_quick_check_on_startup,
            instance_lock_enabled=instance_lock_enabled,
            log_level=log_level,
        )
    )
    errors.extend(
        _validate_healthcheck_config(
            enabled=healthcheck_enabled,
            host=healthcheck_host,
            port=healthcheck_port,
        )
    )
    if not errors:
        errors.extend(
            await _validate_healthcheck_bind(
                enabled=healthcheck_enabled,
                host=healthcheck_host,
                port=healthcheck_port,
            )
        )

    if not skip_db_runtime_check and not errors:
        errors.extend(await _validate_db_runtime(db_path))

    # 在可选 runtime check 后再评估文件权限，避免“已被脚本修复但仍报 warning”。
    warnings.extend(_collect_security_warnings(db_path))

    return PreflightResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def _parse_args() -> argparse.Namespace:
    (
        default_bot_token,
        default_db_path,
        default_instance_lock_enabled,
        default_instance_lock_path,
        default_healthcheck_enabled,
        default_healthcheck_host,
        default_healthcheck_port,
        default_db_quick_check_on_startup,
        default_log_level,
        load_warnings,
        load_errors,
    ) = _load_config_defaults()
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
    parser.add_argument(
        "--instance-lock-enabled",
        type=_parse_bool_arg,
        default=default_instance_lock_enabled,
        help="Whether instance lock check is enabled (true/false)",
    )
    parser.add_argument(
        "--instance-lock-path",
        default=default_instance_lock_path,
        help="Instance lock file path",
    )
    parser.add_argument(
        "--healthcheck-enabled",
        type=_parse_bool_arg,
        default=default_healthcheck_enabled,
        help="Whether healthcheck endpoint is enabled (true/false)",
    )
    parser.add_argument(
        "--healthcheck-host",
        default=default_healthcheck_host,
        help="Healthcheck bind host used for startup readiness checks",
    )
    parser.add_argument(
        "--healthcheck-port",
        type=int,
        default=default_healthcheck_port,
        help="Healthcheck bind port used for startup readiness checks",
    )
    parser.add_argument(
        "--db-quick-check-on-startup",
        type=_parse_bool_arg,
        default=default_db_quick_check_on_startup,
        help="Whether SQLite quick_check runs on startup (true/false)",
    )
    parser.add_argument(
        "--log-level",
        default=default_log_level,
        help="Runtime log level (INFO/DEBUG/...) used for production warnings",
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Treat warnings as release blockers (non-zero exit when warnings exist)",
    )
    args = parser.parse_args()
    args._load_warnings = load_warnings
    args._load_errors = load_errors
    return args


def main() -> int:
    args = _parse_args()
    warnings = list(getattr(args, "_load_warnings", []))
    config_errors = list(getattr(args, "_load_errors", []))
    result = asyncio.run(
        run_preflight(
            bot_token=args.bot_token,
            db_path=args.db_path,
            skip_db_runtime_check=args.skip_db_runtime_check,
            instance_lock_enabled=args.instance_lock_enabled,
            instance_lock_path=args.instance_lock_path,
            healthcheck_enabled=args.healthcheck_enabled,
            healthcheck_host=args.healthcheck_host,
            healthcheck_port=args.healthcheck_port,
            db_quick_check_on_startup=args.db_quick_check_on_startup,
            log_level=args.log_level,
            config_errors=config_errors,
        )
    )
    warnings.extend(result.warnings)
    errors = list(result.errors)
    if args.strict_warnings and warnings:
        errors.append(
            "strict warnings enabled: preflight warnings must be resolved or explicitly waived"
        )
    ok = len(errors) == 0
    payload = {"ok": ok, "errors": errors, "warnings": warnings}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
