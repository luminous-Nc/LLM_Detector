"""Game state data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class TimePeriod(str, Enum):
    """时间段"""
    DAWN = "dawn"           # 黎明
    MORNING = "morning"     # 早上
    NOON = "noon"           # 中午
    AFTERNOON = "afternoon" # 下午
    EVENING = "evening"     # 傍晚
    NIGHT = "night"         # 深夜

    @classmethod
    def order(cls) -> List[TimePeriod]:
        """返回时间段顺序"""
        return [
            cls.DAWN, cls.MORNING, cls.NOON,
            cls.AFTERNOON, cls.EVENING, cls.NIGHT
        ]

    def next(self) -> tuple[TimePeriod, bool]:
        """
        返回下一个时间段和是否进入新的一天
        Returns: (next_period, is_new_day)
        """
        order = self.order()
        idx = order.index(self)
        if idx == len(order) - 1:
            return order[0], True  # 回到黎明，新的一天
        return order[idx + 1], False

    def to_chinese(self) -> str:
        """转换为中文"""
        mapping = {
            TimePeriod.DAWN: "黎明",
            TimePeriod.MORNING: "早上",
            TimePeriod.NOON: "中午",
            TimePeriod.AFTERNOON: "下午",
            TimePeriod.EVENING: "傍晚",
            TimePeriod.NIGHT: "深夜",
        }
        return mapping.get(self, str(self.value))


@dataclass
class GameTime:
    """游戏时间"""
    day: int = 1
    period: TimePeriod = TimePeriod.MORNING

    def advance(self) -> bool:
        """
        推进到下一个时间段
        Returns: 是否进入了新的一天
        """
        next_period, is_new_day = self.period.next()
        self.period = next_period
        if is_new_day:
            self.day += 1
        return is_new_day

    def __str__(self) -> str:
        return f"第{self.day}天 {self.period.to_chinese()}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "period": self.period.value,
            "display": str(self),
        }

    def matches(self, day: int, time: str) -> bool:
        """检查是否匹配指定的时间"""
        return self.day == day and self.period.value == time


@dataclass
class PlayerState:
    """玩家状态"""
    name: str = "玩家"
    location: str = "entrance_hall"
    
    # 收集的线索
    clues: Set[str] = field(default_factory=set)
    
    # 对话历史 ID 列表
    conversation_ids: List[str] = field(default_factory=list)
    
    # 物品栏
    inventory: Set[str] = field(default_factory=set)

    def add_clue(self, clue_id: str) -> None:
        """添加线索"""
        self.clues.add(clue_id)

    def has_clue(self, clue_id: str) -> bool:
        """检查是否拥有线索"""
        return clue_id in self.clues

    def add_item(self, item_id: str) -> None:
        """添加物品"""
        self.inventory.add(item_id)

    def has_item(self, item_id: str) -> bool:
        """检查是否拥有物品"""
        return item_id in self.inventory


@dataclass
class GameState:
    """游戏总状态"""
    # 时间
    time: GameTime = field(default_factory=GameTime)
    
    # 玩家
    player: PlayerState = field(default_factory=PlayerState)
    
    # 全局标记（用于事件触发等）
    flags: Dict[str, Any] = field(default_factory=dict)
    
    # 已触发的事件
    triggered_events: Set[str] = field(default_factory=set)
    
    # 事件日志
    event_log: List[Dict[str, Any]] = field(default_factory=list)

    def set_flag(self, key: str, value: Any = True) -> None:
        """设置标记"""
        self.flags[key] = value

    def get_flag(self, key: str, default: Any = None) -> Any:
        """获取标记"""
        return self.flags.get(key, default)

    def has_flag(self, key: str) -> bool:
        """检查标记是否存在且为真"""
        return bool(self.flags.get(key))

    def mark_event_triggered(self, event_id: str) -> None:
        """标记事件为已触发"""
        self.triggered_events.add(event_id)

    def is_event_triggered(self, event_id: str) -> bool:
        """检查事件是否已触发"""
        return event_id in self.triggered_events

    def add_event_to_log(self, event: Dict[str, Any]) -> None:
        """添加事件到日志"""
        self.event_log.append(event)

