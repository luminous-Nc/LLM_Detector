"""State management and turn controller for the detective game."""

from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable, List, Optional

from .models import (
    ActionType,
    Clue,
    Event,
    EventType,
    GameState,
    Location,
    PersonaConfig,
    PersonaState,
)


class GameStateManager:
    """Owns the canonical game state and exposes turn level operations."""

    def __init__(self, persona_configs: Iterable[PersonaConfig]):
        self.state = GameState()
        self._event_log: List[Event] = []
        self._init_locations()
        self._init_personas(persona_configs)

    # --------------------------------------------------------------------- setup
    def _init_locations(self) -> None:
        locations = {
            "Town Square": Location(
                name="Town Square",
                description="The heart of the town, where townsfolk gather.",
                tags={"public", "central"},
            ),
            "Library": Location(
                name="Library",
                description="Quiet stacks of books and whispered secrets.",
                tags={"quiet", "knowledge"},
            ),
            "Cafe": Location(
                name="Cafe",
                description="The smell of coffee beans and murmured gossip fill the air.",
                tags={"social"},
            ),
        }
        self.state.locations.update(locations)

    def _init_personas(self, persona_configs: Iterable[PersonaConfig]) -> None:
        for config in persona_configs:
            location = config.default_location
            self.state.personas[config.name] = PersonaState(
                name=config.name,
                location=location,
                scratch={"traits": ", ".join(config.traits), "backstory": config.backstory},
            )
            self.state.locations[location].occupants.add(config.name)

    # ---------------------------------------------------------------- turn logic
    def log_event(self, event: Event) -> None:
        self._event_log.append(event)

    def consume_events(self) -> List[Event]:
        events = list(self._event_log)
        self._event_log.clear()
        return events

    def available_actions(self) -> List[Dict[str, object]]:
        """Return structured action options for the frontend."""
        options: List[Dict[str, object]] = []
        curr_loc = self.state.player_location
        locations = [
            {"type": ActionType.MOVE, "label": f"前往 {name}", "target": name}
            for name in self.state.locations
            if name != curr_loc
        ]
        talk_targets = [
            {"type": ActionType.TALK, "label": f"与 {persona} 对话", "target": persona}
            for persona in sorted(self.state.locations[curr_loc].occupants)
        ]
        investigate = {
            "type": ActionType.INVESTIGATE,
            "label": "调查当前地点",
            "target": curr_loc,
        }
        options.extend(locations)
        options.extend(talk_targets)
        options.append(investigate)
        options.append({"type": ActionType.REFLECT, "label": "梳理线索", "target": None})
        return options

    def apply_player_action(self, action: Dict[str, object]) -> None:
        action_type = ActionType(action["type"])
        target = action.get("target")
        if action_type == ActionType.MOVE and isinstance(target, str):
            self._move_player(target)
        elif action_type == ActionType.TALK and isinstance(target, str):
            self._talk_to_persona(target)
        elif action_type == ActionType.INVESTIGATE:
            self._investigate_location()
        elif action_type == ActionType.REFLECT:
            self._reflect()
        else:
            self.log_event(Event(EventType.SYSTEM, "未知的玩家动作。"))
        self.state.turn += 1

    # ----------------------------------------------------------------- actions
    def _move_player(self, destination: str) -> None:
        if destination not in self.state.locations:
            self.log_event(Event(EventType.SYSTEM, "你试图前往未知地点，但失败了。"))
            return
        self.state.player_location = destination
        self.log_event(
            Event(
                event_type=EventType.PLAYER_ACTION,
                text=f"你来到了 {destination}。",
                actor="player",
                location=destination,
            )
        )

    def _talk_to_persona(self, persona_name: str) -> None:
        if persona_name not in self.state.personas:
            self.log_event(Event(EventType.SYSTEM, f"{persona_name} 并不存在。"))
            return
        persona_state = self.state.personas[persona_name]
        if persona_state.location != self.state.player_location:
            self.log_event(Event(EventType.SYSTEM, f"{persona_name} 不在这里。"))
            return
        self.log_event(
            Event(
                event_type=EventType.PLAYER_ACTION,
                text=f"你向 {persona_name} 打了声招呼。",
                actor="player",
                location=self.state.player_location,
            )
        )

    def _investigate_location(self) -> None:
        location = self.state.player_location
        clue_id = f"{location.lower().replace(' ', '_')}_clue_{self.state.turn}"
        event = Event(
            event_type=EventType.CLUE_FOUND,
            text=f"你在 {location} 发现了一条线索。",
            actor="player",
            location=location,
            metadata={"clue_id": clue_id},
        )
        self.state.clues[clue_id] = Clue(
            clue_id=clue_id,
            summary=f"{location} 的新发现",
            discovered_by="player",
        )
        self.log_event(event)

    def _reflect(self) -> None:
        summary = ", ".join(sorted(self.state.clues.keys())) or "暂无线索"
        self.log_event(
            Event(
                event_type=EventType.PLAYER_ACTION,
                text=f"你回顾了目前掌握的线索：{summary}",
                actor="player",
            )
        )

    # ------------------------------------------------------------ serialization
    def snapshot(self, events: Optional[List[Event]] = None) -> Dict[str, object]:
        return {
            "turn": self.state.turn,
            "current_time": self.state.current_time,
            "player_location": self.state.player_location,
            "locations": self.state.location_snapshot(),
            "clues": list(self.state.clues.keys()),
            "story_flags": self.state.story_flags,
            "personas": {
                name: {"location": persona.location, "scratch": persona.scratch}
                for name, persona in self.state.personas.items()
            },
            "available_actions": self.available_actions(),
            "events": [asdict(event) for event in (events or [])],
        }
