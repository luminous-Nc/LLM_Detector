"""FastAPI entry point for the detective game prototype."""

from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .game_state import GameStateManager
from .models import ActionType, Event
from .persona import PersonaActor, PersonaConfig, build_persona_actors
from .story_manager import StoryManager

app = FastAPI(title="Detective Game Prototype")

allowed_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://0.0.0.0:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ActionRequest(BaseModel):
    type: ActionType
    target: Optional[str] = None
    metadata: Dict[str, str] | None = None


PERSONA_CONFIGS = [
    PersonaConfig(
        name="艾琳娜",
        traits=["细心的图书管理员", "善于倾听"],
        backstory="多年来收集镇上的故事，对于每个人的秘密都略知一二。",
        default_location="Library",
    ),
    PersonaConfig(
        name="马修",
        traits=["咖啡师", "健谈"],
        backstory="喜欢打听消息，往往第一个得知八卦。",
        default_location="Cafe",
    ),
]

manager = GameStateManager(PERSONA_CONFIGS)
persona_actors: List[PersonaActor] = build_persona_actors(manager, PERSONA_CONFIGS)
story_manager = StoryManager()
turn_history: List[Event] = []


@app.get("/api/state")
async def get_state() -> Dict[str, object]:
    return manager.snapshot(events=[])


@app.post("/api/action")
async def post_action(request: ActionRequest) -> Dict[str, object]:
    action = {"type": request.type.value, "target": request.target, "metadata": request.metadata}
    manager.apply_player_action(action)
    turn_events: List[Event] = manager.consume_events()

    for actor in persona_actors:
        persona_events = await actor.take_turn(manager, turn_events)
        turn_events.extend(persona_events)

    story_events = story_manager.evaluate(manager.state, turn_events)
    turn_events.extend(story_events)

    turn_history.extend(turn_events)
    return manager.snapshot(events=turn_events)


@app.get("/api/history")
async def get_history(limit: int = 20) -> Dict[str, object]:
    slice_events = turn_history[-limit:]
    return manager.snapshot(events=slice_events)
