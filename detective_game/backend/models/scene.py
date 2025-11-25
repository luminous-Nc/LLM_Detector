"""Scene data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class AccessibilityRule:
    """场景可达性规则"""
    condition: Dict[str, Any]    # 条件
    accessible: bool             # 是否可访问
    message: str = ""            # 提示信息


@dataclass
class InvestigationPoint:
    """调查点"""
    id: str
    name: str
    description: str
    clue_id: Optional[str] = None
    discovered: bool = False
    requires: Optional[str] = None  # 前置条件（线索ID或事件ID）


@dataclass
class SceneConfig:
    """场景配置（从 YAML 加载）"""
    id: str
    name: str
    description: str
    
    # 可达性
    default_accessible: bool = True
    accessibility_rules: List[AccessibilityRule] = field(default_factory=list)
    
    # 连接的场景
    connections: List[str] = field(default_factory=list)
    
    # 调查点
    investigation_points: List[InvestigationPoint] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SceneConfig:
        """从字典创建 SceneConfig"""
        accessibility = data.get("accessibility", {})
        
        # 解析可达性规则
        rules = []
        for rule_data in accessibility.get("rules", []):
            rules.append(AccessibilityRule(
                condition=rule_data.get("condition", {}),
                accessible=rule_data.get("accessible", True),
                message=rule_data.get("message", ""),
            ))
        
        # 解析调查点
        points = []
        for point_data in data.get("investigation_points", []):
            points.append(InvestigationPoint(
                id=point_data.get("id", ""),
                name=point_data.get("name", ""),
                description=point_data.get("description", ""),
                clue_id=point_data.get("clue_id"),
                discovered=point_data.get("discovered", False),
                requires=point_data.get("requires"),
            ))
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            default_accessible=accessibility.get("default", True),
            accessibility_rules=rules,
            connections=data.get("connections", []),
            investigation_points=points,
        )


@dataclass
class SceneState:
    """场景运行时状态"""
    id: str
    is_accessible: bool = True
    inaccessible_reason: str = ""
    
    # 当前在场的角色
    occupants: Set[str] = field(default_factory=set)
    
    # 已发现的调查点
    discovered_points: Set[str] = field(default_factory=set)
    
    # 临时状态标记
    flags: Dict[str, Any] = field(default_factory=dict)

    def add_occupant(self, actor_id: str) -> None:
        """添加角色到场景"""
        self.occupants.add(actor_id)

    def remove_occupant(self, actor_id: str) -> None:
        """从场景移除角色"""
        self.occupants.discard(actor_id)

    def mark_point_discovered(self, point_id: str) -> None:
        """标记调查点为已发现"""
        self.discovered_points.add(point_id)

    def is_point_discovered(self, point_id: str) -> bool:
        """检查调查点是否已发现"""
        return point_id in self.discovered_points

