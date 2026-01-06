"""提醒服务模块

封装提醒业务逻辑，包括：
- 创建/查询/删除提醒
- 重复提醒的下次时间计算
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from src.database.db import Database
from src.models.reminder import Reminder, RepeatType
from src.utils.time_utils import add_months, now_in_timezone

logger = logging.getLogger(__name__)


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
        created = await self.db.create_reminder(reminder)
        logger.info(
            "Created reminder id=%s user_id=%s chat_id=%s repeat=%s",
            created.id,
            user_id,
            chat_id,
            created.repeat_type.value,
        )
        return created

    async def get_reminder(self, reminder_id: int) -> Optional[Reminder]:
        """获取提醒"""
        return await self.db.get_reminder(reminder_id)

    async def get_user_reminders(
        self,
        user_id: int,
        chat_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Reminder]:
        """获取用户所有提醒"""
        return await self.db.get_user_reminders(user_id, chat_id, limit, offset)

    async def delete_reminder(self, reminder_id: int) -> bool:
        """删除提醒"""
        return await self.db.delete_reminder(reminder_id)

    async def delete_reminder_by_user(
        self, reminder_id: int, user_id: int, chat_id: Optional[int] = None
    ) -> bool:
        """删除指定用户的提醒（带权限校验，可选限定 chat）"""
        return await self.db.delete_reminder_by_user(reminder_id, user_id, chat_id)

    async def process_reminder(
        self,
        reminder: Reminder,
        sent_at: Optional[datetime] = None,
        sent_for: Optional[datetime] = None,
        release_lock: bool = True,
    ) -> Optional[datetime]:
        """处理提醒，返回下次提醒时间（如果是重复提醒）"""
        if sent_at is not None:
            reminder.last_sent_at = sent_at
        if sent_for is not None:
            reminder.last_sent_for = sent_for
        reminder.send_attempt_for = None
        reminder.send_attempt_until = None
        if release_lock:
            reminder.locked_until = None
        if reminder.repeat_type == RepeatType.NONE:
            reminder.is_active = False
            updated = await self.db.update_reminder(reminder)
            if not updated:
                logger.warning(
                    "Failed to update reminder id=%s after send; maybe deleted",
                    reminder.id,
                )
            return None

        # 计算下次提醒时间
        next_time = self._calculate_next_time(
            reminder.remind_at,
            reminder.repeat_type,
            reminder.repeat_weekday,
            reminder.repeat_monthday,
        )
        now = now_in_timezone()
        if reminder.repeat_type in (RepeatType.DAILY, RepeatType.WEEKLY):
            interval = (
                timedelta(days=1)
                if reminder.repeat_type == RepeatType.DAILY
                else timedelta(weeks=1)
            )
            if next_time <= now:
                delta = now - next_time
                steps = int(delta.total_seconds() // interval.total_seconds()) + 1
                next_time = next_time + interval * steps
        elif reminder.repeat_type == RepeatType.MONTHLY:
            if next_time <= now:
                target_day = reminder.repeat_monthday or next_time.day
                months_now = now.year * 12 + now.month
                months_next = next_time.year * 12 + next_time.month
                diff = max(0, months_now - months_next)
                candidate = add_months(next_time, diff, target_day=target_day)
                if candidate <= now:
                    candidate = add_months(candidate, 1, target_day=target_day)
                next_time = candidate
        else:
            while next_time <= now:
                next_time = self._advance_time(
                    next_time,
                    reminder.repeat_type,
                    reminder.repeat_weekday,
                    reminder.repeat_monthday,
                )
        reminder.remind_at = next_time
        updated = await self.db.update_reminder(reminder)
        if not updated:
            logger.warning(
                "Failed to update reminder id=%s after reschedule; maybe deleted",
                reminder.id,
            )
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
