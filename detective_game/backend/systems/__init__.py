"""Game systems for the detective game."""

from .time_system import TimeSystem
from .event_system import EventSystem
from .scene_system import SceneSystem
from .clue_system import ClueSystem
from .conversation_system import ConversationSystem

__all__ = [
    "TimeSystem",
    "EventSystem",
    "SceneSystem",
    "ClueSystem",
    "ConversationSystem",
]

