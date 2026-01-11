"""SQLite backup utility."""

from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQLite backup utility")
    parser.add_argument("--db", required=True, help="Path to SQLite database")
    parser.add_argument(
        "--out-dir", required=True, help="Directory to store backup files"
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Number of backups to keep (default: 7)",
    )
    return parser.parse_args()


def backup(db_path: str, out_dir: str, keep: int) -> Path:
    src_path = Path(db_path).expanduser()
    if db_path == ":memory:":
        raise ValueError("In-memory database cannot be backed up")
    if not src_path.exists():
        raise FileNotFoundError(f"Database file not found: {src_path}")
    if src_path.is_dir():
        raise IsADirectoryError(f"Database path is a directory: {src_path}")

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = out_path / f"reminders_{timestamp}.db"

    src = sqlite3.connect(str(src_path))
    dest = sqlite3.connect(str(backup_path))
    try:
        with dest:
            src.backup(dest)
    finally:
        dest.close()
        src.close()

    _prune_backups(out_path, keep)
    return backup_path


def _prune_backups(out_dir: Path, keep: int) -> None:
    if keep <= 0:
        return
    backups = sorted(out_dir.glob("reminders_*.db"), key=os.path.getmtime, reverse=True)
    for old in backups[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def main() -> None:
    args = parse_args()
    backup_path = backup(args.db, args.out_dir, args.keep)
    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
