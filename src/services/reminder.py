"""提醒服务模块"""
from datetime import datetime, timedelta
from typing import List, Optional
from src.database.db import Database
from src.models.reminder import Reminder, RepeatType


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
        repeat_type: RepeatType = RepeatType.NONE
    ) -> Reminder:
        """创建提醒"""
        reminder = Reminder(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            remind_at=remind_at,
            repeat_type=repeat_type
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
    
    async def process_reminder(self, reminder: Reminder) -> Optional[datetime]:
        """处理提醒，返回下次提醒时间（如果是重复提醒）"""
        if reminder.repeat_type == RepeatType.NONE:
            reminder.is_active = False
            await self.db.update_reminder(reminder)
            return None
        
        # 计算下次提醒时间
        next_time = self._calculate_next_time(
            reminder.remind_at, 
            reminder.repeat_type
        )
        reminder.remind_at = next_time
        await self.db.update_reminder(reminder)
        return next_time
    
    def _calculate_next_time(
        self, 
        current: datetime, 
        repeat_type: RepeatType
    ) -> datetime:
        """计算下次提醒时间"""
        if repeat_type == RepeatType.DAILY:
            return current + timedelta(days=1)
        elif repeat_type == RepeatType.WEEKLY:
            return current + timedelta(weeks=1)
        elif repeat_type == RepeatType.MONTHLY:
            # 简单处理：加30天
            return current + timedelta(days=30)
        return current
