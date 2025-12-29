"""提醒数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


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
    is_active: bool = True
    id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "content": self.content,
            "remind_at": self.remind_at.isoformat(),
            "repeat_type": self.repeat_type.value,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat()
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
            is_active=data.get("is_active", True),
            created_at=datetime.fromisoformat(data["created_at"])
        )
