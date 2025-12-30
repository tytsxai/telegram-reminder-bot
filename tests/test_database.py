"""数据库测试"""

import os
import pytest
import aiosqlite
from datetime import timedelta
from src.database.db import Database
from src.models.reminder import Reminder, RepeatType
from src.utils.time_utils import now_in_timezone


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
    async def test_ping(self, db):
        await db.init_db()
        assert await db.ping() is True

    @pytest.mark.asyncio
    async def test_schema_version(self, db):
        await db.init_db()
        async with aiosqlite.connect(db.db_path) as conn:
            cursor = await conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = await cursor.fetchone()
            assert row is not None
            assert int(row[0]) >= 1

    @pytest.mark.asyncio
    async def test_create_reminder(self, db):
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456, content="测试", remind_at=now_in_timezone()
        )
        result = await db.create_reminder(r)
        assert result.id is not None

    @pytest.mark.asyncio
    async def test_get_reminder(self, db):
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456, content="测试", remind_at=now_in_timezone()
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
        r1 = Reminder(
            user_id=123, chat_id=456, content="1", remind_at=now_in_timezone()
        )
        r2 = Reminder(
            user_id=123, chat_id=456, content="2", remind_at=now_in_timezone()
        )
        await db.create_reminder(r1)
        await db.create_reminder(r2)
        results = await db.get_user_reminders(123)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_pending_reminders(self, db):
        await db.init_db()
        past = now_in_timezone() - timedelta(hours=1)
        r = Reminder(user_id=123, chat_id=456, content="过期", remind_at=past)
        await db.create_reminder(r)
        results = await db.get_pending_reminders()
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_update_reminder(self, db):
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456, content="原始", remind_at=now_in_timezone()
        )
        created = await db.create_reminder(r)
        created.content = "更新后"
        result = await db.update_reminder(created)
        assert result is True
        updated = await db.get_reminder(created.id)
        assert updated.content == "更新后"

    @pytest.mark.asyncio
    async def test_update_reminder_no_id(self, db):
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456, content="无ID", remind_at=now_in_timezone()
        )
        result = await db.update_reminder(r)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_reminder(self, db):
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456, content="删除", remind_at=now_in_timezone()
        )
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

    @pytest.mark.asyncio
    async def test_delete_reminder_by_user_success(self, db):
        """测试按用户删除提醒成功"""
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456, content="删除", remind_at=now_in_timezone()
        )
        created = await db.create_reminder(r)
        result = await db.delete_reminder_by_user(created.id, 123)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_reminder_by_user_wrong_user(self, db):
        """测试按用户删除提醒失败（用户不匹配）"""
        await db.init_db()
        r = Reminder(
            user_id=123, chat_id=456, content="删除", remind_at=now_in_timezone()
        )
        created = await db.create_reminder(r)
        result = await db.delete_reminder_by_user(created.id, 999)
        assert result is False

    @pytest.mark.asyncio
    async def test_repeat_fields_persist(self, db):
        """测试重复字段持久化"""
        await db.init_db()
        r = Reminder(
            user_id=123,
            chat_id=456,
            content="每周三",
            remind_at=now_in_timezone(),
            repeat_type=RepeatType.WEEKLY,
            repeat_weekday=2,
            repeat_monthday=15,
        )
        created = await db.create_reminder(r)
        fetched = await db.get_reminder(created.id)
        assert fetched is not None
        assert fetched.repeat_weekday == 2
        assert fetched.repeat_monthday == 15
