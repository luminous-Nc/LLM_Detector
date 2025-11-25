"""Conversation data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class Message:
    """对话消息"""
    speaker: str                     # 发言者 ID（player 或 actor_id）
    content: str                     # 消息内容
    day: int                         # 游戏内天数
    time: str                        # 游戏内时间段
    attached_clue: Optional[str] = None   # 出示的证据 ID
    quoted_message_idx: Optional[int] = None  # 引用的消息索引

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "speaker": self.speaker,
            "content": self.content,
            "day": self.day,
            "time": self.time,
            "attached_clue": self.attached_clue,
            "quoted_message_idx": self.quoted_message_idx,
        }


@dataclass
class Conversation:
    """对话记录"""
    id: str
    participants: List[str]          # 参与者（2人）
    messages: List[Message] = field(default_factory=list)
    location: str = ""
    started_day: int = 1
    started_time: str = "morning"
    ended: bool = False

    @classmethod
    def create(cls, participant1: str, participant2: str, 
               location: str, day: int, time: str) -> Conversation:
        """创建新对话"""
        return cls(
            id=str(uuid.uuid4())[:8],
            participants=[participant1, participant2],
            location=location,
            started_day=day,
            started_time=time,
        )

    def add_message(self, speaker: str, content: str, day: int, time: str,
                    attached_clue: Optional[str] = None,
                    quoted_message_idx: Optional[int] = None) -> Message:
        """添加消息"""
        msg = Message(
            speaker=speaker,
            content=content,
            day=day,
            time=time,
            attached_clue=attached_clue,
            quoted_message_idx=quoted_message_idx,
        )
        self.messages.append(msg)
        return msg

    def get_other_participant(self, current: str) -> Optional[str]:
        """获取对话的另一方"""
        for p in self.participants:
            if p != current:
                return p
        return None

    def get_message_by_idx(self, idx: int) -> Optional[Message]:
        """通过索引获取消息"""
        if 0 <= idx < len(self.messages):
            return self.messages[idx]
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "participants": self.participants,
            "messages": [m.to_dict() for m in self.messages],
            "location": self.location,
            "started_day": self.started_day,
            "started_time": self.started_time,
            "ended": self.ended,
        }

    def format_history(self, max_messages: int = 20) -> str:
        """格式化对话历史（用于 LLM prompt）"""
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        lines = []
        for i, msg in enumerate(recent):
            prefix = f"[{msg.speaker}]"
            if msg.attached_clue:
                prefix += f" (出示证据: {msg.attached_clue})"
            if msg.quoted_message_idx is not None:
                quoted = self.get_message_by_idx(msg.quoted_message_idx)
                if quoted:
                    prefix += f" (引用: \"{quoted.content[:30]}...\")"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

