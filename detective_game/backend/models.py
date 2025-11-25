"""Core data structures used by the detective game backend."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple


class ActionType(str, Enum):
    """Enumerates the actions the player can take per turn."""

    MOVE = "move"
    TALK = "talk"
    INVESTIGATE = "investigate"
    REFLECT = "reflect"
    END_TURN = "end_turn"


class EventType(str, Enum):
    """Types of events that can show up in the turn log."""

    PLAYER_ACTION = "player_action"
    NPC_ACTION = "npc_action"
    STORY = "story"
    CLUE_FOUND = "clue_found"
    SYSTEM = "system"


@dataclass
class Event:
    event_type: EventType
    text: str
    actor: Optional[str] = None
    location: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class Clue:
    clue_id: str
    summary: str
    discovered_by: str
    important: bool = False


@dataclass
class Location:
    name: str
    description: str
    tags: Set[str] = field(default_factory=set)
    occupants: Set[str] = field(default_factory=set)


@dataclass
class PersonaConfig:
    name: str
    traits: List[str]
    backstory: str
    default_location: str


@dataclass
class PersonaState:
    name: str
    location: str
    scratch: Dict[str, str] = field(default_factory=dict)
    known_clues: Set[str] = field(default_factory=set)


@dataclass
class GameState:
    turn: int = 0
    current_time: str = "Day 1 - Morning"
    player_location: str = "Town Square"
    locations: Dict[str, Location] = field(default_factory=dict)
    clues: Dict[str, Clue] = field(default_factory=dict)
    story_flags: Dict[str, bool] = field(default_factory=dict)
    personas: Dict[str, PersonaState] = field(default_factory=dict)

    def location_snapshot(self) -> Dict[str, Dict[str, List[str]]]:
        """Return a lightweight snapshot for clients."""
        return {
            name: {
                "description": loc.description,
                "tags": sorted(loc.tags),
                "occupants": sorted(loc.occupants),
            }
            for name, loc in self.locations.items()
        }

