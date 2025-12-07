"""Prompt builders for discussion stage speeches."""

from __future__ import annotations

from typing import Any, Dict


def build_meeting_prompt(
    npc_name: str,
    role_info: str,
    goal: str,
    abilities: str,
    win_text: str,
    memories: str,
    messages: str,
) -> str:
    """Construct prompt for NPC meeting speech."""
    return f"""
You are {npc_name}, you are playing a Goose Duck game and currently in a discussion meeting.
[Your Identity] {role_info}
[Your Abilities] {abilities}
[Your Win Condition] {win_text or 'Complete team objectives'}
[Team Goal] {goal}
[Your Current Memories (only you can see)]
{memories}
[Current Meeting Discussion Record]
{messages if messages else '(No speeches yet)'}

Please give a brief speech, combining your memories and the meeting content to achieve your team's goals, while maintaining the reasonableness of your identity. Output the speech content directly, no JSON.
"""
