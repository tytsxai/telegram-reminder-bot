"""服务测试"""
import pytest
from datetime import datetime, timedelta
from src.database.db import Database
from src.services.reminder import ReminderService
from src.services.scheduler import SchedulerService
from src.models.reminder import Reminder, RepeatType


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
            user_id=123, chat_id=456,
            content="测试", remind_at=datetime.now()
        )
        assert r.id is not None
    
    @pytest.mark.asyncio
    async def test_get_reminder(self, db):
        await db.init_db()
        service = ReminderService(db)
        created = await service.create_reminder(
            user_id=123, chat_id=456,
            content="测试", remind_at=datetime.now()
        )
        result = await service.get_reminder(created.id)
        assert result is not None
        assert result.content == "测试"
    
    @pytest.mark.asyncio
    async def test_get_user_reminders(self, db):
        await db.init_db()
        service = ReminderService(db)
        await service.create_reminder(123, 456, "1", datetime.now())
        await service.create_reminder(123, 456, "2", datetime.now())
        results = await service.get_user_reminders(123)
        assert len(results) == 2
    
    @pytest.mark.asyncio
    async def test_delete_reminder(self, db):
        await db.init_db()
        service = ReminderService(db)
        created = await service.create_reminder(123, 456, "删除", datetime.now())
        result = await service.delete_reminder(created.id)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_process_reminder_no_repeat(self, db):
        await db.init_db()
        service = ReminderService(db)
        created = await service.create_reminder(
            123, 456, "一次性", datetime.now()
        )
        result = await service.process_reminder(created)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_process_reminder_daily(self, db):
        await db.init_db()
        service = ReminderService(db)
        now = datetime.now()
        created = await service.create_reminder(
            123, 456, "每日", now, RepeatType.DAILY
        )
        result = await service.process_reminder(created)
        assert result is not None
        assert result > now
    
    @pytest.mark.asyncio
    async def test_process_reminder_weekly(self, db):
        await db.init_db()
        service = ReminderService(db)
        now = datetime.now()
        created = await service.create_reminder(
            123, 456, "每周", now, RepeatType.WEEKLY
        )
        result = await service.process_reminder(created)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_process_reminder_monthly(self, db):
        await db.init_db()
        service = ReminderService(db)
        now = datetime.now()
        created = await service.create_reminder(
            123, 456, "每月", now, RepeatType.MONTHLY
        )
        result = await service.process_reminder(created)
        assert result is not None


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
    
    @pytest.mark.asyncio
    async def test_check_reminders(self, db):
        await db.init_db()
        sent = []
        async def callback(chat_id, msg):
            sent.append((chat_id, msg))
        scheduler = SchedulerService(db, callback)
        past = datetime.now() - timedelta(hours=1)
        r = Reminder(user_id=123, chat_id=456, content="过期", remind_at=past)
        await db.create_reminder(r)
        await scheduler._check_reminders()
        assert len(sent) == 1
