"""服务测试"""

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
        scheduler.start()
        assert scheduler.scheduler.add_job.called
        scheduler.scheduler.start.assert_called_once()
        scheduler.stop()
        scheduler.scheduler.shutdown.assert_called_once()

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
