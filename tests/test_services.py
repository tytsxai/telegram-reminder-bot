"""服务测试"""

import asyncio

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from src.database.db import Database
from src.services.reminder import ReminderService
from src.services.scheduler import SchedulerService
from src.models.reminder import Reminder, RepeatType
from src.utils.time_utils import now_in_timezone


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def db(db_path):
    return Database(db_path)


class TestReminderService:
    """ReminderService 测试"""

    @pytest.mark.asyncio
    async def test_create_reminder(self, db):
        await db.init_db()
        service = ReminderService(db)
        r = await service.create_reminder(
            user_id=123, chat_id=456, content="测试", remind_at=now_in_timezone()
        )
        assert r.id is not None

    @pytest.mark.asyncio
    async def test_get_reminder(self, db):
        await db.init_db()
        service = ReminderService(db)
        created = await service.create_reminder(
            user_id=123, chat_id=456, content="测试", remind_at=now_in_timezone()
        )
        result = await service.get_reminder(created.id)
        assert result is not None
        assert result.content == "测试"

    @pytest.mark.asyncio
    async def test_get_user_reminders(self, db):
        await db.init_db()
        service = ReminderService(db)
        await service.create_reminder(123, 456, "1", now_in_timezone())
        await service.create_reminder(123, 456, "2", now_in_timezone())
        results = await service.get_user_reminders(123)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_delete_reminder(self, db):
        await db.init_db()
        service = ReminderService(db)
        created = await service.create_reminder(123, 456, "删除", now_in_timezone())
        result = await service.delete_reminder(created.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_reminder_by_user(self, db):
        """测试按用户删除提醒"""
        await db.init_db()
        service = ReminderService(db)
        created = await service.create_reminder(123, 456, "删除", now_in_timezone())
        result = await service.delete_reminder_by_user(created.id, 123, 456)
        assert result is True

    @pytest.mark.asyncio
    async def test_process_reminder_no_repeat(self, db):
        await db.init_db()
        service = ReminderService(db)
        created = await service.create_reminder(123, 456, "一次性", now_in_timezone())
        result = await service.process_reminder(created)
        assert result is None

    @pytest.mark.asyncio
    async def test_process_reminder_daily(self, db):
        await db.init_db()
        service = ReminderService(db)
        now = now_in_timezone()
        created = await service.create_reminder(123, 456, "每日", now, RepeatType.DAILY)
        result = await service.process_reminder(created)
        assert result is not None
        assert result > now

    @pytest.mark.asyncio
    async def test_process_reminder_weekly(self, db):
        await db.init_db()
        service = ReminderService(db)
        now = now_in_timezone()
        created = await service.create_reminder(
            123, 456, "每周", now, RepeatType.WEEKLY
        )
        result = await service.process_reminder(created)
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_reminder_monthly(self, db):
        await db.init_db()
        service = ReminderService(db)
        now = now_in_timezone()
        created = await service.create_reminder(
            123, 456, "每月", now, RepeatType.MONTHLY
        )
        result = await service.process_reminder(created)
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_reminder_monthly_target_day(self, db, monkeypatch):
        await db.init_db()
        service = ReminderService(db)
        fixed_now = datetime(2025, 1, 15, 10, 0, 0)
        monkeypatch.setattr("src.services.reminder.now_in_timezone", lambda: fixed_now)
        base = datetime(2025, 1, 31, 9, 0, 0)
        created = await service.create_reminder(
            123, 456, "每月31号", base, RepeatType.MONTHLY, repeat_monthday=31
        )
        result = await service.process_reminder(created)
        assert result is not None
        assert result.month == 2
        assert result.day in (28, 29)


class TestSchedulerService:
    """SchedulerService 测试"""

    def test_init(self, db):
        scheduler = SchedulerService(db)
        assert scheduler.db == db
        assert scheduler.send_callback is None

    def test_init_with_callback(self, db):
        async def callback(chat_id, msg):
            pass

        scheduler = SchedulerService(db, callback)
        assert scheduler.send_callback is not None

    @pytest.mark.asyncio
    async def test_start_stop(self, db):
        await db.init_db()
        scheduler = SchedulerService(db)
        # 跳过实际启动测试，验证初始化
        assert scheduler.scheduler is not None

    def test_start_stop_calls_scheduler(self, db):
        scheduler = SchedulerService(db)
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.running = False
        scheduler.start()
        assert scheduler.scheduler.add_job.called
        scheduler.scheduler.start.assert_called_once()
        scheduler.scheduler.running = True
        scheduler.stop()
        scheduler.scheduler.shutdown.assert_called_once_with(wait=True)

    def test_start_skips_when_running(self, db):
        scheduler = SchedulerService(db)
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.running = True
        scheduler.start()
        scheduler.scheduler.add_job.assert_not_called()
        scheduler.scheduler.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_reminders(self, db):
        await db.init_db()
        sent = []

        async def callback(chat_id, msg):
            sent.append((chat_id, msg))

        scheduler = SchedulerService(db, callback)
        past = now_in_timezone() - timedelta(hours=1)
        r = Reminder(user_id=123, chat_id=456, content="过期", remind_at=past)
        await db.create_reminder(r)
        await scheduler._check_reminders()
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_scheduler_becomes_unhealthy_after_consecutive_claim_failures(
        self, db
    ):
        await db.init_db()
        scheduler = SchedulerService(db)
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.running = True

        async def _raise_once(*_args, **_kwargs):
            raise RuntimeError("db down")

        scheduler.db.claim_pending_reminders = _raise_once

        for _ in range(3):
            await scheduler._check_reminders()

        snapshot = scheduler.health_snapshot()
        assert scheduler.is_healthy() is False
        assert snapshot["consecutive_claim_failures"] == 3
        assert "claim_failed" in (snapshot["last_error"] or "")

    @pytest.mark.asyncio
    async def test_scheduler_claim_failure_counter_resets_after_success(self, db):
        await db.init_db()
        scheduler = SchedulerService(db)
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.running = True

        async def _raise_once(*_args, **_kwargs):
            raise RuntimeError("temporary db error")

        scheduler.db.claim_pending_reminders = _raise_once
        await scheduler._check_reminders()
        assert scheduler.health_snapshot()["consecutive_claim_failures"] == 1

        async def _ok(*_args, **_kwargs):
            return []

        scheduler.db.claim_pending_reminders = _ok
        await scheduler._check_reminders()

        snapshot = scheduler.health_snapshot()
        assert scheduler.is_healthy() is True
        assert snapshot["consecutive_claim_failures"] == 0
        assert snapshot["last_success_at"] is not None

    @pytest.mark.asyncio
    async def test_check_reminders_forbidden_deactivates(self, db):
        await db.init_db()

        async def callback(chat_id, msg):
            from telegram.error import Forbidden

            raise Forbidden("blocked")

        scheduler = SchedulerService(db, callback)
        past = now_in_timezone() - timedelta(hours=1)
        r = Reminder(user_id=123, chat_id=456, content="过期", remind_at=past)
        created = await db.create_reminder(r)
        await scheduler._check_reminders()
        updated = await db.get_reminder(created.id)
        assert updated is not None
        assert updated.is_active is False

    @pytest.mark.asyncio
    async def test_check_reminders_timeout_sets_retry_window(self, db):
        await db.init_db()

        async def callback(chat_id, msg):
            await asyncio.sleep(0.05)

        scheduler = SchedulerService(db, callback)
        scheduler.send_timeout_seconds = 0.01
        scheduler.lock_seconds = 1

        past = now_in_timezone() - timedelta(hours=1)
        r = Reminder(user_id=123, chat_id=456, content="超时", remind_at=past)
        created = await db.create_reminder(r)

        await scheduler._check_reminders()

        updated = await db.get_reminder(created.id)
        assert updated is not None
        assert updated.is_active is True
        assert updated.locked_until is not None
        assert updated.send_attempt_for == updated.remind_at
        assert updated.send_attempt_until is not None
        snapshot = scheduler.health_snapshot()
        assert snapshot["send_failed"] >= 1
        assert snapshot["consecutive_process_failures"] >= 1

    @pytest.mark.asyncio
    async def test_scheduler_unhealthy_after_consecutive_process_failures(self, db):
        await db.init_db()
        scheduler = SchedulerService(db)
        scheduler.scheduler = MagicMock()
        scheduler.scheduler.running = True

        due = now_in_timezone() - timedelta(minutes=1)
        reminder = Reminder(
            id=1, user_id=123, chat_id=456, content="失败", remind_at=due
        )

        async def _claim(*_args, **_kwargs):
            return [reminder]

        async def _reload(*_args, **_kwargs):
            raise RuntimeError("db reload failed")

        scheduler.db.claim_pending_reminders = _claim
        scheduler.db.get_reminder = _reload

        for _ in range(10):
            await scheduler._check_reminders()

        snapshot = scheduler.health_snapshot()
        assert snapshot["consecutive_process_failures"] >= 10
        assert scheduler.is_healthy() is False
