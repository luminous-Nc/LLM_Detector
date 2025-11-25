"""Scene system for managing locations and accessibility."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..models.scene import SceneConfig, SceneState, InvestigationPoint

if TYPE_CHECKING:
    from ..models import GameState, GameTime


class SceneSystem:
    """场景系统 - 管理地点和可达性"""

    def __init__(self, scene_configs: Dict[str, Dict[str, Any]]):
        """
        初始化场景系统
        
        Args:
            scene_configs: 从 YAML 加载的场景配置
        """
        self.configs: Dict[str, SceneConfig] = {}
        self.states: Dict[str, SceneState] = {}

        for scene_id, scene_data in scene_configs.items():
            config = SceneConfig.from_dict(scene_data)
            self.configs[scene_id] = config
            self.states[scene_id] = SceneState(
                id=scene_id,
                is_accessible=config.default_accessible,
            )

    def get_scene_config(self, scene_id: str) -> Optional[SceneConfig]:
        """获取场景配置"""
        return self.configs.get(scene_id)

    def get_scene_state(self, scene_id: str) -> Optional[SceneState]:
        """获取场景状态"""
        return self.states.get(scene_id)

    def check_accessibility(
        self, 
        scene_id: str, 
        game_state: GameState
    ) -> Tuple[bool, str]:
        """
        检查场景是否可访问
        
        Returns:
            (可访问, 原因/消息)
        """
        config = self.configs.get(scene_id)
        if not config:
            return False, "未知的地点"

        state = self.states.get(scene_id)
        if not state:
            return False, "地点状态错误"

        # 检查可达性规则
        for rule in config.accessibility_rules:
            if self._match_rule_condition(rule.condition, game_state):
                return rule.accessible, rule.message

        return config.default_accessible, ""

    def _match_rule_condition(
        self, 
        condition: Dict[str, Any], 
        game_state: GameState
    ) -> bool:
        """检查规则条件是否匹配"""
        # 时间条件
        if "time" in condition:
            if game_state.time.period.value != condition["time"]:
                return False

        # 事件后条件
        if "after_event" in condition:
            if not game_state.is_event_triggered(condition["after_event"]):
                return False

        # 事件前条件
        if "before_event" in condition:
            if game_state.is_event_triggered(condition["before_event"]):
                return False

        # 物品条件
        if "has_item" in condition:
            if not game_state.player.has_item(condition["has_item"]):
                return False

        # flag 条件
        if "flag" in condition:
            if not game_state.has_flag(condition["flag"]):
                return False

        return True

    def get_accessible_scenes(self, game_state: GameState) -> List[str]:
        """获取所有可访问的场景"""
        accessible = []
        for scene_id in self.configs:
            is_accessible, _ = self.check_accessibility(scene_id, game_state)
            if is_accessible:
                accessible.append(scene_id)
        return accessible

    def get_connected_scenes(
        self, 
        scene_id: str, 
        game_state: GameState
    ) -> List[Dict[str, Any]]:
        """获取从当前场景可以前往的场景列表"""
        config = self.configs.get(scene_id)
        if not config:
            return []

        result = []
        for connected_id in config.connections:
            connected_config = self.configs.get(connected_id)
            if not connected_config:
                continue
            
            is_accessible, message = self.check_accessibility(connected_id, game_state)
            result.append({
                "id": connected_id,
                "name": connected_config.name,
                "accessible": is_accessible,
                "message": message,
            })

        return result

    def get_investigation_points(
        self, 
        scene_id: str, 
        game_state: GameState
    ) -> List[Dict[str, Any]]:
        """获取场景中的调查点"""
        config = self.configs.get(scene_id)
        state = self.states.get(scene_id)
        if not config or not state:
            return []

        result = []
        for point in config.investigation_points:
            # 检查是否已发现
            is_discovered = state.is_point_discovered(point.id)
            
            # 检查前置条件
            can_investigate = True
            requires_message = ""
            
            if point.requires:
                # 检查是否有所需的线索或物品
                has_requirement = (
                    game_state.player.has_clue(point.requires) or
                    game_state.player.has_item(point.requires) or
                    game_state.has_flag(point.requires)
                )
                if not has_requirement:
                    can_investigate = False
                    requires_message = f"需要: {point.requires}"

            result.append({
                "id": point.id,
                "name": point.name,
                "description": point.description,
                "discovered": is_discovered,
                "can_investigate": can_investigate and not is_discovered,
                "requires_message": requires_message,
                "has_clue": point.clue_id is not None and not is_discovered,
            })

        return result

    def investigate_point(
        self, 
        scene_id: str, 
        point_id: str, 
        game_state: GameState
    ) -> Optional[str]:
        """
        调查一个调查点
        
        Returns:
            发现的线索 ID，如果没有则返回 None
        """
        config = self.configs.get(scene_id)
        state = self.states.get(scene_id)
        if not config or not state:
            return None

        # 查找调查点
        point = None
        for p in config.investigation_points:
            if p.id == point_id:
                point = p
                break

        if not point:
            return None

        # 检查是否已发现
        if state.is_point_discovered(point_id):
            return None

        # 检查前置条件
        if point.requires:
            has_requirement = (
                game_state.player.has_clue(point.requires) or
                game_state.player.has_item(point.requires) or
                game_state.has_flag(point.requires)
            )
            if not has_requirement:
                return None

        # 标记为已发现
        state.mark_point_discovered(point_id)

        return point.clue_id

    def move_actor_to_scene(self, actor_id: str, from_scene: str, to_scene: str) -> None:
        """移动角色到新场景"""
        if from_scene in self.states:
            self.states[from_scene].remove_occupant(actor_id)
        if to_scene in self.states:
            self.states[to_scene].add_occupant(actor_id)

    def get_scene_occupants(self, scene_id: str) -> List[str]:
        """获取场景中的所有角色"""
        state = self.states.get(scene_id)
        if state:
            return list(state.occupants)
        return []

    def get_scene_description(self, scene_id: str) -> str:
        """获取场景描述"""
        config = self.configs.get(scene_id)
        if config:
            return config.description.strip()
        return ""

    def get_all_scenes_info(self, game_state: GameState) -> List[Dict[str, Any]]:
        """获取所有场景信息"""
        result = []
        for scene_id, config in self.configs.items():
            is_accessible, message = self.check_accessibility(scene_id, game_state)
            state = self.states.get(scene_id)
            
            result.append({
                "id": scene_id,
                "name": config.name,
                "description": config.description.strip(),
                "accessible": is_accessible,
                "message": message,
                "occupants": list(state.occupants) if state else [],
            })
        
        return result

