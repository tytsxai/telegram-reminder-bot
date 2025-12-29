"""AI解析接口模块"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import pytz
from src.models.reminder import RepeatType
from src.config import settings
from src.utils.time_utils import add_months


@dataclass
class ParseResult:
    """解析结果"""

    content: str
    remind_at: datetime
    repeat_type: RepeatType = RepeatType.NONE
    repeat_weekday: Optional[int] = None
    repeat_monthday: Optional[int] = None


class AIParser(ABC):
    """AI解析器抽象基类"""

    @abstractmethod
    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本"""
        pass


class RuleBasedParser(AIParser):
    """基于规则的解析器"""

    _WEEKDAY_MAP = {
        "一": 0,
        "二": 1,
        "三": 2,
        "四": 3,
        "五": 4,
        "六": 5,
        "日": 6,
        "天": 6,
    }

    def __init__(self, timezone: Optional[str] = None):
        self.tz = pytz.timezone(timezone or settings.TIMEZONE)

    def _get_now(self) -> datetime:
        """获取当前时区时间"""
        return datetime.now(self.tz).replace(tzinfo=None)

    def _parse_time(self, text: str) -> Optional[tuple[int, int]]:
        time_match = re.search(r"(\d{1,2})[点时](\d{1,2})?[分]?", text)
        if not time_match:
            return None
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        if hour > 23 or minute > 59:
            return None
        if "下午" in text or "晚上" in text or "傍晚" in text:
            if hour < 12:
                hour += 12
        if "中午" in text and hour < 12:
            hour += 12
        if "凌晨" in text and hour == 12:
            hour = 0
        if "上午" in text and hour == 12:
            hour = 0
        return hour, minute

    def _next_weekday(
        self, base: datetime, weekday: int, hour: int, minute: int
    ) -> datetime:
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (weekday - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)
        if candidate <= base:
            candidate = candidate + timedelta(days=7)
        return candidate

    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本"""
        now = self._get_now()
        remind_at = None
        repeat_type = RepeatType.NONE
        repeat_weekday = None
        repeat_monthday = None
        content = text

        # 解析重复类型
        if "每天" in text or "每日" in text:
            repeat_type = RepeatType.DAILY
        elif "每周" in text or "每星期" in text:
            repeat_type = RepeatType.WEEKLY
        elif "每月" in text:
            repeat_type = RepeatType.MONTHLY

        weekday_match = re.search(r"(?:每周|每星期)([一二三四五六日天])", text)
        if weekday_match:
            repeat_type = RepeatType.WEEKLY
            repeat_weekday = self._WEEKDAY_MAP[weekday_match.group(1)]

        monthday_match = re.search(r"(?:每月)?(\d{1,2})[号日]", text)
        if monthday_match and "每月" in text:
            day = int(monthday_match.group(1))
            if not 1 <= day <= 31:
                return None
            repeat_type = RepeatType.MONTHLY
            repeat_monthday = day

        # 解析日期
        if "今天" in text:
            remind_at = now
        elif "明天" in text:
            remind_at = now + timedelta(days=1)
        elif "后天" in text:
            remind_at = now + timedelta(days=2)

        # 解析时间
        parsed_time = self._parse_time(text)
        if parsed_time is None:
            return None
        hour, minute = parsed_time
        if remind_at is None:
            remind_at = now
        remind_at = remind_at.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # 提取提醒内容
        content_match = re.search(r"提醒我?(.+)", text)
        if content_match:
            content = content_match.group(1).strip()

        if remind_at is None:
            return None

        # 根据重复类型调整到最近一次触发时间
        if repeat_type == RepeatType.WEEKLY:
            if repeat_weekday is None:
                repeat_weekday = remind_at.weekday()
            remind_at = self._next_weekday(now, repeat_weekday, hour, minute)
        elif repeat_type == RepeatType.MONTHLY:
            if repeat_monthday is None:
                repeat_monthday = remind_at.day
            remind_at = add_months(remind_at, 0, target_day=repeat_monthday).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if remind_at <= now:
                remind_at = add_months(remind_at, 1, target_day=repeat_monthday)
        elif repeat_type in (RepeatType.DAILY, RepeatType.NONE):
            if remind_at <= now:
                remind_at = remind_at + timedelta(days=1)

        return ParseResult(
            content=content,
            remind_at=remind_at,
            repeat_type=repeat_type,
            repeat_weekday=repeat_weekday,
            repeat_monthday=repeat_monthday,
        )


class OpenAIParser(AIParser):
    """OpenAI 解析器 (预留接口)"""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model

    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本 - 预留实现"""
        raise NotImplementedError(
            "OpenAI parser not implemented. " "Please implement with OpenAI API."
        )


class ClaudeParser(AIParser):
    """Claude 解析器 (预留接口)"""

    def __init__(self, api_key: str, model: str = "claude-3"):
        self.api_key = api_key
        self.model = model

    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本 - 预留实现"""
        raise NotImplementedError(
            "Claude parser not implemented. " "Please implement with Anthropic API."
        )
