"""鹅鸭杀游戏 FastAPI 入口"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .goose_duck_game import GooseDuckGame

app = FastAPI(title="LLM 鹅鸭杀")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 游戏实例
game: Optional[GooseDuckGame] = None


def get_game() -> GooseDuckGame:
    global game
    if game is None:
        game = GooseDuckGame()
    return game


# ============================================================
# 请求模型
# ============================================================

class ActionRequest(BaseModel):
    type: str
    target: Optional[str] = None


class MessageRequest(BaseModel):
    content: str


# ============================================================
# API 端点
# ============================================================

@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """获取游戏状态"""
    g = get_game()
    return g.get_game_snapshot()


@app.post("/api/start")
async def start_game() -> Dict[str, Any]:
    """开始游戏"""
    g = get_game()
    return g.start_game()


@app.post("/api/action")
async def do_action(request: ActionRequest) -> Dict[str, Any]:
    """执行动作"""
    g = get_game()
    return await g.execute_action("player", {
        "type": request.type,
        "target": request.target,
    })


@app.get("/api/map")
async def get_map() -> Dict[str, Any]:
    """获取地图信息"""
    g = get_game()
    return g.get_map_info()


@app.get("/api/discussion")
async def get_discussion() -> Dict[str, Any]:
    """获取讨论状态"""
    g = get_game()
    return g.get_discussion_state()


@app.post("/api/discussion/message")
async def send_discussion_message(request: MessageRequest) -> Dict[str, Any]:
    """发送讨论消息"""
    g = get_game()
    return await g.add_discussion_message("player", request.content)


@app.post("/api/discussion/end")
async def end_discussion() -> Dict[str, Any]:
    """结束讨论，开始投票"""
    g = get_game()
    return g.start_voting()


@app.post("/api/reset")
async def reset_game() -> Dict[str, Any]:
    """重置游戏"""
    global game
    game = GooseDuckGame()
    return {"message": "游戏已重置"}

@app.get("/api/admin/overview")
async def admin_overview() -> Dict[str, Any]:
    """后台观察视图：房间、玩家、事件、讨论"""
    g = get_game()
    snapshot = g.get_game_snapshot()
    map_info = g.get_map_info()
    # 为监控面板生成 A/B/C 标签
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
            "role": player.identity.role.to_dict() if player.identity else None,
        })
    return {
        "phase": snapshot.get("phase"),
        "round": snapshot.get("round"),
        "rooms": map_info.get("rooms", {}),
        "events": snapshot.get("events", []),
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

