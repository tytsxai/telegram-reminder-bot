"""AI解析接口模块"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import pytz

from src.config import settings
from src.models.reminder import RepeatType
from src.utils.time_utils import add_months

logger = logging.getLogger(__name__)


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
        raise NotImplementedError


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

        next_week_match = re.search(r"下周([一二三四五六日天])", text)
        if next_week_match:
            weekday = self._WEEKDAY_MAP[next_week_match.group(1)]
            remind_at = self._next_weekday(now, weekday, now.hour, now.minute)

        date_match = re.search(r"(\d{4})[年/\-](\d{1,2})[月/\-](\d{1,2})[日号]?", text)
        if date_match:
            year, month, day = map(int, date_match.groups())
            try:
                remind_at = datetime(year, month, day)
            except ValueError:
                return None

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


class LLMJSONParser(AIParser):
    """通用 JSON 输出解析基类"""

    _WEEKDAY_MAP = {
        "一": 0,
        "二": 1,
        "三": 2,
        "四": 3,
        "五": 4,
        "六": 5,
        "日": 6,
        "天": 6,
        "周一": 0,
        "周二": 1,
        "周三": 2,
        "周四": 3,
        "周五": 4,
        "周六": 5,
        "周日": 6,
        "周天": 6,
        "星期一": 0,
        "星期二": 1,
        "星期三": 2,
        "星期四": 3,
        "星期五": 4,
        "星期六": 5,
        "星期日": 6,
        "星期天": 6,
        "mon": 0,
        "monday": 0,
        "tue": 1,
        "tues": 1,
        "tuesday": 1,
        "wed": 2,
        "weds": 2,
        "wednesday": 2,
        "thu": 3,
        "thur": 3,
        "thurs": 3,
        "thursday": 3,
        "fri": 4,
        "friday": 4,
        "sat": 5,
        "saturday": 5,
        "sun": 6,
        "sunday": 6,
    }

    def __init__(
        self,
        timezone: Optional[str] = None,
        timeout_seconds: int = 15,
        fallback: Optional[AIParser] = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.tz = pytz.timezone(timezone or settings.TIMEZONE)
        self.fallback = fallback or RuleBasedParser(timezone or settings.TIMEZONE)

    def _fallback_parse(self, text: str) -> Optional[ParseResult]:
        return self.fallback.parse(text) if self.fallback else None

    def _is_configured(self) -> bool:
        return True

    def _get_now(self) -> datetime:
        """获取当前时区时间"""
        return datetime.now(self.tz).replace(tzinfo=None)

    def _build_prompt(self, now: datetime) -> str:
        now_str = now.strftime("%Y-%m-%d %H:%M")
        return (
            "你是提醒时间解析器。\n"
            f"当前时间：{now_str}（时区 {self.tz.zone}）。\n"
            "请从用户输入中提取提醒信息，并严格输出 JSON 对象。\n"
            "字段说明：\n"
            "1) content: 提醒内容，字符串。\n"
            '2) remind_at: 具体提醒时间，格式为 "YYYY-MM-DD HH:MM"，无法确定时为 null。\n'
            '3) repeat_type: "none" | "daily" | "weekly" | "monthly"。\n'
            "4) repeat_weekday: 周几（0=周一...6=周日），仅 weekly 使用，否则为 null。\n"
            "5) repeat_monthday: 月内日期（1-31），仅 monthly 使用，否则为 null。\n"
            "规则：\n"
            "- 识别中文相对时间（今天/明天/后天/下周X/下个月X号）并换算为具体日期。\n"
            "- 若仅给出时间无日期，默认使用最近一次发生的日期。\n"
            "- 必须只输出 JSON，不要输出额外文本或代码块。\n"
        )

    def _call_api(self, text: str) -> Optional[str]:
        raise NotImplementedError

    def _extract_json(self, content: str) -> Optional[dict]:
        if not content:
            return None
        stripped = content.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # 去除代码块包裹
        fenced = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        fenced = re.sub(r"```$", "", fenced).strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 片段
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
        return None

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 1e12:
                timestamp = timestamp / 1000
            dt = datetime.fromtimestamp(timestamp, tz=self.tz)
            return dt.replace(tzinfo=None)
        if not isinstance(value, str):
            return None
        text = value.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            dt = None
        if dt is None:
            for fmt in (
                "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
            ):
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            return None
        if dt.tzinfo:
            dt = dt.astimezone(self.tz).replace(tzinfo=None)
        return dt

    def _parse_repeat_type(self, value: Any) -> Optional[RepeatType]:
        if value is None:
            return None
        if isinstance(value, RepeatType):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v in {"none", "no", "null", "不重复", "无", "不"}:
                return RepeatType.NONE
            if v in {"daily", "day", "每天", "每日"}:
                return RepeatType.DAILY
            if v in {"weekly", "week", "每周", "每星期", "每礼拜"}:
                return RepeatType.WEEKLY
            if v in {"monthly", "month", "每月"}:
                return RepeatType.MONTHLY
        return None

    def _parse_weekday(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            if 0 <= value <= 6:
                return value
            if 1 <= value <= 7:
                return value - 1
            return None
        if isinstance(value, str):
            v = value.strip().lower()
            if v.isdigit():
                return self._parse_weekday(int(v))
            return self._WEEKDAY_MAP.get(v) or self._WEEKDAY_MAP.get(value.strip())
        return None

    def _parse_monthday(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            day = int(str(value).strip())
        except (ValueError, TypeError):
            return None
        if 1 <= day <= 31:
            return day
        return None

    def _next_weekday(
        self, base: datetime, weekday: int, hour: int, minute: int
    ) -> datetime:
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (weekday - candidate.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)
        if candidate <= base:
            candidate = candidate + timedelta(days=7)
        return candidate

    def _normalize_result(
        self,
        now: datetime,
        remind_at: datetime,
        repeat_type: RepeatType,
        repeat_weekday: Optional[int],
        repeat_monthday: Optional[int],
    ) -> tuple[datetime, Optional[int], Optional[int]]:
        remind_at = remind_at.replace(second=0, microsecond=0)
        hour = remind_at.hour
        minute = remind_at.minute

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
        return remind_at, repeat_weekday, repeat_monthday

    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本"""
        if not text:
            return self._fallback_parse(text)

        if not self._is_configured():
            logger.info("AI parser not configured; falling back")
            return self._fallback_parse(text)

        content = self._call_api(text)
        if not content:
            return self._fallback_parse(text)

        data = self._extract_json(content)
        if not isinstance(data, dict):
            return self._fallback_parse(text)

        if data.get("ok") is False:
            return self._fallback_parse(text)

        raw_content = (
            data.get("content")
            or data.get("task")
            or data.get("reminder")
            or data.get("text")
            or text
        )
        content_match = re.search(r"提醒我?(.+)", str(raw_content))
        if content_match:
            content = content_match.group(1).strip()
        else:
            content = str(raw_content).strip()

        remind_at_value = (
            data.get("remind_at")
            or data.get("remindAt")
            or data.get("time")
            or data.get("datetime")
        )
        remind_at = self._parse_datetime(remind_at_value)
        if remind_at is None:
            return self._fallback_parse(text)

        repeat_type = (
            self._parse_repeat_type(
                data.get("repeat_type") or data.get("repeatType") or data.get("repeat")
            )
            or RepeatType.NONE
        )
        repeat_weekday = self._parse_weekday(
            data.get("repeat_weekday") or data.get("repeatWeekday")
        )
        repeat_monthday = self._parse_monthday(
            data.get("repeat_monthday") or data.get("repeatMonthday")
        )

        if repeat_type == RepeatType.WEEKLY and repeat_weekday is None:
            repeat_weekday = remind_at.weekday()
        if repeat_type == RepeatType.MONTHLY and repeat_monthday is None:
            repeat_monthday = remind_at.day
        if repeat_type == RepeatType.NONE:
            if repeat_weekday is not None:
                repeat_type = RepeatType.WEEKLY
            elif repeat_monthday is not None:
                repeat_type = RepeatType.MONTHLY

        now = self._get_now()
        remind_at, repeat_weekday, repeat_monthday = self._normalize_result(
            now, remind_at, repeat_type, repeat_weekday, repeat_monthday
        )

        return ParseResult(
            content=content,
            remind_at=remind_at,
            repeat_type=repeat_type,
            repeat_weekday=repeat_weekday,
            repeat_monthday=repeat_monthday,
        )


