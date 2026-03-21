"""数据库操作模块

提供异步 SQLite 数据库操作，包括：
- 提醒的 CRUD 操作
- 数据库初始化与迁移
- 并发控制（锁定机制）
- 发送尝试标记（避免崩溃后重复发送）
"""

from __future__ import annotations

import logging
import os
import stat
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import aiosqlite
import pytz

from src.models.reminder import Reminder, RepeatType
from src.utils.time_utils import (
    from_utc_iso,
    now_utc,
    to_utc,
    to_utc_iso,
)

logger = logging.getLogger(__name__)


class Database:
    """异步数据库操作类"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from src.config import settings

            db_path = settings.DATABASE_PATH
        self.db_path = db_path
        self._timeout_seconds = 30
        self._busy_timeout_ms = 5000

    def _ensure_db_dir(self) -> None:
        if not self.db_path or self.db_path == ":memory:":
            return
        path = Path(self.db_path).expanduser()
        parent = path.parent
        if parent and str(parent) not in (".", ""):
            os.makedirs(parent, exist_ok=True)

    def _harden_db_permissions(self) -> None:
        """Best-effort permission hardening for SQLite file."""
        if os.name == "nt":
            return
        if not self.db_path or self.db_path == ":memory:":
            return
        path = Path(self.db_path).expanduser()
        if not path.exists() or not path.is_file():
            return
        try:
            current = stat.S_IMODE(path.stat().st_mode)
            if current & 0o077:
                path.chmod(0o600)
        except Exception as exc:
            logger.warning("Failed to harden database file permissions: %s", exc)

    async def _configure_connection(self, db: aiosqlite.Connection) -> None:
        try:
            await db.execute("PRAGMA journal_mode=WAL")
        except Exception as exc:
            logger.debug("Failed to set journal_mode=WAL: %s", exc)
        try:
            await db.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
        except Exception as exc:
            logger.debug("Failed to set busy_timeout: %s", exc)
        try:
            await db.execute("PRAGMA foreign_keys=ON")
        except Exception as exc:
            logger.debug("Failed to set foreign_keys: %s", exc)

    @asynccontextmanager
    async def _connect(self):
        self._ensure_db_dir()
        db = await aiosqlite.connect(self.db_path, timeout=self._timeout_seconds)
        try:
            await self._configure_connection(db)
            yield db
        finally:
            await db.close()

    async def ping(self) -> bool:
        """检查数据库连通性"""
        try:
            async with self._connect() as db:
                await db.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def checkpoint(self) -> None:
        """触发 WAL checkpoint，防止 WAL 文件无限增长。"""
        try:
            async with self._connect() as db:
                await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:
            logger.warning("WAL checkpoint failed: %s", exc)

    async def quick_check(self) -> bool:
        """执行 SQLite 快速完整性检查。"""
        try:
            async with self._connect() as db:
                cursor = await db.execute("PRAGMA quick_check(1)")
                row = await cursor.fetchone()
            result = (
                "" if row is None or row[0] is None else str(row[0]).strip().lower()
            )
            if result != "ok":
                logger.error("Database quick_check failed: %s", row[0] if row else None)
                return False
            return True
        except Exception as exc:
            logger.error("Database quick_check error: %s", exc)
            return False

    async def init_db(self) -> None:
        """初始化数据库表"""
        async with self._connect() as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    repeat_type TEXT DEFAULT 'none',
                    repeat_weekday INTEGER,
                    repeat_monthday INTEGER,
                    locked_until TEXT,
                    last_sent_at TEXT,
                    last_sent_for TEXT,
                    send_attempt_for TEXT,
                    send_attempt_until TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """
            )
            await self._apply_migrations(db)
            await db.commit()
        self._harden_db_permissions()

    async def _apply_migrations(self, db: aiosqlite.Connection) -> None:
        """按版本应用迁移"""
        current = await self._get_schema_version(db)
        if current < 1:
            await self._ensure_columns(db)
            await self._set_schema_version(db, 1)
            current = 1
        if current < 2:
            await self._create_indexes(db)
            await self._set_schema_version(db, 2)
            current = 2
        if current < 3:
            await self._ensure_columns(db)
            await self._migrate_times_to_utc(db)
            await self._set_schema_version(db, 3)
            current = 3
        if current < 4:
            await self._ensure_columns(db)
            await self._create_indexes(db)
            await self._set_schema_version(db, 4)

    async def _get_schema_version(self, db: aiosqlite.Connection) -> int:
        """读取当前数据库版本"""
        await db.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
        )
        cursor = await db.execute("SELECT version FROM schema_version LIMIT 1")
        row = await cursor.fetchone()
        if row is None:
            await db.execute("INSERT INTO schema_version (version) VALUES (0)")
            return 0
        try:
            return int(row[0])
        except (TypeError, ValueError):
            return 0

    async def _set_schema_version(self, db: aiosqlite.Connection, version: int) -> None:
        """更新数据库版本"""
        await db.execute("UPDATE schema_version SET version = ?", (version,))

    async def _ensure_columns(self, db: aiosqlite.Connection) -> None:
        """为旧表补充新增字段"""
        cursor = await db.execute("PRAGMA table_info(reminders)")
        rows = await cursor.fetchall()
        existing = {row[1] for row in rows}
        if "repeat_weekday" not in existing:
            await db.execute("ALTER TABLE reminders ADD COLUMN repeat_weekday INTEGER")
        if "repeat_monthday" not in existing:
            await db.execute("ALTER TABLE reminders ADD COLUMN repeat_monthday INTEGER")
        if "locked_until" not in existing:
            await db.execute("ALTER TABLE reminders ADD COLUMN locked_until TEXT")
        if "last_sent_at" not in existing:
            await db.execute("ALTER TABLE reminders ADD COLUMN last_sent_at TEXT")
        if "last_sent_for" not in existing:
            await db.execute("ALTER TABLE reminders ADD COLUMN last_sent_for TEXT")
        if "send_attempt_for" not in existing:
            await db.execute("ALTER TABLE reminders ADD COLUMN send_attempt_for TEXT")
        if "send_attempt_until" not in existing:
            await db.execute("ALTER TABLE reminders ADD COLUMN send_attempt_until TEXT")

    async def _migrate_times_to_utc(self, db: aiosqlite.Connection) -> None:
        """将时间字段统一转换为 UTC ISO 格式。"""
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, remind_at, created_at, locked_until, last_sent_at, "
            "last_sent_for, send_attempt_for, send_attempt_until FROM reminders"
        )
        rows = await cursor.fetchall()
        for row in rows:
            updates = {}
            for field in (
                "remind_at",
                "created_at",
                "locked_until",
                "last_sent_at",
                "last_sent_for",
                "send_attempt_for",
                "send_attempt_until",
            ):
                value = row[field]
                if not value:
                    continue
                try:
                    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                except ValueError:
                    continue
                if dt.tzinfo is None:
                    dt_utc = to_utc(dt)
                else:
                    dt_utc = dt.astimezone(pytz.UTC)
                updates[field] = dt_utc.isoformat()
            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                params = list(updates.values())
                params.append(row["id"])
                await db.execute(
                    f"UPDATE reminders SET {set_clause} WHERE id = ?", params
                )

    async def _create_indexes(self, db: aiosqlite.Connection) -> None:
        """创建常用索引"""
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_active_remind_at "
            "ON reminders (is_active, remind_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders (user_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_pending "
            "ON reminders (is_active, remind_at, locked_until, send_attempt_until)"
        )

    async def create_reminder(self, reminder: Reminder) -> Reminder:
        """创建提醒"""
        async with self._connect() as db:
            cursor = await db.execute(
                """INSERT INTO reminders 
                   (user_id, chat_id, content, remind_at, repeat_type,
                    repeat_weekday, repeat_monthday, locked_until, last_sent_at,
                    last_sent_for, send_attempt_for, send_attempt_until, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    reminder.user_id,
                    reminder.chat_id,
                    reminder.content,
                    to_utc_iso(reminder.remind_at),
                    reminder.repeat_type.value,
                    reminder.repeat_weekday,
                    reminder.repeat_monthday,
                    (
                        to_utc_iso(reminder.locked_until)
                        if reminder.locked_until
                        else None
                    ),
                    (
                        to_utc_iso(reminder.last_sent_at)
                        if reminder.last_sent_at
                        else None
                    ),
                    (
                        to_utc_iso(reminder.last_sent_for)
                        if reminder.last_sent_for
                        else None
                    ),
                    (
                        to_utc_iso(reminder.send_attempt_for)
                        if reminder.send_attempt_for
                        else None
                    ),
                    (
                        to_utc_iso(reminder.send_attempt_until)
                        if reminder.send_attempt_until
                        else None
                    ),
                    1 if reminder.is_active else 0,
                    to_utc_iso(reminder.created_at),
                ),
            )
            await db.commit()
            reminder.id = cursor.lastrowid
            return reminder

    async def get_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """获取单个提醒"""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            )
            row = await cursor.fetchone()
            if row:
                return self._row_to_reminder(dict(row))
            return None

    async def get_user_reminders(
        self,
        user_id: int,
        chat_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Reminder]:
        """获取用户所有提醒"""
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            if chat_id is None:
                sql = (
                    "SELECT * FROM reminders WHERE user_id = ? AND is_active = 1 "
                    "ORDER BY remind_at"
                )
                params = [user_id]
            else:
                sql = (
                    "SELECT * FROM reminders WHERE user_id = ? AND chat_id = ? "
                    "AND is_active = 1 ORDER BY remind_at"
                )
                params = [user_id, chat_id]
            if limit is not None:
                if offset is None:
                    offset = 0
                sql = f"{sql} LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            cursor = await db.execute(sql, tuple(params))
            rows = await cursor.fetchall()
            return [self._row_to_reminder(dict(row)) for row in rows]

    async def get_pending_reminders(self) -> List[Reminder]:
        """获取待发送提醒"""
        now = now_utc().isoformat()
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            # send_attempt_* ensures retries are delayed after in-flight attempts.
            cursor = await db.execute(
                """
                SELECT * FROM reminders
                WHERE is_active = 1
                  AND remind_at <= ?
                  AND (locked_until IS NULL OR locked_until < ?)
                  AND (last_sent_for IS NULL OR last_sent_for != remind_at)
                  AND (
                        send_attempt_for IS NULL
                        OR send_attempt_for != remind_at
                        OR send_attempt_until IS NULL
                        OR send_attempt_until < ?
                  )
                """,
                (now, now, now),
            )
            rows = await cursor.fetchall()
            return [self._row_to_reminder(dict(row)) for row in rows]

    async def claim_pending_reminders(
        self, limit: int, lock_seconds: int
    ) -> List[Reminder]:
        """领取待发送提醒（防止并发重复处理）"""
        if limit <= 0:
            return []
        now_dt = now_utc()
        now = now_dt.isoformat()
        lock_until = (now_dt + timedelta(seconds=lock_seconds)).isoformat()
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            # Avoid claiming items that are currently being attempted elsewhere.
            cursor = await db.execute(
                """
                SELECT * FROM reminders
                WHERE is_active = 1
                  AND remind_at <= ?
                  AND (locked_until IS NULL OR locked_until < ?)
                  AND (last_sent_for IS NULL OR last_sent_for != remind_at)
                  AND (
                        send_attempt_for IS NULL
                        OR send_attempt_for != remind_at
                        OR send_attempt_until IS NULL
                        OR send_attempt_until < ?
                  )
                ORDER BY remind_at
                LIMIT ?
                """,
                (now, now, now, limit),
            )
            rows = await cursor.fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                placeholders = ",".join("?" for _ in ids)
                await db.execute(
                    f"UPDATE reminders SET locked_until = ? WHERE id IN ({placeholders})",
                    (lock_until, *ids),
                )
            await db.commit()
            reminders = [self._row_to_reminder(dict(row)) for row in rows]
            # 保持内存态锁与 DB 一致，避免刚领取就被再次认领。
            if ids:
                locked_local = from_utc_iso(lock_until)
                for reminder in reminders:
                    reminder.locked_until = locked_local
            return reminders

    async def update_reminder(self, reminder: Reminder) -> bool:
        """更新提醒"""
        if reminder.id is None:
            return False
        async with self._connect() as db:
            cursor = await db.execute(
                """UPDATE reminders SET content=?, remind_at=?, 
                   repeat_type=?, repeat_weekday=?, repeat_monthday=?,
                   locked_until=?, last_sent_at=?, last_sent_for=?,
                   send_attempt_for=?, send_attempt_until=?,
                   is_active=? WHERE id=?""",
                (
                    reminder.content,
                    to_utc_iso(reminder.remind_at),
                    reminder.repeat_type.value,
                    reminder.repeat_weekday,
                    reminder.repeat_monthday,
                    (
                        to_utc_iso(reminder.locked_until)
                        if reminder.locked_until
                        else None
                    ),
                    (
                        to_utc_iso(reminder.last_sent_at)
                        if reminder.last_sent_at
                        else None
                    ),
                    (
                        to_utc_iso(reminder.last_sent_for)
                        if reminder.last_sent_for
                        else None
                    ),
                    (
                        to_utc_iso(reminder.send_attempt_for)
                        if reminder.send_attempt_for
                        else None
                    ),
                    (
                        to_utc_iso(reminder.send_attempt_until)
                        if reminder.send_attempt_until
                        else None
                    ),
                    1 if reminder.is_active else 0,
                    reminder.id,
                ),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_reminder(self, reminder_id: int) -> bool:
        """删除提醒"""
        async with self._connect() as db:
            cursor = await db.execute(
                "DELETE FROM reminders WHERE id = ?", (reminder_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_reminder_by_user(
        self, reminder_id: int, user_id: int, chat_id: Optional[int] = None
    ) -> bool:
        """删除指定用户的提醒（带权限校验，可选限定 chat）"""
        async with self._connect() as db:
            if chat_id is None:
                cursor = await db.execute(
                    "DELETE FROM reminders WHERE id = ? AND user_id = ?",
                    (reminder_id, user_id),
                )
            else:
                cursor = await db.execute(
                    "DELETE FROM reminders WHERE id = ? AND user_id = ? AND chat_id = ?",
                    (reminder_id, user_id, chat_id),
                )
            await db.commit()
            return cursor.rowcount > 0

    def _row_to_reminder(self, row: dict) -> Reminder:
        """将数据库行转换为 Reminder 对象"""
        return Reminder(
            id=row["id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            content=row["content"],
            remind_at=from_utc_iso(row["remind_at"]),
            repeat_type=RepeatType(row["repeat_type"]),
            repeat_weekday=row.get("repeat_weekday"),
            repeat_monthday=row.get("repeat_monthday"),
            locked_until=(
                from_utc_iso(row["locked_until"]) if row.get("locked_until") else None
            ),
            last_sent_at=(
                from_utc_iso(row["last_sent_at"]) if row.get("last_sent_at") else None
            ),
            last_sent_for=(
                from_utc_iso(row["last_sent_for"]) if row.get("last_sent_for") else None
            ),
            send_attempt_for=(
                from_utc_iso(row["send_attempt_for"])
                if row.get("send_attempt_for")
                else None
            ),
            send_attempt_until=(
                from_utc_iso(row["send_attempt_until"])
                if row.get("send_attempt_until")
                else None
            ),
            is_active=bool(row["is_active"]),
            created_at=from_utc_iso(row["created_at"]),
        )
