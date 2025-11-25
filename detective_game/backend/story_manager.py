"""Simple story manager that reacts to game state and events."""

from __future__ import annotations

from typing import Iterable, List

from .models import Event, EventType, GameState


class StoryManager:
    """Rule based hook for unlocking narrative beats."""

    def __init__(self) -> None:
        self.triggered: set[str] = set()

    def evaluate(self, game_state: GameState, recent_events: Iterable[Event]) -> List[Event]:
        new_events: List[Event] = []
        if "first_meeting" not in self.triggered and game_state.turn >= 1:
            new_events.append(
                Event(
                    event_type=EventType.STORY,
                    text="风吹动广场上的旗帜，仿佛暗示着隐藏的秘密。",
                )
            )
            self.triggered.add("first_meeting")
        return new_events

