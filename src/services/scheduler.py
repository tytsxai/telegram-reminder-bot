"""调度器服务模块"""

import asyncio
import logging
from datetime import timedelta
from typing import Awaitable, Callable, Optional

from telegram.error import Forbidden, RetryAfter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.config import settings
from src.database.db import Database
from src.services.reminder import ReminderService
from src.utils.time_utils import now_in_timezone

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
        self.batch_size = settings.SCHEDULER_BATCH_SIZE
        self.lock_seconds = settings.SCHEDULER_LOCK_SECONDS
        self.send_concurrency = settings.SCHEDULER_SEND_CONCURRENCY

    def start(self):
        """启动调度器"""
        self.scheduler.add_job(
            self._check_reminders,
            IntervalTrigger(seconds=self.interval_seconds),
            id="check_reminders",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def _check_reminders(self):
        """检查并发送到期提醒"""
        try:
            reminders = await self.db.claim_pending_reminders(
                self.batch_size, self.lock_seconds
            )
        except Exception as e:
            logger.error(f"获取待发送提醒失败: {e}")
            return
        if not reminders:
            return

        # 限制并发发送，降低触发限流与阻塞事件循环的风险。
        semaphore = asyncio.Semaphore(self.send_concurrency)

        async def _process_one(reminder):
            async with semaphore:
                try:
                    sent = await self._send_reminder(reminder)
                    if sent:
                        sent_at = now_in_timezone()
                        sent_for = reminder.remind_at
                        await self.reminder_service.process_reminder(
                            reminder, sent_at=sent_at, sent_for=sent_for
                        )
                        logger.info(
                            "Processed reminder id=%s user_id=%s chat_id=%s",
                            reminder.id,
                            reminder.user_id,
                            reminder.chat_id,
                        )
                except Exception as e:
                    # 避免临时失败后立即被再次认领导致重试风暴。
                    now = now_in_timezone()
                    desired = now + timedelta(seconds=self.lock_seconds)
                    if reminder.locked_until is None or reminder.locked_until < desired:
                        reminder.locked_until = desired
                    try:
                        await self.db.update_reminder(reminder)
                    except Exception as update_exc:
                        logger.error(
                            "Failed to update lock for reminder id=%s: %s",
                            reminder.id,
                            update_exc,
                        )
                    logger.error(f"处理提醒 {reminder.id} 失败: {e}")

        await asyncio.gather(*[_process_one(r) for r in reminders])

    async def _send_reminder(self, reminder) -> bool:
        """发送提醒"""
        if not self.send_callback:
            return True
        try:
            await self.send_callback(reminder.chat_id, f"⏰ 提醒: {reminder.content}")
            logger.info("Sent reminder id=%s chat_id=%s", reminder.id, reminder.chat_id)
            return True
        except RetryAfter as exc:
            delay = max(int(getattr(exc, "retry_after", 0) or 0), self.lock_seconds)
            reminder.locked_until = now_in_timezone() + timedelta(seconds=delay)
            try:
                await self.db.update_reminder(reminder)
            except Exception as update_exc:
                logger.error(
                    "Failed to delay reminder id=%s after rate limit: %s",
                    reminder.id,
                    update_exc,
                )
            logger.warning(
                "Rate limited for reminder id=%s chat_id=%s retry_after=%s",
                reminder.id,
                reminder.chat_id,
                getattr(exc, "retry_after", None),
            )
            return False
        except Forbidden as exc:
            logger.warning(
                "Chat forbidden, deactivating reminder id=%s chat_id=%s: %s",
                reminder.id,
                reminder.chat_id,
                exc,
            )
            reminder.is_active = False
            reminder.locked_until = None
            try:
                await self.db.update_reminder(reminder)
            except Exception as update_exc:
                logger.error(
                    "Failed to deactivate reminder id=%s: %s",
                    reminder.id,
                    update_exc,
                )
            return False
        except Exception as e:
            logger.error(f"发送提醒到 {reminder.chat_id} 失败: {e}")
            raise
