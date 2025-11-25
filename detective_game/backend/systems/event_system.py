"""Event system for managing timeline events."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..models.event import TimelineEvent, GameEvent, EventType

if TYPE_CHECKING:
    from ..models import GameState, GameTime


class EventSystem:
    """事件系统 - 管理时间线事件的触发"""

    def __init__(self, timeline_events: List[Dict[str, Any]]):
        """
        初始化事件系统
        
        Args:
            timeline_events: 从 YAML 加载的事件列表
        """
        self.events: List[TimelineEvent] = []
        for event_data in timeline_events:
            self.events.append(TimelineEvent.from_dict(event_data))

    def check_and_trigger_events(
        self, 
        game_state: GameState,
        actor_states: Optional[Dict[str, Any]] = None,
    ) -> List[GameEvent]:
        """
        检查并触发当前时间点的事件
        
        Returns:
            触发的事件列表
        """
        triggered: List[GameEvent] = []
        current_time = game_state.time

        for event in self.events:
            # 跳过已触发的事件
            if event.triggered or game_state.is_event_triggered(event.id):
                continue

            # 检查时间是否匹配
            if not current_time.matches(event.trigger_day, event.trigger_time):
                continue

            # 检查条件是否满足
            if not self._check_condition(event.condition, game_state):
                continue

            # 触发事件
            event.triggered = True
            game_state.mark_event_triggered(event.id)

            # 应用效果
            self._apply_effects(event.effects, game_state, actor_states)

            # 创建游戏事件
            if event.text:  # 隐藏事件不生成显示事件
                game_event = GameEvent(
                    event_type=event.type,
                    text=event.text.strip(),
                    day=current_time.day,
                    time=current_time.period.value,
                    actor=event.actor,
                    metadata={
                        "event_id": event.id,
                        "victim": event.victim,
                    },
                )
                triggered.append(game_event)

        return triggered

    def _check_condition(
        self, 
        condition: Dict[str, Any], 
        game_state: GameState
    ) -> bool:
        """检查事件条件是否满足"""
        if not condition:
            return True

        # 检查 flag 条件
        if "flag" in condition:
            flag_name = condition["flag"]
            if not game_state.has_flag(flag_name):
                return False

        # 检查 after_event 条件
        if "after_event" in condition:
            event_id = condition["after_event"]
            if not game_state.is_event_triggered(event_id):
                return False

        # 检查 before_event 条件
        if "before_event" in condition:
            event_id = condition["before_event"]
            if game_state.is_event_triggered(event_id):
                return False

        return True

    def _apply_effects(
        self,
        effects: List[Dict[str, Any]],
        game_state: GameState,
        actor_states: Optional[Dict[str, Any]] = None,
    ) -> None:
        """应用事件效果"""
        for effect in effects:
            # 设置 flag
            if "set_flag" in effect:
                flag_dict = effect["set_flag"]
                for key, value in flag_dict.items():
                    game_state.set_flag(key, value)

            # 更新角色状态
            if "actor_status" in effect and actor_states:
                status_dict = effect["actor_status"]
                for actor_id, status in status_dict.items():
                    if actor_id in actor_states:
                        if status == "dead":
                            actor_states[actor_id].is_alive = False

            # 场景解锁（需要由 SceneSystem 处理）
            # scene_unlock, scene_lock 会在 SceneSystem 中读取 flags

            # 线索可用（需要由 ClueSystem 处理）
            if "clue_available" in effect:
                clues = effect["clue_available"]
                for clue_id in clues:
                    game_state.set_flag(f"clue_available_{clue_id}", True)

    def get_upcoming_events(
        self, 
        game_state: GameState, 
        look_ahead: int = 2
    ) -> List[TimelineEvent]:
        """获取即将发生的事件（用于调试）"""
        upcoming = []
        current_day = game_state.time.day
        
        for event in self.events:
            if event.triggered:
                continue
            if event.trigger_day <= current_day + look_ahead:
                upcoming.append(event)
        
        return upcoming

