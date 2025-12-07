"""Prompt builder for conversation messages."""

from __future__ import annotations

from typing import List


def build_chat_prompt(
    npc_name: str,
    partner_name: str,
    role_text: str,
    team_goal: str,
    role_hint: str,
    abilities_text: str,
    win_text: str,
    memories: List[str],
    chat_history: List[str],
    tasks_info: List[str],
) -> str:
    mem_text = "\n".join(memories) if memories else "(No recent memories)"
    history_text = "\n".join(f"- {h}" for h in chat_history) if chat_history else "(No conversation history)"
    tasks_text = "\n".join(f"- {t}" for t in tasks_info) if tasks_info else "(No task information)"
    return f"""
You are {npc_name}, currently conversing with {partner_name} in a Goose Duck game.
Your identity: {role_text}
Your abilities: {abilities_text or 'None'}
Your win condition: {win_text or 'Complete team objectives'}
Team goal: {team_goal}
Role hint: {role_hint or 'None'}

Task progress:
{tasks_text}

Your memories (recent events):
{mem_text}

Current conversation history:
{history_text}

Please reply briefly (1-2 sentences) in English, keep it conversational and aligned with your identity and motivation. You can choose to continue the conversation or end it if there's no more information.
Respond only in JSON format, no additional explanations:
{{"content": "your reply", "end": false}}
If you want to end the conversation, set end to true and provide a closing statement.
"""
