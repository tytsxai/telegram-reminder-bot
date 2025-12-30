"""数据库操作模块"""

import aiosqlite
from datetime import datetime
from typing import List, Optional
from src.models.reminder import Reminder, RepeatType
from src.utils.time_utils import now_in_timezone


class Database:
    """异步数据库操作类"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from src.config import settings

            db_path = settings.DATABASE_PATH
        self.db_path = db_path

    async def ping(self) -> bool:
        """检查数据库连通性"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("SELECT 1")
            return True
        except Exception:
            return False

    async def init_db(self) -> None:
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
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
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """
            )
            await self._apply_migrations(db)
            await db.commit()

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

    async def _create_indexes(self, db: aiosqlite.Connection) -> None:
        """创建常用索引"""
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_active_remind_at "
            "ON reminders (is_active, remind_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders (user_id)"
        )

    async def create_reminder(self, reminder: Reminder) -> Reminder:
        """创建提醒"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO reminders 
                   (user_id, chat_id, content, remind_at, repeat_type,
                    repeat_weekday, repeat_monthday, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    reminder.user_id,
                    reminder.chat_id,
                    reminder.content,
                    reminder.remind_at.isoformat(),
                    reminder.repeat_type.value,
                    reminder.repeat_weekday,
                    reminder.repeat_monthday,
                    1 if reminder.is_active else 0,
                    reminder.created_at.isoformat(),
                ),
            )
            await db.commit()
            reminder.id = cursor.lastrowid
            return reminder

    async def get_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """获取单个提醒"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            )
            row = await cursor.fetchone()
            if row:
                return self._row_to_reminder(dict(row))
            return None

    async def get_user_reminders(self, user_id: int) -> List[Reminder]:
        """获取用户所有提醒"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM reminders WHERE user_id = ? AND is_active = 1",
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_reminder(dict(row)) for row in rows]

    async def get_pending_reminders(self) -> List[Reminder]:
        """获取待发送提醒"""
        now = now_in_timezone().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM reminders WHERE is_active = 1 AND remind_at <= ?", (now,)
            )
            rows = await cursor.fetchall()
            return [self._row_to_reminder(dict(row)) for row in rows]

    async def update_reminder(self, reminder: Reminder) -> bool:
        """更新提醒"""
        if reminder.id is None:
            return False
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE reminders SET content=?, remind_at=?, 
                   repeat_type=?, repeat_weekday=?, repeat_monthday=?, is_active=? WHERE id=?""",
                (
                    reminder.content,
                    reminder.remind_at.isoformat(),
                    reminder.repeat_type.value,
                    reminder.repeat_weekday,
                    reminder.repeat_monthday,
                    1 if reminder.is_active else 0,
                    reminder.id,
                ),
            )
            await db.commit()
            return True

    async def delete_reminder(self, reminder_id: int) -> bool:
        """删除提醒"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM reminders WHERE id = ?", (reminder_id,)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def delete_reminder_by_user(self, reminder_id: int, user_id: int) -> bool:
        """删除指定用户的提醒（带权限校验）"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM reminders WHERE id = ? AND user_id = ?",
                (reminder_id, user_id),
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
            remind_at=datetime.fromisoformat(row["remind_at"]),
            repeat_type=RepeatType(row["repeat_type"]),
            repeat_weekday=row.get("repeat_weekday"),
            repeat_monthday=row.get("repeat_monthday"),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
