"""Event data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EventType(str, Enum):
    """事件类型"""
    NARRATIVE = "narrative"      # 叙事事件
    CRITICAL = "critical"        # 关键事件
    CRIME = "crime"              # 犯罪事件
    HIDDEN = "hidden"            # 隐藏事件（不显示文字）
    PLAYER_ACTION = "player_action"
    NPC_ACTION = "npc_action"
    SYSTEM = "system"


@dataclass
class TimelineEvent:
    """时间线事件（预定义的世界事件）"""
    id: str
    trigger_day: int
    trigger_time: str
    type: EventType
    text: Optional[str]          # 显示的文字
    
    # 触发条件
    condition: Dict[str, Any] = field(default_factory=dict)
    
    # 效果
    effects: List[Dict[str, Any]] = field(default_factory=list)
    
    # 犯罪事件专用
    actor: Optional[str] = None
    victim: Optional[str] = None
    
    # 是否已触发
    triggered: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineEvent:
        """从字典创建 TimelineEvent"""
        trigger = data.get("trigger", {})
        
        return cls(
            id=data.get("id", ""),
            trigger_day=trigger.get("day", 1),
            trigger_time=trigger.get("time", "morning"),
            type=EventType(data.get("type", "narrative")),
            text=data.get("text"),
            condition=data.get("condition", {}),
            effects=data.get("effects", []),
            actor=data.get("actor"),
            victim=data.get("victim"),
            triggered=False,
        )


@dataclass
class GameEvent:
    """游戏运行时事件"""
    event_type: EventType
    text: str
    day: int
    time: str
    actor: Optional[str] = None
    location: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type.value,
            "text": self.text,
            "day": self.day,
            "time": self.time,
            "actor": self.actor,
            "location": self.location,
            "metadata": self.metadata,
        }

