"""模型测试"""
import pytest
from datetime import datetime
from src.models.reminder import Reminder, RepeatType


class TestRepeatType:
    """RepeatType 枚举测试"""
    
    def test_values(self):
        assert RepeatType.NONE.value == "none"
        assert RepeatType.DAILY.value == "daily"
        assert RepeatType.WEEKLY.value == "weekly"
        assert RepeatType.MONTHLY.value == "monthly"
    
    def test_from_string(self):
        assert RepeatType("none") == RepeatType.NONE
        assert RepeatType("daily") == RepeatType.DAILY


class TestReminder:
    """Reminder 模型测试"""
    
    def test_create_reminder(self):
        now = datetime.now()
        r = Reminder(
            user_id=123,
            chat_id=456,
            content="测试提醒",
            remind_at=now
        )
        assert r.user_id == 123
        assert r.chat_id == 456
        assert r.content == "测试提醒"
        assert r.repeat_type == RepeatType.NONE
        assert r.is_active is True
    
    def test_to_dict(self):
        now = datetime.now()
        r = Reminder(
            id=1,
            user_id=123,
            chat_id=456,
            content="测试",
            remind_at=now,
            created_at=now
        )
        d = r.to_dict()
        assert d["id"] == 1
        assert d["user_id"] == 123
        assert d["content"] == "测试"
    
    def test_from_dict(self):
        now = datetime.now()
        data = {
            "id": 1,
            "user_id": 123,
            "chat_id": 456,
            "content": "测试",
            "remind_at": now.isoformat(),
            "repeat_type": "daily",
            "is_active": True,
            "created_at": now.isoformat()
        }
        r = Reminder.from_dict(data)
        assert r.id == 1
        assert r.repeat_type == RepeatType.DAILY
