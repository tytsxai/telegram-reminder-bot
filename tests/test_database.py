"""数据库测试"""
import pytest
import os
import asyncio
from datetime import datetime, timedelta
from src.database.db import Database
from src.models.reminder import Reminder, RepeatType


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def db(db_path):
    return Database(db_path)


class TestDatabase:
    """Database 类测试"""
    
    @pytest.mark.asyncio
    async def test_init_db(self, db):
        await db.init_db()
        assert os.path.exists(db.db_path)
    
    @pytest.mark.asyncio
    async def test_create_reminder(self, db):
        await db.init_db()
        r = Reminder(
            user_id=123,
            chat_id=456,
            content="测试",
            remind_at=datetime.now()
        )
        result = await db.create_reminder(r)
        assert result.id is not None
    
    @pytest.mark.asyncio
    async def test_get_reminder(self, db):
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456,
            content="测试", remind_at=datetime.now()
        )
        created = await db.create_reminder(r)
        result = await db.get_reminder(created.id)
        assert result is not None
        assert result.content == "测试"
    
    @pytest.mark.asyncio
    async def test_get_reminder_not_found(self, db):
        await db.init_db()
        result = await db.get_reminder(999)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_reminders(self, db):
        await db.init_db()
        r1 = Reminder(user_id=123, chat_id=456, content="1", remind_at=datetime.now())
        r2 = Reminder(user_id=123, chat_id=456, content="2", remind_at=datetime.now())
        await db.create_reminder(r1)
        await db.create_reminder(r2)
        results = await db.get_user_reminders(123)
        assert len(results) == 2
    
    @pytest.mark.asyncio
    async def test_get_pending_reminders(self, db):
        await db.init_db()
        past = datetime.now() - timedelta(hours=1)
        r = Reminder(user_id=123, chat_id=456, content="过期", remind_at=past)
        await db.create_reminder(r)
        results = await db.get_pending_reminders()
        assert len(results) >= 1
    
    @pytest.mark.asyncio
    async def test_update_reminder(self, db):
        await db.init_db()
        r = Reminder(user_id=123, chat_id=456, content="原始", remind_at=datetime.now())
        created = await db.create_reminder(r)
        created.content = "更新后"
        result = await db.update_reminder(created)
        assert result is True
        updated = await db.get_reminder(created.id)
        assert updated.content == "更新后"
    
    @pytest.mark.asyncio
    async def test_update_reminder_no_id(self, db):
        await db.init_db()
        r = Reminder(user_id=123, chat_id=456, content="无ID", remind_at=datetime.now())
        result = await db.update_reminder(r)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_reminder(self, db):
        await db.init_db()
        r = Reminder(user_id=123, chat_id=456, content="删除", remind_at=datetime.now())
        created = await db.create_reminder(r)
        result = await db.delete_reminder(created.id)
        assert result is True
        deleted = await db.get_reminder(created.id)
        assert deleted is None
    
    @pytest.mark.asyncio
    async def test_delete_reminder_not_found(self, db):
        await db.init_db()
        result = await db.delete_reminder(999)
        assert result is False
