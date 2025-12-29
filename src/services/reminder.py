"""提醒服务模块"""

from datetime import datetime, timedelta
from typing import List, Optional
from src.database.db import Database
from src.models.reminder import Reminder, RepeatType
from src.utils.time_utils import add_months, now_in_timezone


class ReminderService:
    """提醒服务"""

    def __init__(self, db: Database):
        self.db = db

    async def create_reminder(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        remind_at: datetime,
        repeat_type: RepeatType = RepeatType.NONE,
        repeat_weekday: Optional[int] = None,
        repeat_monthday: Optional[int] = None,
    ) -> Reminder:
        """创建提醒"""
        if repeat_type == RepeatType.WEEKLY and repeat_weekday is None:
            repeat_weekday = remind_at.weekday()
        if repeat_type == RepeatType.MONTHLY and repeat_monthday is None:
            repeat_monthday = remind_at.day
        reminder = Reminder(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            remind_at=remind_at,
            repeat_type=repeat_type,
            repeat_weekday=repeat_weekday,
            repeat_monthday=repeat_monthday,
        )
        return await self.db.create_reminder(reminder)

    async def get_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """获取提醒"""
        return await self.db.get_reminder(reminder_id)

    async def get_user_reminders(self, user_id: int) -> List[Reminder]:
        """获取用户所有提醒"""
        return await self.db.get_user_reminders(user_id)

    async def delete_reminder(self, reminder_id: int) -> bool:
        """删除提醒"""
        return await self.db.delete_reminder(reminder_id)

    async def delete_reminder_by_user(self, reminder_id: int, user_id: int) -> bool:
        """删除指定用户的提醒（带权限校验）"""
        return await self.db.delete_reminder_by_user(reminder_id, user_id)

    async def process_reminder(self, reminder: Reminder) -> Optional[datetime]:
        """处理提醒，返回下次提醒时间（如果是重复提醒）"""
        if reminder.repeat_type == RepeatType.NONE:
            reminder.is_active = False
            await self.db.update_reminder(reminder)
            return None

        # 计算下次提醒时间
        next_time = self._calculate_next_time(
            reminder.remind_at,
            reminder.repeat_type,
            reminder.repeat_weekday,
            reminder.repeat_monthday,
        )
        now = now_in_timezone()
        while next_time <= now:
            next_time = self._advance_time(
                next_time,
                reminder.repeat_type,
                reminder.repeat_weekday,
                reminder.repeat_monthday,
            )
        reminder.remind_at = next_time
        await self.db.update_reminder(reminder)
        return next_time

    def _calculate_next_time(
        self,
        current: datetime,
        repeat_type: RepeatType,
        repeat_weekday: Optional[int] = None,
        repeat_monthday: Optional[int] = None,
    ) -> datetime:
        """计算下次提醒时间"""
        return self._advance_time(current, repeat_type, repeat_weekday, repeat_monthday)

    def _advance_time(
        self,
        current: datetime,
        repeat_type: RepeatType,
        repeat_weekday: Optional[int],
        repeat_monthday: Optional[int],
    ) -> datetime:
        if repeat_type == RepeatType.DAILY:
            return current + timedelta(days=1)
        if repeat_type == RepeatType.WEEKLY:
            return current + timedelta(weeks=1)
        if repeat_type == RepeatType.MONTHLY:
            target_day = repeat_monthday or current.day
            return add_months(current, 1, target_day=target_day)
        return current
