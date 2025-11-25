"""Clue data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ClueType(str, Enum):
    """线索类型"""
    PHYSICAL = "physical"        # 物证
    DOCUMENT = "document"        # 文档
    TESTIMONIAL = "testimonial"  # 证词
    ITEM = "item"                # 物品（可使用）


@dataclass
class ClueConfig:
    """线索配置（从 YAML 加载）"""
    id: str
    name: str
    type: ClueType
    category: str                # 细分类别
    description: str
    
    # 发现条件
    discovery_location: Optional[str] = None
    discovery_point: Optional[str] = None
    requires_event: Optional[str] = None
    requires_item: Optional[str] = None
    
    # 关联
    related_to: List[str] = field(default_factory=list)
    points_to: List[str] = field(default_factory=list)  # 指向的嫌疑人
    unlocks: Optional[str] = None  # 解锁其他东西
    
    # 是否关键证据
    is_key_evidence: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClueConfig:
        """从字典创建 ClueConfig"""
        discovery = data.get("discovery", {})
        connections = data.get("connections", [])
        
        related_to = []
        points_to = []
        unlocks = None
        
        for conn in connections:
            if "related_to" in conn:
                related_to.append(conn["related_to"])
            if "points_to" in conn:
                pts = conn["points_to"]
                if isinstance(pts, list):
                    points_to.extend(pts)
                else:
                    points_to.append(pts)
            if "unlocks" in conn:
                unlocks = conn["unlocks"]
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=ClueType(data.get("type", "physical")),
            category=data.get("category", ""),
            description=data.get("description", ""),
            discovery_location=discovery.get("location"),
            discovery_point=discovery.get("point"),
            requires_event=discovery.get("requires_event"),
            requires_item=discovery.get("requires_item"),
            related_to=related_to,
            points_to=points_to,
            unlocks=unlocks,
            is_key_evidence=data.get("is_key_evidence", False),
        )


@dataclass
class ClueState:
    """线索运行时状态"""
    id: str
    is_discoverable: bool = False  # 是否可被发现
    discovered_by: Optional[str] = None  # 发现者（player 或 actor_id）
    discovered_at_day: Optional[int] = None
    discovered_at_time: Optional[str] = None

