"""数据库操作模块"""
import aiosqlite
from datetime import datetime
from typing import List, Optional
from src.models.reminder import Reminder, RepeatType


class Database:
    """异步数据库操作类"""
    
    def __init__(self, db_path: str = "reminders.db"):
        self.db_path = db_path
    
    async def init_db(self) -> None:
        """初始化数据库表"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    repeat_type TEXT DEFAULT 'none',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL
                )
            """)
            await db.commit()
    
    async def create_reminder(self, reminder: Reminder) -> Reminder:
        """创建提醒"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO reminders 
                   (user_id, chat_id, content, remind_at, repeat_type, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (reminder.user_id, reminder.chat_id, reminder.content,
                 reminder.remind_at.isoformat(), reminder.repeat_type.value,
                 1 if reminder.is_active else 0, reminder.created_at.isoformat())
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
                (user_id,)
            )
            rows = await cursor.fetchall()
            return [self._row_to_reminder(dict(row)) for row in rows]
    
    async def get_pending_reminders(self) -> List[Reminder]:
        """获取待发送提醒"""
        now = datetime.now().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM reminders WHERE is_active = 1 AND remind_at <= ?",
                (now,)
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
                   repeat_type=?, is_active=? WHERE id=?""",
                (reminder.content, reminder.remind_at.isoformat(),
                 reminder.repeat_type.value, 1 if reminder.is_active else 0,
                 reminder.id)
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
    
    def _row_to_reminder(self, row: dict) -> Reminder:
        """将数据库行转换为 Reminder 对象"""
        return Reminder(
            id=row["id"],
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            content=row["content"],
            remind_at=datetime.fromisoformat(row["remind_at"]),
            repeat_type=RepeatType(row["repeat_type"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"])
        )
