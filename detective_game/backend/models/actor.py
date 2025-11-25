"""Actor (NPC) data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ActorRole(str, Enum):
    """角色类型"""
    DETECTIVE = "detective"      # 侦探
    SUSPECT = "suspect"          # 嫌疑人
    WITNESS = "witness"          # 目击者
    VICTIM = "victim"            # 受害者
    MURDERER = "murderer"        # 凶手


@dataclass
class Relationship:
    """人物关系"""
    target_id: str
    type: str                    # friend, enemy, lover, acquaintance, etc.
    trust: float = 0.5           # 0.0 - 1.0
    note: str = ""


@dataclass
class ActionPlanItem:
    """凶手的行动计划项"""
    trigger_day: int
    trigger_time: str
    action: str                  # kill, sabotage, etc.
    target: Optional[str] = None
    location: Optional[str] = None
    method: Optional[str] = None
    condition: Optional[str] = None
    clue_left: Optional[str] = None


@dataclass
class ActorConfig:
    """角色配置（从 YAML 加载）"""
    id: str
    name: str
    role: ActorRole
    
    # 公开信息
    occupation: str = ""
    description: str = ""
    
    # 私密信息
    secret: str = ""
    guilt: Optional[str] = None
    goal: str = ""
    
    # 性格
    traits: List[str] = field(default_factory=list)
    speaking_style: str = ""
    backstory: str = ""
    
    # 关系
    relationships: Dict[str, Relationship] = field(default_factory=dict)
    
    # 日程
    schedule: Dict[str, str] = field(default_factory=dict)
    
    # 特殊行动计划（凶手使用）
    action_plan: List[ActionPlanItem] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ActorConfig:
        """从字典创建 ActorConfig"""
        public = data.get("public", {})
        private = data.get("private", {})
        personality = data.get("personality", {})
        
        # 解析关系
        relationships = {}
        for target_id, rel_data in data.get("relationships", {}).items():
            relationships[target_id] = Relationship(
                target_id=target_id,
                type=rel_data.get("type", "acquaintance"),
                trust=rel_data.get("trust", 0.5),
                note=rel_data.get("note", ""),
            )
        
        # 解析行动计划
        action_plan = []
        for plan_data in data.get("action_plan", []) or []:
            trigger = plan_data.get("trigger", {})
            action_plan.append(ActionPlanItem(
                trigger_day=trigger.get("day", 1),
                trigger_time=trigger.get("time", "night"),
                action=plan_data.get("action", ""),
                target=plan_data.get("target"),
                location=plan_data.get("location"),
                method=plan_data.get("method"),
                condition=plan_data.get("condition"),
                clue_left=plan_data.get("clue_left"),
            ))
        
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            role=ActorRole(data.get("role", "suspect")),
            occupation=public.get("occupation", ""),
            description=public.get("description", ""),
            secret=private.get("secret", ""),
            guilt=private.get("guilt"),
            goal=private.get("goal", ""),
            traits=personality.get("traits", []),
            speaking_style=personality.get("speaking_style", ""),
            backstory=data.get("backstory", ""),
            relationships=relationships,
            schedule=data.get("schedule", {}),
            action_plan=action_plan,
        )


@dataclass
class MemoryEntry:
    """记忆条目"""
    day: int
    time: str
    content: str
    location: str
    actors_involved: List[str] = field(default_factory=list)


@dataclass
class ActorState:
    """角色运行时状态"""
    id: str
    location: str
    is_alive: bool = True
    
    # 知道的线索
    known_clues: Set[str] = field(default_factory=set)
    
    # 对其他人的印象（LLM 生成）
    impressions: Dict[str, str] = field(default_factory=dict)
    
    # 记忆
    memory: List[MemoryEntry] = field(default_factory=list)
    
    # 当前正在进行的对话
    current_conversation: Optional[str] = None
    
    # 临时数据
    scratch: Dict[str, Any] = field(default_factory=dict)

    def add_memory(self, day: int, time: str, content: str, 
                   location: str, actors: List[str] = None) -> None:
        """添加一条记忆"""
        self.memory.append(MemoryEntry(
            day=day,
            time=time,
            content=content,
            location=location,
            actors_involved=actors or [],
        ))
        # 保留最近50条记忆
        if len(self.memory) > 50:
            self.memory = self.memory[-50:]

    def get_recent_memory(self, count: int = 10) -> List[MemoryEntry]:
        """获取最近的记忆"""
        return self.memory[-count:]

    def update_impression(self, actor_id: str, impression: str) -> None:
        """更新对某人的印象"""
        self.impressions[actor_id] = impression

