"""Prompt builder for voting decisions."""

from __future__ import annotations

from typing import Any, Dict, List


def build_vote_prompt(
    npc_name: str,
    role_info: str,
    goal: str,
    abilities: str,
    win_text: str,
    messages: List[Dict[str, Any]],
) -> str:
    history = "\n".join(
        f"- {m.get('speaker_name')}: {m.get('content')}"
        for m in messages[-10:]
    ) or "No speeches"
    return f"""
You are {npc_name}, currently in the voting phase.
[Your Identity] {role_info}
[Your Abilities] {abilities}
[Your Win Condition] {win_text or 'Complete team objectives'}
[Team Goal] {goal}
[Meeting Speech Summary]
{history}

Please choose the most suspicious person from the meeting participants to vote for (or choose to skip vote). Only output the candidate's name or "skip", without other explanations.
"""
