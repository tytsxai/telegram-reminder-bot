"""调度器服务模块"""
import asyncio
from datetime import datetime
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.database.db import Database
from src.services.reminder import ReminderService


class SchedulerService:
    """调度器服务"""
    
    def __init__(
        self, 
        db: Database,
        send_callback: Optional[Callable] = None
    ):
        self.db = db
        self.reminder_service = ReminderService(db)
        self.scheduler = AsyncIOScheduler()
        self.send_callback = send_callback
    
    def start(self):
        """启动调度器"""
        self.scheduler.add_job(
            self._check_reminders,
            IntervalTrigger(seconds=30),
            id="check_reminders",
            replace_existing=True
        )
        self.scheduler.start()
    
    def stop(self):
        """停止调度器"""
        self.scheduler.shutdown()
    
    async def _check_reminders(self):
        """检查并发送到期提醒"""
        reminders = await self.db.get_pending_reminders()
        for reminder in reminders:
            await self._send_reminder(reminder)
            await self.reminder_service.process_reminder(reminder)
    
    async def _send_reminder(self, reminder):
        """发送提醒"""
        if self.send_callback:
            await self.send_callback(
                reminder.chat_id,
                f"⏰ 提醒: {reminder.content}"
            )
