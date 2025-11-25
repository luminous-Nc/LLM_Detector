"""Conversation system for managing dialogues."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..models.conversation import Conversation, Message

if TYPE_CHECKING:
    from ..models import GameState, GameTime


class ConversationSystem:
    """对话系统 - 管理玩家与 NPC 以及 NPC 之间的对话"""

    def __init__(self):
        self.conversations: Dict[str, Conversation] = {}
        self.active_conversations: Dict[str, str] = {}  # participant -> conversation_id

    def start_conversation(
        self,
        participant1: str,
        participant2: str,
        location: str,
        game_time: GameTime,
    ) -> Conversation:
        """开始一段新对话"""
        # 检查是否已有进行中的对话
        if participant1 in self.active_conversations:
            existing_id = self.active_conversations[participant1]
            existing = self.conversations.get(existing_id)
            if existing and not existing.ended:
                return existing

        conv = Conversation.create(
            participant1=participant1,
            participant2=participant2,
            location=location,
            day=game_time.day,
            time=game_time.period.value,
        )
        
        self.conversations[conv.id] = conv
        self.active_conversations[participant1] = conv.id
        self.active_conversations[participant2] = conv.id
        
        return conv

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        """获取对话"""
        return self.conversations.get(conv_id)

    def get_active_conversation(self, participant: str) -> Optional[Conversation]:
        """获取参与者当前的活跃对话"""
        conv_id = self.active_conversations.get(participant)
        if conv_id:
            conv = self.conversations.get(conv_id)
            if conv and not conv.ended:
                return conv
        return None

    def add_message(
        self,
        conv_id: str,
        speaker: str,
        content: str,
        game_time: GameTime,
        attached_clue: Optional[str] = None,
        quoted_message_idx: Optional[int] = None,
    ) -> Optional[Message]:
        """添加消息到对话"""
        conv = self.conversations.get(conv_id)
        if not conv or conv.ended:
            return None

        return conv.add_message(
            speaker=speaker,
            content=content,
            day=game_time.day,
            time=game_time.period.value,
            attached_clue=attached_clue,
            quoted_message_idx=quoted_message_idx,
        )

    def end_conversation(self, conv_id: str) -> bool:
        """结束对话"""
        conv = self.conversations.get(conv_id)
        if not conv:
            return False

        conv.ended = True
        
        # 清理活跃对话映射
        for participant in conv.participants:
            if self.active_conversations.get(participant) == conv_id:
                del self.active_conversations[participant]

        return True

    def get_conversation_history(
        self,
        participant: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """获取参与者的对话历史"""
        history = []
        for conv in self.conversations.values():
            if participant in conv.participants:
                history.append(conv.to_dict())
        
        # 按时间倒序
        history.sort(
            key=lambda x: (x["started_day"], x["started_time"]),
            reverse=True,
        )
        
        return history[:limit]

    def get_conversations_with(
        self,
        participant1: str,
        participant2: str,
    ) -> List[Conversation]:
        """获取两个参与者之间的所有对话"""
        result = []
        for conv in self.conversations.values():
            if participant1 in conv.participants and participant2 in conv.participants:
                result.append(conv)
        return result

    def format_conversation_for_prompt(
        self,
        conv_id: str,
        max_messages: int = 20,
    ) -> str:
        """格式化对话历史（用于 LLM prompt）"""
        conv = self.conversations.get(conv_id)
        if not conv:
            return ""
        return conv.format_history(max_messages)

    def get_all_messages_involving(
        self,
        participant: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取涉及某参与者的所有消息"""
        messages = []
        for conv in self.conversations.values():
            if participant in conv.participants:
                for i, msg in enumerate(conv.messages):
                    messages.append({
                        "conversation_id": conv.id,
                        "message_index": i,
                        "speaker": msg.speaker,
                        "content": msg.content,
                        "day": msg.day,
                        "time": msg.time,
                        "attached_clue": msg.attached_clue,
                        "other_participant": conv.get_other_participant(participant),
                    })
        
        # 按时间排序
        messages.sort(key=lambda x: (x["day"], x["time"]), reverse=True)
        return messages[:limit]

