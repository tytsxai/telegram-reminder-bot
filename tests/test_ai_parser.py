"""AI解析器测试"""

from datetime import datetime
from src.services.ai_parser import (
    ParseResult,
    RuleBasedParser,
    OpenAIParser,
    ClaudeParser,
    SiliconFlowParser,
    get_default_parser,
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

    def test_parse_next_week(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("下周一9点提醒我开会")
        assert result is not None
        assert result.remind_at == datetime(2025, 1, 6, 9, 0, 0)

    def test_parse_explicit_date(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("2025-01-05 9点提醒我开会")
        assert result is not None
        assert result.remind_at == datetime(2025, 1, 5, 9, 0, 0)

    def test_parse_past_explicit_date_rejected(self, monkeypatch):
        fixed_now = datetime(2025, 1, 2, 10, 0, 0)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        parser = RuleBasedParser()
        result = parser.parse("2024-12-31 9点提醒我开会")
        assert result is None


class TestOpenAIParser:
    """OpenAIParser 测试"""

    def test_init(self):
        parser = OpenAIParser("sk-test", "gpt-4")
        assert parser.api_key == "sk-test"
        assert parser.model == "gpt-4"

    def test_parse_success(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        parser = OpenAIParser("sk-test", "gpt-test")
        monkeypatch.setattr(OpenAIParser, "_get_now", lambda self: fixed_now)
        monkeypatch.setattr(
            OpenAIParser,
            "_call_api",
            lambda self, text: '{"content":"开会","remind_at":"2025-01-01 09:00","repeat_type":"none"}',
        )
        result = parser.parse("明天9点提醒我开会")
        assert result is not None
        assert result.content == "开会"
        assert result.remind_at == datetime(2025, 1, 1, 9, 0, 0)

    def test_parse_fallback_when_unconfigured(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        fallback = RuleBasedParser()
        parser = OpenAIParser(api_key=None, model=None, fallback=fallback)
        monkeypatch.setattr(RuleBasedParser, "_get_now", lambda self: fixed_now)
        result = parser.parse("明天9点提醒我开会")
        assert result is not None


class TestClaudeParser:
    """ClaudeParser 测试"""

    def test_init(self):
        parser = ClaudeParser("sk-test", "claude-3")
        assert parser.api_key == "sk-test"
        assert parser.model == "claude-3"

    def test_parse_success(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        parser = ClaudeParser("sk-test", "claude-test")
        monkeypatch.setattr(ClaudeParser, "_get_now", lambda self: fixed_now)
        monkeypatch.setattr(
            ClaudeParser,
            "_call_api",
            lambda self, text: '{"content":"买菜","remind_at":"2025-01-01 10:00","repeat_type":"none"}',
        )
        result = parser.parse("后天10点提醒我买菜")
        assert result is not None
        assert result.content == "买菜"
        assert result.remind_at == datetime(2025, 1, 1, 10, 0, 0)


class TestDefaultParser:
    """默认解析器选择测试"""

    def test_default_parser_falls_back_to_rule(self, monkeypatch):
        monkeypatch.setattr("src.config.settings.AI_PROVIDER", None)
        monkeypatch.setattr("src.config.settings.AI_API_KEY", None)
        monkeypatch.setattr("src.config.settings.OPENAI_API_KEY", None)
        monkeypatch.setattr("src.config.settings.ANTHROPIC_API_KEY", None)
        parser = get_default_parser()
        assert isinstance(parser, RuleBasedParser)


class TestLLMJSONHelpers:
    """通用 JSON 解析辅助函数测试"""

    def test_extract_json_variants(self):
        parser = SiliconFlowParser(api_key="sk-test")
        assert parser._extract_json('{"content":"a"}')["content"] == "a"
        fenced = '```json\\n{"content":"b"}\\n```'
        assert parser._extract_json(fenced)["content"] == "b"
        mixed = 'prefix {"content":"c"} suffix'
        assert parser._extract_json(mixed)["content"] == "c"

    def test_parse_datetime_and_repeat_fields(self):
        parser = SiliconFlowParser(api_key="sk-test")
        ts = 1_700_000_000_000
        assert parser._parse_datetime(ts) is not None
        assert parser._parse_repeat_type("weekly") == RepeatType.WEEKLY
        assert parser._parse_weekday("周二") == 1
        assert parser._parse_weekday("2") == 2
        assert parser._parse_monthday("15") == 15
        assert parser._parse_monthday("99") is None

    def test_parse_with_repeat_weekday_infers_weekly(self, monkeypatch):
        fixed_now = datetime(2025, 1, 1, 8, 0, 0)
        parser = SiliconFlowParser(api_key="sk-test", model="m")
        monkeypatch.setattr(SiliconFlowParser, "_get_now", lambda self: fixed_now)
        monkeypatch.setattr(
            SiliconFlowParser,
            "_call_api",
            lambda self, text: '{"content":"测试","remind_at":"2025-01-01 07:00","repeat_weekday":2}',
        )
        result = parser.parse("提醒我测试")
        assert result is not None
        assert result.repeat_type == RepeatType.WEEKLY

    def test_extract_json_invalid_fragment(self):
        parser = SiliconFlowParser(api_key="sk-test")
        assert parser._extract_json("prefix {invalid} suffix") is None

    def test_parse_datetime_iso_timezone(self):
        parser = SiliconFlowParser(api_key="sk-test")
        dt = parser._parse_datetime("2025-01-01T09:00:00+00:00")
        assert dt is not None
        assert dt.tzinfo is None

    def test_parse_weekday_and_repeat_type_edges(self):
        parser = SiliconFlowParser(api_key="sk-test")
        assert parser._parse_weekday(7) == 6
        assert parser._parse_repeat_type("不重复") == RepeatType.NONE
