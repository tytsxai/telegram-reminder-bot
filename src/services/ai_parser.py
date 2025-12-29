"""AI解析接口模块"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from src.models.reminder import RepeatType


@dataclass
class ParseResult:
    """解析结果"""
    content: str
    remind_at: datetime
    repeat_type: RepeatType = RepeatType.NONE


class AIParser(ABC):
    """AI解析器抽象基类"""
    
    @abstractmethod
    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本"""
        pass


class RuleBasedParser(AIParser):
    """基于规则的解析器"""
    
    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本"""
        now = datetime.now()
        remind_at = None
        repeat_type = RepeatType.NONE
        content = text
        
        # 解析重复类型
        if "每天" in text or "每日" in text:
            repeat_type = RepeatType.DAILY
        elif "每周" in text:
            repeat_type = RepeatType.WEEKLY
        elif "每月" in text:
            repeat_type = RepeatType.MONTHLY
        
        # 解析日期
        if "今天" in text:
            remind_at = now
        elif "明天" in text:
            remind_at = now + timedelta(days=1)
        elif "后天" in text:
            remind_at = now + timedelta(days=2)
        
        # 解析时间
        time_match = re.search(r'(\d{1,2})[点时](\d{1,2})?[分]?', text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            if "下午" in text or "晚上" in text:
                if hour < 12:
                    hour += 12
            if remind_at is None:
                remind_at = now
            remind_at = remind_at.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        
        # 提取提醒内容
        content_match = re.search(r'提醒我?(.+)', text)
        if content_match:
            content = content_match.group(1).strip()
        
        if remind_at is None:
            return None
        
        return ParseResult(
            content=content,
            remind_at=remind_at,
            repeat_type=repeat_type
        )


class OpenAIParser(AIParser):
    """OpenAI 解析器 (预留接口)"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
    
    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本 - 预留实现"""
        raise NotImplementedError(
            "OpenAI parser not implemented. "
            "Please implement with OpenAI API."
        )


class ClaudeParser(AIParser):
    """Claude 解析器 (预留接口)"""
    
    def __init__(self, api_key: str, model: str = "claude-3"):
        self.api_key = api_key
        self.model = model
    
    def parse(self, text: str) -> Optional[ParseResult]:
        """解析自然语言文本 - 预留实现"""
        raise NotImplementedError(
            "Claude parser not implemented. "
            "Please implement with Anthropic API."
        )
