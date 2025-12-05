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


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}

