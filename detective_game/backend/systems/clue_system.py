"""Clue system for managing evidence and discoveries."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..models.clue import ClueConfig, ClueState, ClueType

if TYPE_CHECKING:
    from ..models import GameState


class ClueSystem:
    """线索系统 - 管理证据的发现和收集"""

    def __init__(self, clue_configs: Dict[str, Dict[str, Any]]):
        """
        初始化线索系统
        
        Args:
            clue_configs: 从 YAML 加载的线索配置
        """
        self.configs: Dict[str, ClueConfig] = {}
        self.states: Dict[str, ClueState] = {}

        for clue_id, clue_data in clue_configs.items():
            config = ClueConfig.from_dict(clue_data)
            self.configs[clue_id] = config
            self.states[clue_id] = ClueState(id=clue_id)

    def get_clue_config(self, clue_id: str) -> Optional[ClueConfig]:
        """获取线索配置"""
        return self.configs.get(clue_id)

    def get_clue_state(self, clue_id: str) -> Optional[ClueState]:
        """获取线索状态"""
        return self.states.get(clue_id)

    def is_clue_discoverable(self, clue_id: str, game_state: GameState) -> bool:
        """检查线索是否可被发现"""
        config = self.configs.get(clue_id)
        if not config:
            return False

        # 检查事件条件
        if config.requires_event:
            if not game_state.has_flag(config.requires_event):
                # 也检查是否通过 clue_available flag 可用
                if not game_state.has_flag(f"clue_available_{clue_id}"):
                    return False

        # 检查物品条件
        if config.requires_item:
            if not game_state.player.has_item(config.requires_item):
                if not game_state.has_flag(config.requires_item):
                    return False

        return True

    def discover_clue(
        self, 
        clue_id: str, 
        discoverer: str,  # "player" or actor_id
        game_state: GameState
    ) -> Optional[Dict[str, Any]]:
        """
        发现线索
        
        Returns:
            线索信息字典，如果无法发现则返回 None
        """
        config = self.configs.get(clue_id)
        state = self.states.get(clue_id)
        
        if not config or not state:
            return None

        # 检查是否已被发现
        if state.discovered_by:
            return None

        # 检查是否可发现
        if not self.is_clue_discoverable(clue_id, game_state):
            return None

        # 标记为已发现
        state.is_discoverable = True
        state.discovered_by = discoverer
        state.discovered_at_day = game_state.time.day
        state.discovered_at_time = game_state.time.period.value

        # 如果是玩家发现，添加到玩家的线索列表
        if discoverer == "player":
            game_state.player.add_clue(clue_id)
            
            # 如果线索是物品类型，也添加到物品栏
            if config.type == ClueType.ITEM:
                game_state.player.add_item(clue_id)
            
            # 如果线索解锁其他东西，设置 flag
            if config.unlocks:
                game_state.set_flag(f"has_{config.unlocks}", True)

        return self.get_clue_info(clue_id)

    def get_clue_info(self, clue_id: str) -> Optional[Dict[str, Any]]:
        """获取线索信息"""
        config = self.configs.get(clue_id)
        state = self.states.get(clue_id)
        
        if not config:
            return None

        return {
            "id": clue_id,
            "name": config.name,
            "type": config.type.value,
            "category": config.category,
            "description": config.description.strip(),
            "is_key_evidence": config.is_key_evidence,
            "discovered_by": state.discovered_by if state else None,
            "points_to": config.points_to,
        }

    def get_player_clues(self, game_state: GameState) -> List[Dict[str, Any]]:
        """获取玩家已收集的所有线索"""
        clues = []
        for clue_id in game_state.player.clues:
            info = self.get_clue_info(clue_id)
            if info:
                clues.append(info)
        return clues

    def get_clues_by_type(
        self, 
        clue_type: ClueType, 
        game_state: GameState
    ) -> List[Dict[str, Any]]:
        """按类型获取玩家的线索"""
        clues = []
        for clue_id in game_state.player.clues:
            config = self.configs.get(clue_id)
            if config and config.type == clue_type:
                info = self.get_clue_info(clue_id)
                if info:
                    clues.append(info)
        return clues

    def get_key_evidence(self, game_state: GameState) -> List[Dict[str, Any]]:
        """获取关键证据"""
        evidence = []
        for clue_id in game_state.player.clues:
            config = self.configs.get(clue_id)
            if config and config.is_key_evidence:
                info = self.get_clue_info(clue_id)
                if info:
                    evidence.append(info)
        return evidence

    def get_clues_pointing_to(
        self, 
        suspect_id: str, 
        game_state: GameState
    ) -> List[Dict[str, Any]]:
        """获取指向特定嫌疑人的线索"""
        clues = []
        for clue_id in game_state.player.clues:
            config = self.configs.get(clue_id)
            if config and suspect_id in config.points_to:
                info = self.get_clue_info(clue_id)
                if info:
                    clues.append(info)
        return clues

    def get_all_discoverable_clues(
        self, 
        game_state: GameState
    ) -> List[str]:
        """获取当前可发现的所有线索 ID（调试用）"""
        discoverable = []
        for clue_id in self.configs:
            if self.is_clue_discoverable(clue_id, game_state):
                state = self.states.get(clue_id)
                if state and not state.discovered_by:
                    discoverable.append(clue_id)
        return discoverable

