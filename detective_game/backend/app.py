"""FastAPI entry point for the detective game."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .game_manager import GameManager

app = FastAPI(title="侦探游戏 - 尸人庄谜案")

# CORS 配置
allowed_origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://0.0.0.0:5173",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 游戏管理器实例
game_manager: Optional[GameManager] = None


def get_game_manager() -> GameManager:
    """获取或创建游戏管理器"""
    global game_manager
    if game_manager is None:
        game_manager = GameManager()
    return game_manager


# ============================================================
# 请求模型
# ============================================================

class ActionRequest(BaseModel):
    type: str
    target: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageRequest(BaseModel):
    conversation_id: str
    content: str
    attached_clue: Optional[str] = None
    quoted_message_idx: Optional[int] = None


class EndConversationRequest(BaseModel):
    conversation_id: str


# ============================================================
# API 端点
# ============================================================

@app.get("/api/state")
async def get_state() -> Dict[str, Any]:
    """获取当前游戏状态"""
    manager = get_game_manager()
    return manager.get_game_state_snapshot()


@app.post("/api/action")
async def post_action(request: ActionRequest) -> Dict[str, Any]:
    """执行玩家动作"""
    manager = get_game_manager()
    action = {
        "type": request.type,
        "target": request.target,
        "metadata": request.metadata or {},
    }
    result = await manager.execute_player_action(action)
    return result


@app.post("/api/conversation/message")
async def send_message(request: MessageRequest) -> Dict[str, Any]:
    """在对话中发送消息"""
    manager = get_game_manager()
    result = await manager.send_message_in_conversation(
        conversation_id=request.conversation_id,
        content=request.content,
        attached_clue=request.attached_clue,
        quoted_message_idx=request.quoted_message_idx,
    )
    return result


@app.post("/api/conversation/end")
async def end_conversation(request: EndConversationRequest) -> Dict[str, Any]:
    """结束对话"""
    manager = get_game_manager()
    return manager.end_conversation(request.conversation_id)


@app.get("/api/conversation/{conversation_id}")
async def get_conversation(conversation_id: str) -> Dict[str, Any]:
    """获取对话详情"""
    manager = get_game_manager()
    return manager.get_conversation(conversation_id)


@app.get("/api/conversations")
async def get_conversation_history() -> Dict[str, Any]:
    """获取对话历史"""
    manager = get_game_manager()
    return {"conversations": manager.get_conversation_history()}


@app.get("/api/clues")
async def get_clues() -> Dict[str, Any]:
    """获取玩家收集的线索"""
    manager = get_game_manager()
    return {
        "clues": manager.clue_system.get_player_clues(manager.game_state),
        "key_evidence": manager.clue_system.get_key_evidence(manager.game_state),
    }


@app.get("/api/scenes")
async def get_scenes() -> Dict[str, Any]:
    """获取所有场景信息"""
    manager = get_game_manager()
    return {
        "scenes": manager.scene_system.get_all_scenes_info(manager.game_state),
    }


@app.get("/api/actors")
async def get_actors() -> Dict[str, Any]:
    """获取所有 NPC 信息"""
    manager = get_game_manager()
    return {"actors": manager.get_all_actors_info()}


@app.post("/api/reset")
async def reset_game() -> Dict[str, Any]:
    """重置游戏"""
    global game_manager
    game_manager = GameManager()
    return {"message": "游戏已重置", "state": game_manager.get_game_state_snapshot()}


# ============================================================
# 健康检查
# ============================================================

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """健康检查"""
    return {"status": "ok"}
