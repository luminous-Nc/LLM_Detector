"""Persona actor implementation inspired by the original project."""

from __future__ import annotations

import textwrap
from typing import List, Sequence

from .game_state import GameStateManager
from .llm import EchoLLMClient, LLMClient, get_llm_client
from .models import Event, EventType, PersonaConfig, PersonaState


class PersonaActor:
    """Wraps PersonaState with LLM-backed decision making."""

    def __init__(self, config: PersonaConfig, state: PersonaState, llm_client: LLMClient | None = None):
        self.config = config
        self.state = state
        self.llm = llm_client or EchoLLMClient()

    async def take_turn(self, game: GameStateManager, recent_events: Sequence[Event]) -> List[Event]:
        """Generate persona actions for the current turn."""
        observations = self._format_observations(game, recent_events)
        prompt = self._build_prompt(observations)
        reply = await self.llm.complete(prompt)
        action_event = Event(
            event_type=EventType.NPC_ACTION,
            text=f"{self.config.name}：{reply}",
            actor=self.config.name,
            location=self.state.location,
        )
        return [action_event]

    # ----------------------------------------------------------------- helpers
    def _format_observations(self, game: GameStateManager, events: Sequence[Event]) -> str:
        recent_lines: List[str] = []
        for event in events:
            if event.location and event.location != self.state.location:
                continue
            if event.actor == self.config.name:
                continue
            recent_lines.append(f"- {event.text}")

        if not recent_lines:
            recent_lines.append("- 当前地点一片寂静，没有新的动态。")
        scratch_summary = self.state.scratch.get("internal_note", "（暂无记忆）")
        return "\n".join(recent_lines) + f"\n过去的思考：{scratch_summary}"

    def _build_prompt(self, observations: str) -> str:
        backstory = self.state.scratch.get("backstory", self.config.backstory)
        traits = self.state.scratch.get("traits", ", ".join(self.config.traits))
        template = textwrap.dedent(
            f"""
            角色设定：
            姓名：{self.config.name}
            关键词：{traits}
            背景：{backstory}

            当前场景观察：
            {observations}

            请以角色口吻写一句话，回应当前局面，推动剧情或提供线索。
            用简短自然的中文回复。
            """
        ).strip()
        return template


def build_persona_actors(game: GameStateManager, configs: Sequence[PersonaConfig]) -> List[PersonaActor]:
    actors: List[PersonaActor] = []
    # Initialize the LLM client once using the factory function
    llm_client = get_llm_client()

    for config in configs:
        state = game.state.personas[config.name]
        actors.append(PersonaActor(config, state, llm_client=llm_client))
    return actors

