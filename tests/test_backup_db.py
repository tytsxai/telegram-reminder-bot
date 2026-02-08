"""Backup script tests."""

from pathlib import Path
import sqlite3

import pytest

from scripts.backup_db import backup


def _create_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
        conn.commit()
    finally:
        conn.close()


def test_backup_success(tmp_path: Path) -> None:
    db_path = tmp_path / "reminders.db"
    _create_db(db_path)
    out_dir = tmp_path / "backups"
    backup_path = backup(str(db_path), str(out_dir), keep=1)
    assert backup_path.exists()


def test_backup_missing_db(tmp_path: Path) -> None:
    missing = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        backup(str(missing), str(tmp_path), keep=1)


def test_backup_db_is_directory(tmp_path: Path) -> None:
    db_dir = tmp_path / "db_dir"
    db_dir.mkdir()
    with pytest.raises(IsADirectoryError):
        backup(str(db_dir), str(tmp_path), keep=1)


def test_backup_in_memory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        backup(":memory:", str(tmp_path), keep=1)


def test_backup_keep_negative(tmp_path: Path) -> None:
    db_path = tmp_path / "reminders.db"
    _create_db(db_path)
    with pytest.raises(ValueError):
        backup(str(db_path), str(tmp_path), keep=-1)


def test_backup_out_dir_not_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "reminders.db"
    _create_db(db_path)
    out_file = tmp_path / "not-a-dir"
    out_file.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        backup(str(db_path), str(out_file), keep=1)


def test_backup_file_permission_600(tmp_path: Path) -> None:
    db_path = tmp_path / "reminders.db"
    _create_db(db_path)
    out_dir = tmp_path / "backups"
    backup_path = backup(str(db_path), str(out_dir), keep=1)
    mode = backup_path.stat().st_mode & 0o777
    assert mode == 0o600
