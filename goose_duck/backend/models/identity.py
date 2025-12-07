"""身份系统 - 鹅鸭杀角色身份定义"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class Team(str, Enum):
    """阵营"""
    GOOD = "good"        # 好人阵营（鹅）
    NEUTRAL = "neutral"  # 中立阵营
    EVIL = "evil"        # 坏人阵营（鸭）


class RoleType(str, Enum):
    """角色类型"""
    # 好人阵营
    GOOSE = "goose"               # 普通鹅
    SHERIFF = "sheriff"           # 警长[鹅] - 可以击杀，但误杀鹅会同归于尽
    VIGILANTE = "vigilante"       # 正义使者[鹅] - 仅一次击杀机会
    CANADIAN = "canadian"         # 加拿大鹅 - 被杀后自动报警
    
    # 中立阵营
    DODO = "dodo"                 # 呆呆鸟 - 被投票放逐即获胜
    
    # 坏人阵营
    ASSASSIN = "assassin"         # 刺客[鸭] - 会议期间可狙击


# 角色配置
ROLE_CONFIGS: Dict[RoleType, Dict[str, Any]] = {
    # 好人
    RoleType.GOOSE: {
        "team": Team.GOOD,
        "name": "鹅",
        "description": "普通的好人，通过完成任务或找出坏人获胜",
        "abilities": [],
        "can_kill": False,
    },
    RoleType.SHERIFF: {
        "team": Team.GOOD,
        "name": "警长[鹅]",
        "description": "可以击杀任意角色，但如果击杀了鹅将与目标同归于尽。",
        "abilities": ["sheriff_kill"],
        "can_kill": True,
    },
    RoleType.VIGILANTE: {
        "team": Team.GOOD,
        "name": "正义使者[鹅]",
        "description": "只有一次击杀机会，可以猎杀任意目标。",
        "abilities": ["single_kill"],
        "can_kill": True,
        "kill_uses": 1,
    },
    RoleType.CANADIAN: {
        "team": Team.GOOD,
        "name": "加拿大鹅",
        "description": "被杀后会强制凶手立刻报警。",
        "abilities": ["death_report"],
        "can_kill": False,
    },

    # 中立
    RoleType.DODO: {
        "team": Team.NEUTRAL,
        "name": "呆呆鸟",
        "description": "在投票阶段被放逐即可直接获胜。",
        "abilities": [],
        "can_kill": False,
        "win_condition": "voted_out",
    },
    
    # 坏人
    RoleType.ASSASSIN: {
        "team": Team.EVIL,
        "name": "刺客[鸭]",
        "description": "伪装成鹅，暗中击杀；会议期间可狙击两次（每次会议一次）。",
        "abilities": ["kill", "snipe"],
        "can_kill": True,
    },
}


@dataclass
class Role:
    """角色身份"""
    role_type: RoleType
    team: Team
    name: str
    description: str
    abilities: List[str] = field(default_factory=list)
    can_kill: bool = False
    kill_uses: Optional[int] = None
    win_condition: Optional[str] = None
    
    @classmethod
    def from_type(cls, role_type: RoleType) -> "Role":
        """从角色类型创建角色"""
        config = ROLE_CONFIGS[role_type]
        return cls(
            role_type=role_type,
            team=config["team"],
            name=config["name"],
            description=config["description"],
            abilities=config.get("abilities", []),
            can_kill=config.get("can_kill", False),
            kill_uses=config.get("kill_uses"),
            win_condition=config.get("win_condition"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_type": self.role_type.value,
            "team": self.team.value,
            "name": self.name,
            "description": self.description,
            "abilities": self.abilities,
            "can_kill": self.can_kill,
            "kill_uses": self.kill_uses,
        }


@dataclass
class PlayerIdentity:
    """玩家身份状态"""
    player_id: str
    player_name: str
    role: Role
    is_alive: bool = True
    kill_uses_remaining: Optional[int] = None
    
    # 特殊状态
    is_protected: bool = False      # 被医生保护
    morphed_as: Optional[str] = None  # 变形成的目标

    def __post_init__(self) -> None:
        """初始化一次性技能的剩余次数"""
        if self.kill_uses_remaining is None:
            self.kill_uses_remaining = self.role.kill_uses
    
    def can_use_kill(self) -> bool:
        """是否可以使用杀人能力"""
        return (
            self.is_alive 
            and self.role.can_kill 
            and (self.kill_uses_remaining is None or self.kill_uses_remaining > 0)
        )
    
    def use_kill(self) -> None:
        """使用杀人能力后进入冷却"""
        if self.kill_uses_remaining is not None and self.kill_uses_remaining > 0:
            self.kill_uses_remaining -= 1
    
    def to_dict(self, reveal_role: bool = False) -> Dict[str, Any]:
        """转换为字典，reveal_role 控制是否暴露身份"""
        result = {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "is_alive": self.is_alive,
        }
        if reveal_role:
            result["role"] = self.role.to_dict()
        return result
