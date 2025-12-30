"""调度器服务模块"""

import logging
from typing import Awaitable, Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.config import settings
from src.database.db import Database
from src.services.reminder import ReminderService

logger = logging.getLogger(__name__)


class SchedulerService:
    """调度器服务"""

    def __init__(
        self,
        db: Database,
        send_callback: Optional[Callable[[int, str], Awaitable[None]]] = None,
        interval_seconds: Optional[int] = None,
    ):
        self.db = db
        self.reminder_service = ReminderService(db)
        self.scheduler = AsyncIOScheduler()
        self.send_callback = send_callback
        self.interval_seconds = interval_seconds or settings.SCHEDULER_INTERVAL_SECONDS

    def start(self):
        """启动调度器"""
        self.scheduler.add_job(
            self._check_reminders,
            IntervalTrigger(seconds=self.interval_seconds),
            id="check_reminders",
            replace_existing=True,
        )
        self.scheduler.start()

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def _check_reminders(self):
        """检查并发送到期提醒"""
        try:
            reminders = await self.db.get_pending_reminders()
        except Exception as e:
            logger.error(f"获取待发送提醒失败: {e}")
            return

        for reminder in reminders:
            try:
                await self._send_reminder(reminder)
                await self.reminder_service.process_reminder(reminder)
                logger.info(
                    "Processed reminder id=%s user_id=%s chat_id=%s",
                    reminder.id,
                    reminder.user_id,
                    reminder.chat_id,
                )
            except Exception as e:
                logger.error(f"处理提醒 {reminder.id} 失败: {e}")

    async def _send_reminder(self, reminder):
        """发送提醒"""
        if self.send_callback:
            try:
                await self.send_callback(
                    reminder.chat_id, f"⏰ 提醒: {reminder.content}"
                )
                logger.info(
                    "Sent reminder id=%s chat_id=%s", reminder.id, reminder.chat_id
                )
            except Exception as e:
                logger.error(f"发送提醒到 {reminder.chat_id} 失败: {e}")
                raise
