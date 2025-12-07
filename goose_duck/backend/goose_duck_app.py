"""Goose Duck Game FastAPI Entry Point"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .goose_duck_game import GooseDuckGame

app = FastAPI(title="LLM Goose Duck Game")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Game instance
game: Optional[GooseDuckGame] = None


def get_game() -> GooseDuckGame:
    global game
    if game is None:
        game = GooseDuckGame()
    return game


# ============================================================
# Request Models
# ============================================================

class ActionRequest(BaseModel):
    type: str
    target: Optional[str] = None


class MessageRequest(BaseModel):
    content: str


class ChatStartRequest(BaseModel):
    target_id: str


# ============================================================
# API Endpoints
# ============================================================

@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """Get game state"""
    g = get_game()
    return g.get_game_snapshot()


@app.post("/api/start")
async def start_game() -> Dict[str, Any]:
    """Start game"""
    g = get_game()
    return g.start_game()


@app.post("/api/action")
async def do_action(request: ActionRequest) -> Dict[str, Any]:
    """Execute action"""
    g = get_game()
    return await g.execute_action("player", {
        "type": request.type,
        "target": request.target,
    })


@app.get("/api/map")
async def get_map() -> Dict[str, Any]:
    """Get map information"""
    g = get_game()
    return g.get_map_info()


@app.get("/api/discussion")
async def get_discussion() -> Dict[str, Any]:
    """Get discussion state"""
    g = get_game()
    return g.get_discussion_state()


@app.post("/api/discussion/message")
async def send_discussion_message(request: MessageRequest) -> Dict[str, Any]:
    """Send discussion message"""
    g = get_game()
    return await g.add_discussion_message("player", request.content)


@app.post("/api/discussion/next")
async def next_speaker() -> Dict[str, Any]:
    """Advance to next speaker (automatically handles NPC speeches)"""
    g = get_game()
    await g.advance_discussion()
    return g.get_discussion_state()


@app.post("/api/chat/start")
async def chat_start(request: ChatStartRequest) -> Dict[str, Any]:
    """Start conversation with specified character"""
    g = get_game()
    return await g._do_talk("player", request.target_id, auto=False)


@app.get("/api/chat/state")
async def chat_state() -> Dict[str, Any]:
    """Get current conversation state"""
    g = get_game()
    return g.get_chat_state()


@app.post("/api/chat/message")
async def chat_message(request: MessageRequest) -> Dict[str, Any]:
    """Player sends conversation message"""
    g = get_game()
    return await g.add_chat_message("player", request.content)


@app.post("/api/chat/end")
async def chat_end() -> Dict[str, Any]:
    """End current conversation"""
    g = get_game()
    return await g.end_chat()


@app.post("/api/discussion/end")
async def end_discussion() -> Dict[str, Any]:
    """End discussion and start voting"""
    g = get_game()
    return g.start_voting()


@app.post("/api/reset")
async def reset_game() -> Dict[str, Any]:
    """Reset game"""
    global game
    game = GooseDuckGame()
    return {"message": "Game has been reset"}

@app.get("/api/admin/overview")
async def admin_overview() -> Dict[str, Any]:
    """Admin overview view: rooms, players, events, discussion"""
    g = get_game()
    snapshot = g.get_game_snapshot()
    map_info = g.get_map_info()
    # All events (for admin)
    all_events = [e.to_dict() for e in g.events]
    # Generate A/B/C labels for monitoring panel
    labels = {}
    statuses = []
    for idx, player in enumerate(sorted(g.players.values(), key=lambda p: p.id)):
        label = chr(ord("A") + idx)
        labels[player.id] = label
        statuses.append({
            "label": label,
            "id": player.id,
            "name": player.name,
            "is_alive": player.is_alive,
            "location": player.location,
            "last_action": player.last_action,
            "last_prompt": getattr(player, "last_prompt", None),
            "last_response": getattr(player, "last_response", None),
            "last_prompts": getattr(player, "last_prompts", {}),
            "last_responses": getattr(player, "last_responses", {}),
            "role": player.identity.role.to_dict() if player.identity else None,
        })
    return {
        "phase": snapshot.get("phase"),
        "round": snapshot.get("round"),
        "rooms": map_info.get("rooms", {}),
        "events": all_events,
        "discussion": {
            "messages": g.state.discussion_messages,
            "reporter": g.state.reporter,
            "body_location": g.state.body_location,
        },
        "players": [p.to_dict(reveal_role=True) for p in g.players.values()],
        "statuses": statuses,
    }


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}

