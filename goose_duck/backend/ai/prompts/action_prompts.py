"""Prompt builders for NPC action decisions."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ...models.identity import RoleType


def build_decision_prompt(
    npc_name: str,
    obs: Dict[str, Any],
    role_hint: str = "",
    win_text: str = "",
) -> str:
    """Build the decision prompt text for an NPC."""
    role = obs.get("role")
    role_info = ""
    team_goals = {
        "good": "Complete tasks or find and eliminate all ducks, protect good players.",
        "evil": "Disguise and eliminate good players or make duck count >= good player count, avoid revealing identity.",
        "neutral": "Act according to your special win condition.",
    }
    if role:
        role_info = f"{role.name} (Team: {role.team.value}), Abilities: {', '.join(role.abilities) if role.abilities else 'None'}"
    team_goal = team_goals.get(role.team.value, "") if role else ""
    win_condition = win_text or (role.win_condition if role and role.win_condition else "")
    if role and not win_condition:
        # fallback by team
        if role.team.value == "good":
            win_condition = "Complete all tasks, or eliminate all evil players."
        elif role.team.value == "evil":
            win_condition = "Evil player count reaches or exceeds good player count."
        else:
            win_condition = "Meet your neutral win condition."

    mem_text = "\n".join(obs.get("memories", [])) if obs.get("memories") else "(No recent memories)"
    people_text = ", ".join(
        f"{p['name']}{'❌' if not p['is_alive'] else ''}" for p in obs.get("people_here", [])
    ) or "No one"
    actions_text = "\n".join(
        f"- {a['type']} -> {a.get('target') or ''} ({a.get('label','')})"
        for a in obs.get("available_actions", [])
    ) or "No available actions"
    tasks_info = obs.get("tasks_info", [])
    tasks_text = "\n".join(
        f"- {t['name']} @ {t.get('room_name') or t.get('room_id') or 'Unknown'} : {t.get('progress', 0)}/2"
        for t in tasks_info
    ) or "No task information"

    return f"""
You are {npc_name}. You are playing a Goose Duck game.
[Game Objectives]
- Good players complete tasks and eliminate evil players; Evil players disguise and eliminate good players; Neutral players win by their own conditions.
- Your team goal: {team_goal}
- Your identity: {role_info}
- Role hint: {role_hint}
[Current Information]
- Phase: {obs.get('phase')}  Round: {obs.get('round')}
- Current location: {obs.get('room').name if obs.get('room') else 'Unknown'}
- Room description: {obs.get('room').description if obs.get('room') else ''}
- Reachable rooms: {', '.join(obs.get('connections', [])) or 'None'}
- People here: {people_text}
- Your abilities: {', '.join(role.abilities) if role and role.abilities else 'None'}
- Your win condition: {win_condition}
- Available actions:
{actions_text}
- Task progress:
{tasks_text}

[Your Memories]
{mem_text}

[Note]
If you are a good player, prioritize completing tasks first. Do not call an emergency meeting before you can confirm identities.

[Goal]
Make your next action based on your team and identity. Choose the most reasonable action.
Respond only in JSON format, no other content:
{{"action": "move|kill|report|emergency|vote|wait", "target": "room_id or player_id or null", "reason": "brief reason"}}
"""