class SiliconFlowParser(LLMJSONParser):
    """SiliconFlow 解析器 (DeepSeek)"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timezone: Optional[str] = None,
        timeout_seconds: int = 15,
        fallback: Optional[AIParser] = None,
    ):
        self.api_key = api_key or settings.AI_API_KEY
        self.model = model or settings.AI_MODEL or "deepseek-ai/DeepSeek-V3.2"
        self.base_url = (
            base_url
            or settings.AI_BASE_URL
            or "https://api.siliconflow.cn/v1/chat/completions"
        )
        super().__init__(
            timezone=timezone, timeout_seconds=timeout_seconds, fallback=fallback
        )

    def _is_configured(self) -> bool:
        return bool(self.api_key)

    def _call_api(self, text: str) -> Optional[str]:
        if not self.api_key:
            return None

        now = self._get_now()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_prompt(now)},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "max_tokens": 200,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        request = urllib.request.Request(
            self.base_url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                data = resp.read().decode("utf-8")
                response_json = json.loads(data)
            return response_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("SiliconFlow 响应解析失败: %s", exc)
            return None
        except urllib.error.HTTPError as exc:
            logger.warning("SiliconFlow 请求失败: %s", exc)
            return None
        except Exception as exc:
            logger.warning("SiliconFlow 请求异常: %s", exc)
            return None


class OpenAIParser(LLMJSONParser):
    """OpenAI 解析器"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timezone: Optional[str] = None,
        timeout_seconds: int = 15,
        fallback: Optional[AIParser] = None,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self.base_url = (
            base_url
            or settings.OPENAI_BASE_URL
            or "https://api.openai.com/v1/chat/completions"
        )
        super().__init__(
            timezone=timezone, timeout_seconds=timeout_seconds, fallback=fallback
        )

    def _is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def _call_api(self, text: str) -> Optional[str]:
        if not self.api_key or not self.model:
            return None

        now = self._get_now()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_prompt(now)},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "max_tokens": 200,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        request = urllib.request.Request(
            self.base_url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                data = resp.read().decode("utf-8")
                response_json = json.loads(data)
            return response_json["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("OpenAI 响应解析失败: %s", exc)
            return None
        except urllib.error.HTTPError as exc:
            logger.warning("OpenAI 请求失败: %s", exc)
            return None
        except Exception as exc:
            logger.warning("OpenAI 请求异常: %s", exc)
            return None


class ClaudeParser(LLMJSONParser):
    """Claude 解析器"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timezone: Optional[str] = None,
        timeout_seconds: int = 15,
        fallback: Optional[AIParser] = None,
        anthropic_version: str = "2023-06-01",
    ):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_MODEL
        self.base_url = (
            base_url
            or settings.ANTHROPIC_BASE_URL
            or "https://api.anthropic.com/v1/messages"
        )
        self.anthropic_version = anthropic_version
        super().__init__(
            timezone=timezone, timeout_seconds=timeout_seconds, fallback=fallback
        )

    def _is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def _call_api(self, text: str) -> Optional[str]:
        if not self.api_key or not self.model:
            return None

        now = self._get_now()
        payload = {
            "model": self.model,
            "system": self._build_prompt(now),
            "messages": [{"role": "user", "content": text}],
            "temperature": 0.1,
            "max_tokens": 200,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        request = urllib.request.Request(
            self.base_url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as resp:
                data = resp.read().decode("utf-8")
                response_json = json.loads(data)
            content = response_json.get("content")
            if isinstance(content, list):
                parts = [
                    item.get("text", "") for item in content if isinstance(item, dict)
                ]
                return "".join(parts).strip() or None
            return response_json.get("completion")
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("Claude 响应解析失败: %s", exc)
            return None
        except urllib.error.HTTPError as exc:
            logger.warning("Claude 请求失败: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Claude 请求异常: %s", exc)
            return None


def get_default_parser() -> AIParser:
    """根据配置选择默认解析器"""
    provider = (settings.AI_PROVIDER or "").strip().lower()
    if provider in {"rule", "rules", "regex", "rulebased"}:
        return RuleBasedParser()
    if provider in {"siliconflow", "deepseek", "sf"}:
        return SiliconFlowParser()
    if provider in {"openai", "gpt"}:
        return OpenAIParser()
    if provider in {"claude", "anthropic"}:
        return ClaudeParser()

    if settings.AI_API_KEY:
        return SiliconFlowParser()
    if settings.OPENAI_API_KEY:
        return OpenAIParser()
    if settings.ANTHROPIC_API_KEY:
        return ClaudeParser()
    return RuleBasedParser()
