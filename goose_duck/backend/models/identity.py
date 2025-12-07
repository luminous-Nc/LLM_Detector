"""Identity System - Goose Duck Game Role Identity Definitions"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class Team(str, Enum):
    """Team"""
    GOOD = "good"        # Good team (Goose)
    NEUTRAL = "neutral"  # Neutral team
    EVIL = "evil"        # Evil team (Duck)


class RoleType(str, Enum):
    """Role Type"""
    # Good team
    GOOSE = "goose"               # Regular Goose
    SHERIFF = "sheriff"           # Sheriff [Goose] - Can kill, but killing a goose causes mutual destruction
    VIGILANTE = "vigilante"       # Vigilante [Goose] - Only one kill opportunity
    CANADIAN = "canadian"         # Canadian Goose - Auto-reports when killed
    
    # Neutral team
    DODO = "dodo"                 # Dodo - Wins by being voted out
    
    # Evil team
    ASSASSIN = "assassin"         # Assassin [Duck] - Can snipe during meetings


# Role configurations
ROLE_CONFIGS: Dict[RoleType, Dict[str, Any]] = {
    # Good
    RoleType.GOOSE: {
        "team": Team.GOOD,
        "name": "Goose",
        "description": "Regular good player, wins by completing tasks or finding evil players",
        "abilities": [],
        "can_kill": False,
    },
    RoleType.SHERIFF: {
        "team": Team.GOOD,
        "name": "Sheriff [Goose]",
        "description": "Can kill any role, but killing a goose will cause mutual destruction.",
        "abilities": ["sheriff_kill"],
        "can_kill": True,
    },
    RoleType.VIGILANTE: {
        "team": Team.GOOD,
        "name": "Vigilante [Goose]",
        "description": "Only one kill opportunity, can hunt any target.",
        "abilities": ["single_kill"],
        "can_kill": True,
        "kill_uses": 1,
    },
    RoleType.CANADIAN: {
        "team": Team.GOOD,
        "name": "Canadian Goose",
        "description": "Forces the killer to immediately report when killed.",
        "abilities": ["death_report"],
        "can_kill": False,
    },

    # Neutral
    RoleType.DODO: {
        "team": Team.NEUTRAL,
        "name": "Dodo",
        "description": "Wins directly by being voted out in the voting phase.",
        "abilities": [],
        "can_kill": False,
        "win_condition": "voted_out",
    },
    
    # Evil
    RoleType.ASSASSIN: {
        "team": Team.EVIL,
        "name": "Assassin [Duck]",
        "description": "Disguised as a goose, kills secretly; can snipe twice during meetings (once per meeting).",
        "abilities": ["kill", "snipe"],
        "can_kill": True,
    },
}


@dataclass
class Role:
    """Role Identity"""
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
        """Create role from role type"""
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
    """Player Identity State"""
    player_id: str
    player_name: str
    role: Role
    is_alive: bool = True
    kill_uses_remaining: Optional[int] = None
    
    # Special status
    is_protected: bool = False      # Protected by doctor
    morphed_as: Optional[str] = None  # Morph target

    def __post_init__(self) -> None:
        """Initialize remaining uses for one-time abilities"""
        if self.kill_uses_remaining is None:
            self.kill_uses_remaining = self.role.kill_uses
    
    def can_use_kill(self) -> bool:
        """Whether can use kill ability"""
        return (
            self.is_alive 
            and self.role.can_kill 
            and (self.kill_uses_remaining is None or self.kill_uses_remaining > 0)
        )
    
    def use_kill(self) -> None:
        """Use kill ability and enter cooldown"""
        if self.kill_uses_remaining is not None and self.kill_uses_remaining > 0:
            self.kill_uses_remaining -= 1
    
    def to_dict(self, reveal_role: bool = False) -> Dict[str, Any]:
        """Convert to dictionary, reveal_role controls whether to expose identity"""
        result = {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "is_alive": self.is_alive,
        }
        if reveal_role:
            result["role"] = self.role.to_dict()
        return result
