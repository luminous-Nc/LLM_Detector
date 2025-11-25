"""Time system for managing game time progression."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import GameState, GameTime


class TimeSystem:
    """时间系统 - 管理游戏时间的推进"""

    def __init__(self, max_days: int = 3):
        self.max_days = max_days

    def advance_time(self, game_state: GameState) -> bool:
        """
        推进时间到下一个时间段
        
        Returns:
            bool: 是否进入了新的一天
        """
        is_new_day = game_state.time.advance()
        return is_new_day

    def is_game_over(self, game_state: GameState) -> bool:
        """检查游戏是否结束（超过最大天数）"""
        return game_state.time.day > self.max_days

    def get_current_time(self, game_state: GameState) -> GameTime:
        """获取当前时间"""
        return game_state.time

    def get_time_display(self, game_state: GameState) -> str:
        """获取时间显示字符串"""
        return str(game_state.time)

