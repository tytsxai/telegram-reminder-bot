"""提醒数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from src.utils.time_utils import now_in_timezone


class RepeatType(str, Enum):
    """重复类型"""

    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class Reminder:
    """提醒模型"""

    user_id: int
    chat_id: int
    content: str
    remind_at: datetime
    repeat_type: RepeatType = RepeatType.NONE
    repeat_weekday: Optional[int] = None
    repeat_monthday: Optional[int] = None
    is_active: bool = True
    id: Optional[int] = None
    created_at: datetime = field(default_factory=now_in_timezone)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "content": self.content,
            "remind_at": self.remind_at.isoformat(),
            "repeat_type": self.repeat_type.value,
            "repeat_weekday": self.repeat_weekday,
            "repeat_monthday": self.repeat_monthday,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Reminder":
        """从字典创建"""
        return cls(
            id=data.get("id"),
            user_id=data["user_id"],
            chat_id=data["chat_id"],
            content=data["content"],
            remind_at=datetime.fromisoformat(data["remind_at"]),
            repeat_type=RepeatType(data.get("repeat_type", "none")),
            repeat_weekday=data.get("repeat_weekday"),
            repeat_monthday=data.get("repeat_monthday"),
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
