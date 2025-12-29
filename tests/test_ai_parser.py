"""AI解析器测试"""
import pytest
from datetime import datetime
from src.services.ai_parser import (
    ParseResult, AIParser, RuleBasedParser,
    OpenAIParser, ClaudeParser
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
    
    def test_parse_today(self):
        parser = RuleBasedParser()
        result = parser.parse("今天9点提醒我开会")
        assert result is not None
        assert "开会" in result.content
    
    def test_parse_tomorrow(self):
        parser = RuleBasedParser()
        result = parser.parse("明天上午9点提醒我开会")
        assert result is not None
        assert result.remind_at.hour == 9
    
    def test_parse_afternoon(self):
        parser = RuleBasedParser()
        result = parser.parse("今天下午3点提醒我喝水")
        assert result is not None
        assert result.remind_at.hour == 15
    
    def test_parse_daily_repeat(self):
        parser = RuleBasedParser()
        result = parser.parse("每天8点提醒我喝水")
        assert result is not None
        assert result.repeat_type == RepeatType.DAILY
    
    def test_parse_weekly_repeat(self):
        parser = RuleBasedParser()
        result = parser.parse("每周一8点提醒我开会")
        assert result is not None
        assert result.repeat_type == RepeatType.WEEKLY
    
    def test_parse_monthly_repeat(self):
        parser = RuleBasedParser()
        result = parser.parse("每月1号8点提醒我交房租")
        assert result is not None
        assert result.repeat_type == RepeatType.MONTHLY
    
    def test_parse_no_time(self):
        parser = RuleBasedParser()
        result = parser.parse("提醒我开会")
        assert result is None
    
    def test_parse_day_after_tomorrow(self):
        parser = RuleBasedParser()
        result = parser.parse("后天10点提醒我买菜")
        assert result is not None


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
