"""AI解析器测试"""

import pytest
from datetime import datetime
from src.services.ai_parser import (
    ParseResult,
    RuleBasedParser,
    OpenAIParser,
    ClaudeParser,
)
from src.models.reminder import RepeatType


class TestParseResult:
    """ParseResult 测试"""

    def test_create(self):
        now = datetime.now()
        r = ParseResult("测试", now)
        assert r.content == "测试"
        assert r.remind_at == now
        assert r.repeat_type == RepeatType.NONE


class TestRuleBasedParser:
    """RuleBasedParser 测试"""

    def test_parse_today(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("今天9点提醒我开会")
        assert result is not None
        assert result.remind_at == datetime(2025, 1, 1, 9, 0, 0)
        assert "开会" in result.content

    def test_parse_tomorrow(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("明天上午9点提醒我开会")
        assert result is not None
        assert result.remind_at == datetime(2025, 1, 2, 9, 0, 0)
        assert result.remind_at.hour == 9

    def test_parse_afternoon(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("今天下午3点提醒我喝水")
        assert result is not None
        assert result.remind_at.hour == 15

    def test_parse_daily_repeat(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 10, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("每天8点提醒我喝水")
        assert result is not None
        assert result.repeat_type == RepeatType.DAILY
        assert result.remind_at == datetime(2025, 1, 2, 8, 0, 0)

    def test_parse_weekly_repeat(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 10, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("每周一8点提醒我开会")
        assert result is not None
        assert result.repeat_type == RepeatType.WEEKLY
        assert result.repeat_weekday == 0
        assert result.remind_at == datetime(2025, 1, 6, 8, 0, 0)

    def test_parse_monthly_repeat(self, monkeypatch):
        fixed_now = datetime(2025, 1, 15, 10, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("每月1号8点提醒我交房租")
        assert result is not None
        assert result.repeat_type == RepeatType.MONTHLY
        assert result.repeat_monthday == 1
        assert result.remind_at == datetime(2025, 2, 1, 8, 0, 0)

    def test_parse_past_time_rolls_forward(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 10, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("今天9点提醒我开会")
        assert result is not None
        assert result.remind_at == datetime(2025, 1, 2, 9, 0, 0)

    def test_parse_no_time(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("提醒我开会")
        assert result is None

    def test_parse_day_after_tomorrow(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("后天10点提醒我买菜")
        assert result is not None
        assert result.remind_at == datetime(2025, 1, 3, 10, 0, 0)


class TestOpenAIParser:
    """OpenAIParser 测试"""

    def test_init(self):
        parser = OpenAIParser("sk-test", "gpt-4")
        assert parser.api_key == "sk-test"
        assert parser.model == "gpt-4"

    def test_parse_not_implemented(self):
        parser = OpenAIParser("sk-test")
        with pytest.raises(NotImplementedError):
            parser.parse("测试")


class TestClaudeParser:
    """ClaudeParser 测试"""

    def test_init(self):
        parser = ClaudeParser("sk-test", "claude-3")
        assert parser.api_key == "sk-test"
        assert parser.model == "claude-3"

    def test_parse_not_implemented(self):
        parser = ClaudeParser("sk-test")
        with pytest.raises(NotImplementedError):
            parser.parse("测试")
