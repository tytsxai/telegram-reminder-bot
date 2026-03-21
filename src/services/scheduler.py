"""调度器服务模块

定时扫描到期提醒并发送通知，支持：
- 批量领取与锁定（防并发重复）
- 发送尝试标记（降低崩溃后的重复发送）
- 限流重试（RetryAfter）
- 用户屏蔽自动停用（Forbidden）
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Awaitable, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram.error import BadRequest, Forbidden, RetryAfter

from src.config import settings
from src.database.db import Database
from src.services.reminder import ReminderService
from src.utils.text_utils import truncate_utf16, utf16_length
from src.utils.time_utils import now_in_timezone, now_utc

logger = logging.getLogger(__name__)


class SchedulerService:
    """调度器服务"""

    _MAX_CONSECUTIVE_CLAIM_FAILURES = 3
    _MAX_CONSECUTIVE_PROCESS_FAILURES = 10

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
        self.send_timeout_seconds = settings.SCHEDULER_SEND_TIMEOUT_SECONDS

        # 这些字段用于健康检查与运维排查，避免调度器无声失败。
        self._last_tick_at = None
        self._last_error = None
        self._run_count = 0
        self._error_count = 0
        self._send_success = 0
        self._send_failed = 0
        self._consecutive_claim_failures = 0
        self._consecutive_process_failures = 0
        self._last_success_at = None

    def _max_lag_seconds(self) -> int:
        return max(int(self.interval_seconds * 3), 90)

    def _build_message(self, reminder) -> str:
        """Build a safe message payload within Telegram limits."""
        prefix = "⏰ 提醒: "
        suffix = "..."
        max_len = 4096
        available = max_len - utf16_length(prefix) - utf16_length(suffix)
        if available <= 0:
            return truncate_utf16(f"{prefix}{reminder.content}", max_len)
        safe_content = truncate_utf16(reminder.content, available, suffix=suffix)
        return f"{prefix}{safe_content}"

    def _mark_processing_failure(self, reason: str) -> None:
        self._error_count += 1
        self._consecutive_process_failures += 1
        self._last_error = reason

    async def _delay_retry(self, reminder, *, delay_seconds: int, reason: str) -> None:
        """设置重试窗口，避免短时间重复认领导致重试风暴。"""
        now_local = now_in_timezone()
        desired = now_local + timedelta(seconds=max(delay_seconds, self.lock_seconds))
        if reminder.locked_until is None or reminder.locked_until < desired:
            reminder.locked_until = desired
        reminder.send_attempt_for = reminder.remind_at
        reminder.send_attempt_until = desired
        try:
            await self.db.update_reminder(reminder)
        except Exception as update_exc:
            logger.error(
                "Failed to set retry window for reminder id=%s (%s): %s",
                reminder.id,
                reason,
                update_exc,
            )

    def is_healthy(self) -> bool:
        """判断调度器是否健康。"""
        if not self.scheduler.running:
            return False
        if self._consecutive_claim_failures >= self._MAX_CONSECUTIVE_CLAIM_FAILURES:
            return False
        if self._consecutive_process_failures >= self._MAX_CONSECUTIVE_PROCESS_FAILURES:
            return False
        if self._last_tick_at is None:
            # 刚启动时允许短暂空窗，避免误报。
            return True
        lag_seconds = (now_utc() - self._last_tick_at).total_seconds()
        return lag_seconds <= self._max_lag_seconds()

    def health_snapshot(self) -> dict:
        """返回调度器健康快照信息。"""
        last_tick = self._last_tick_at.isoformat() if self._last_tick_at else None
        last_success = (
            self._last_success_at.isoformat() if self._last_success_at else None
        )
        lag_seconds = None
        if self._last_tick_at is not None:
            lag_seconds = max(0, (now_utc() - self._last_tick_at).total_seconds())
        return {
            "running": self.scheduler.running,
            "interval_seconds": self.interval_seconds,
            "send_timeout_seconds": self.send_timeout_seconds,
            "last_tick_at": last_tick,
            "lag_seconds": lag_seconds,
            "last_error": self._last_error,
            "run_count": self._run_count,
            "error_count": self._error_count,
            "send_success": self._send_success,
            "send_failed": self._send_failed,
            "last_success_at": last_success,
            "consecutive_claim_failures": self._consecutive_claim_failures,
            "consecutive_process_failures": self._consecutive_process_failures,
        }

    def start(self):
        """启动调度器"""
        if self.scheduler.running:
            logger.info("Scheduler already running, skip duplicate start")
            return
        self.scheduler.add_job(
            self._check_reminders,
            IntervalTrigger(seconds=self.interval_seconds),
            id="check_reminders",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()

    def stop(self, wait: bool = True):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)

    async def _check_reminders(self):
        """检查并发送到期提醒"""
        self._last_tick_at = now_utc()
        self._run_count += 1
        if self._run_count % 100 == 0:
            await self.db.checkpoint()
        self._last_error = None
        try:
            reminders = await self.db.claim_pending_reminders(
                self.batch_size, self.lock_seconds
            )
        except Exception as exc:
            self._error_count += 1
            self._consecutive_claim_failures += 1
            self._last_error = f"claim_failed: {exc}"
            logger.error("获取待发送提醒失败: %s", exc)
            return

        self._consecutive_claim_failures = 0
        if not reminders:
            self._consecutive_process_failures = 0
            self._last_success_at = now_utc()
            return

        # 限制并发发送，降低触发限流与阻塞事件循环的风险。
        semaphore = asyncio.Semaphore(self.send_concurrency)
        processing_failures = 0

        async def _process_one(reminder):
            nonlocal processing_failures
            try:
                async with semaphore:
                    if reminder.id is not None:
                        try:
                            current = await self.db.get_reminder(reminder.id)
                        except Exception as exc:
                            processing_failures += 1
                            self._mark_processing_failure(
                                f"reload_failed reminder_id={reminder.id}: {exc}"
                            )
                            logger.error(
                                "Failed to reload reminder id=%s: %s",
                                reminder.id,
                                exc,
                            )
                            return

                        if not current or not current.is_active:
                            logger.info(
                                "Skipping reminder id=%s (deleted or inactive)",
                                reminder.id,
                            )
                            return

                        now_local = now_in_timezone()
                        if current.remind_at > now_local or (
                            current.last_sent_for is not None
                            and current.last_sent_for == current.remind_at
                        ):
                            logger.info(
                                "Skipping reminder id=%s (not due or already sent)",
                                reminder.id,
                            )
                            if (
                                current.locked_until is not None
                                or current.send_attempt_for is not None
                                or current.send_attempt_until is not None
                            ):
                                current.locked_until = None
                                current.send_attempt_for = None
                                current.send_attempt_until = None
                                try:
                                    await self.db.update_reminder(current)
                                except Exception as update_exc:
                                    processing_failures += 1
                                    self._mark_processing_failure(
                                        "clear_lock_failed "
                                        f"reminder_id={current.id}: {update_exc}"
                                    )
                                    logger.error(
                                        "Failed to clear lock for reminder id=%s: %s",
                                        current.id,
                                        update_exc,
                                    )
                            return

                        reminder = current

                    now_local = now_in_timezone()
                    # Mark in-flight attempt before send to reduce duplicate delivery.
                    reminder.locked_until = now_local + timedelta(
                        seconds=self.lock_seconds
                    )
                    reminder.send_attempt_for = reminder.remind_at
                    reminder.send_attempt_until = reminder.locked_until
                    try:
                        await self.db.update_reminder(reminder)
                    except Exception as update_exc:
                        processing_failures += 1
                        self._mark_processing_failure(
                            f"mark_attempt_failed reminder_id={reminder.id}: {update_exc}"
                        )
                        logger.error(
                            "Failed to mark send attempt for reminder id=%s: %s",
                            reminder.id,
                            update_exc,
                        )
                        return

                    try:
                        sent = await asyncio.wait_for(
                            self._send_reminder(reminder),
                            timeout=self.send_timeout_seconds,
                        )
                    except asyncio.TimeoutError:
                        self._send_failed += 1
                        processing_failures += 1
                        self._mark_processing_failure(
                            "send_timeout "
                            f"reminder_id={reminder.id} "
                            f"timeout={self.send_timeout_seconds}s"
                        )
                        await self._delay_retry(
                            reminder,
                            delay_seconds=self.lock_seconds,
                            reason="send_timeout",
                        )
                        logger.error(
                            "Send timeout for reminder id=%s chat_id=%s after %ss",
                            reminder.id,
                            reminder.chat_id,
                            self.send_timeout_seconds,
                        )
                        return
                    except Exception as exc:
                        processing_failures += 1
                        self._mark_processing_failure(
                            f"send_failed reminder_id={reminder.id}: {exc}"
                        )
                        await self._delay_retry(
                            reminder,
                            delay_seconds=self.lock_seconds,
                            reason="send_exception",
                        )
                        logger.error("处理提醒 %s 失败: %s", reminder.id, exc)
                        return

                    if not sent:
                        return

                    sent_at = now_in_timezone()
                    sent_for = reminder.remind_at
                    try:
                        await self.reminder_service.process_reminder(
                            reminder,
                            sent_at=sent_at,
                            sent_for=sent_for,
                        )
                    except Exception as exc:
                        processing_failures += 1
                        self._mark_processing_failure(
                            "post_send_process_failed "
                            f"reminder_id={reminder.id}: {exc}"
                        )
                        await self._delay_retry(
                            reminder,
                            delay_seconds=self.lock_seconds,
                            reason="post_send_process_failed",
                        )
                        logger.error(
                            "Failed to finalize reminder id=%s after send: %s",
                            reminder.id,
                            exc,
                        )
                        return

                    logger.info(
                        "Processed reminder id=%s user_id=%s chat_id=%s",
                        reminder.id,
                        reminder.user_id,
                        reminder.chat_id,
                    )
            except Exception as exc:
                processing_failures += 1
                self._mark_processing_failure(
                    f"process_failed reminder_id={getattr(reminder, 'id', None)}: {exc}"
                )
                logger.exception(
                    "Unexpected scheduler error for reminder id=%s: %s",
                    getattr(reminder, "id", None),
                    exc,
                )

        await asyncio.gather(
            *[_process_one(r) for r in reminders], return_exceptions=True
        )

        if processing_failures == 0:
            self._consecutive_process_failures = 0
            self._last_success_at = now_utc()
            return

        logger.warning(
            "Scheduler tick finished with %s processing failures",
            processing_failures,
        )

    async def _send_reminder(self, reminder) -> bool:
        """发送提醒"""
        if not self.send_callback:
            return True
        try:
            await self.send_callback(reminder.chat_id, self._build_message(reminder))
            logger.info("Sent reminder id=%s chat_id=%s", reminder.id, reminder.chat_id)
            self._send_success += 1
            return True
        except RetryAfter as exc:
            self._send_failed += 1
            delay = max(int(getattr(exc, "retry_after", 0) or 0), self.lock_seconds)
            reminder.locked_until = now_in_timezone() + timedelta(seconds=delay)
            reminder.send_attempt_for = reminder.remind_at
            reminder.send_attempt_until = reminder.locked_until
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
            self._send_failed += 1
            logger.warning(
                "Chat forbidden, deactivating reminder id=%s chat_id=%s: %s",
                reminder.id,
                reminder.chat_id,
                exc,
            )
            reminder.is_active = False
            reminder.locked_until = None
            reminder.send_attempt_for = None
            reminder.send_attempt_until = None
            try:
                await self.db.update_reminder(reminder)
            except Exception as update_exc:
                logger.error(
                    "Failed to deactivate reminder id=%s: %s",
                    reminder.id,
                    update_exc,
                )
            return False
        except BadRequest as exc:
            self._send_failed += 1
            logger.warning(
                "Bad request, deactivating reminder id=%s chat_id=%s: %s",
                reminder.id,
                reminder.chat_id,
                exc,
            )
            reminder.is_active = False
            reminder.locked_until = None
            reminder.send_attempt_for = None
            reminder.send_attempt_until = None
            try:
                await self.db.update_reminder(reminder)
            except Exception as update_exc:
                logger.error(
                    "Failed to deactivate reminder id=%s after bad request: %s",
                    reminder.id,
                    update_exc,
                )
            return False
        except Exception as exc:
            self._send_failed += 1
            logger.error("发送提醒到 %s 失败: %s", reminder.chat_id, exc)
            raise
