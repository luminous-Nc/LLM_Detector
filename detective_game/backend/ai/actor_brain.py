"""NPC decision engine powered by LLM."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .llm_client import LLMClient, EchoLLMClient

if TYPE_CHECKING:
    from ..models import ActorConfig, ActorState, GameState, GameTime
    from ..models.event import GameEvent


class NPCAction(str, Enum):
    """NPC 可执行的动作类型"""
    MOVE = "move"                    # 移动到其他地点
    TALK_TO_NPC = "talk_to_npc"      # 与其他 NPC 对话
    TALK_TO_PLAYER = "talk_to_player"  # 主动与玩家搭话
    WAIT = "wait"                    # 等待/观察
    SPECIAL = "special"              # 特殊行动（凶手行凶等）


@dataclass
class ActionDecision:
    """NPC 的行动决策"""
    action: NPCAction
    target: Optional[str] = None     # 目标地点或目标人物
    reason: str = ""                 # 内心想法


@dataclass
class Observations:
    """NPC 能观察到的信息"""
    current_time: str
    current_day: int
    location: str
    scene_description: str
    people_present: List[str]
    recent_events: List[str]
    schedule: Dict[str, str]
    memory: List[str]
    impressions: Dict[str, str]
    known_clues: List[str]


class ActorBrain:
    """NPC 的 AI 大脑"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or EchoLLMClient()
        self._load_prompts()

    def _load_prompts(self) -> None:
        """加载 Prompt 模板"""
        prompts_dir = Path(__file__).parent / "prompts"
        
        self.decision_prompt_template = self._read_prompt(
            prompts_dir / "actor_decide.txt"
        )
        self.dialogue_prompt_template = self._read_prompt(
            prompts_dir / "actor_dialogue.txt"
        )

    def _read_prompt(self, path: Path) -> str:
        """读取 prompt 文件"""
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def gather_observations(
        self,
        actor_config: ActorConfig,
        actor_state: ActorState,
        game_state: GameState,
        scene_description: str,
        people_at_location: List[str],
        recent_events: List[GameEvent],
    ) -> Observations:
        """收集 NPC 能观察到的信息"""
        # 过滤最近事件（只包含在同一地点的）
        relevant_events = []
        for event in recent_events[-10:]:
            if event.location == actor_state.location or not event.location:
                relevant_events.append(f"[{event.event_type.value}] {event.text}")

        # 获取记忆摘要
        memory_summary = []
        for mem in actor_state.get_recent_memory(5):
            memory_summary.append(f"第{mem.day}天{mem.time}: {mem.content}")

        return Observations(
            current_time=game_state.time.period.to_chinese(),
            current_day=game_state.time.day,
            location=actor_state.location,
            scene_description=scene_description,
            people_present=people_at_location,
            recent_events=relevant_events,
            schedule=actor_config.schedule,
            memory=memory_summary,
            impressions=actor_state.impressions,
            known_clues=list(actor_state.known_clues),
        )

    async def decide_action(
        self,
        actor_config: ActorConfig,
        actor_state: ActorState,
        observations: Observations,
        available_locations: List[str],
    ) -> ActionDecision:
        """决定 NPC 的下一步行动"""
        
        # 如果 NPC 已死亡，不执行任何动作
        if not actor_state.is_alive:
            return ActionDecision(action=NPCAction.WAIT, reason="已死亡")

        # 构建决策 prompt
        prompt = self._build_decision_prompt(
            actor_config, actor_state, observations, available_locations
        )

        # 调用 LLM
        response = await self.llm.complete(prompt)

        # 解析响应
        return self._parse_decision_response(response, available_locations, observations)

    def _build_decision_prompt(
        self,
        config: ActorConfig,
        state: ActorState,
        obs: Observations,
        available_locations: List[str],
    ) -> str:
        """构建决策 prompt"""
        # 使用模板或手动构建
        if self.decision_prompt_template:
            return self.decision_prompt_template.format(
                actor_name=config.name,
                occupation=config.occupation,
                personality_traits=", ".join(config.traits),
                speaking_style=config.speaking_style,
                private_secret=config.secret,
                private_goal=config.goal,
                day=obs.current_day,
                time_period=obs.current_time,
                location=obs.location,
                scene_description=obs.scene_description,
                people_present=", ".join(obs.people_present) if obs.people_present else "无人",
                recent_memory="\n".join(obs.memory) if obs.memory else "无",
                impressions="\n".join(f"- {k}: {v}" for k, v in obs.impressions.items()) if obs.impressions else "无",
                schedule="\n".join(f"- {k}: {v}" for k, v in obs.schedule.items()),
                available_locations=", ".join(available_locations),
            )
        
        # 默认 prompt
        return f"""你是 {config.name}，{config.occupation}。

【你的性格】
{", ".join(config.traits)}
说话风格：{config.speaking_style}

【你的秘密】
{config.secret}
你的目标：{config.goal}

【当前情况】
时间：第{obs.current_day}天 {obs.current_time}
地点：{obs.location}
场景：{obs.scene_description}

【在场的人】
{", ".join(obs.people_present) if obs.people_present else "无人"}

【你最近的记忆】
{chr(10).join(obs.memory) if obs.memory else "无"}

【你对其他人的印象】
{chr(10).join(f"- {k}: {v}" for k, v in obs.impressions.items()) if obs.impressions else "无"}

【你今天的日程】
{chr(10).join(f"- {k}: {v}" for k, v in obs.schedule.items())}

【可前往的地点】
{", ".join(available_locations)}

---

根据以上信息，决定你接下来要做什么。
可选行动：
1. MOVE: 前往其他地点
2. TALK: 与在场的某人交谈
3. WAIT: 留在原地观察

请以 JSON 格式回复：
{{"action": "MOVE/TALK/WAIT", "target": "目标地点或人物", "reason": "简短说明原因"}}
"""

    def _parse_decision_response(
        self,
        response: str,
        available_locations: List[str],
        observations: Observations,
    ) -> ActionDecision:
        """解析 LLM 的决策响应"""
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[^{}]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                action_str = data.get("action", "WAIT").upper()
                target = data.get("target", "")
                reason = data.get("reason", "")

                if action_str == "MOVE":
                    if target in available_locations:
                        return ActionDecision(
                            action=NPCAction.MOVE,
                            target=target,
                            reason=reason,
                        )
                elif action_str == "TALK":
                    if target in observations.people_present:
                        if target == "player" or target == "玩家":
                            return ActionDecision(
                                action=NPCAction.TALK_TO_PLAYER,
                                target="player",
                                reason=reason,
                            )
                        else:
                            return ActionDecision(
                                action=NPCAction.TALK_TO_NPC,
                                target=target,
                                reason=reason,
                            )

        except (json.JSONDecodeError, KeyError):
            pass

        # 默认等待
        return ActionDecision(action=NPCAction.WAIT, reason="观察周围情况")

    async def generate_dialogue_response(
        self,
        actor_config: ActorConfig,
        actor_state: ActorState,
        conversation_history: str,
        incoming_message: str,
        speaker: str,
        attached_clue: Optional[Dict[str, Any]] = None,
        quoted_message: Optional[str] = None,
    ) -> str:
        """生成 NPC 的对话回复"""
        
        # 构建对话 prompt
        prompt = self._build_dialogue_prompt(
            actor_config,
            actor_state,
            conversation_history,
            incoming_message,
            speaker,
            attached_clue,
            quoted_message,
        )

        # 调用 LLM
        response = await self.llm.complete(prompt)
        
        return response.strip()

    def _build_dialogue_prompt(
        self,
        config: ActorConfig,
        state: ActorState,
        history: str,
        message: str,
        speaker: str,
        clue: Optional[Dict[str, Any]],
        quoted: Optional[str],
    ) -> str:
        """构建对话 prompt"""
        # 证据部分
        clue_section = ""
        if clue:
            clue_section = f"""
【对方出示了证据】
证据名称：{clue.get('name', '未知')}
证据描述：{clue.get('description', '无')}
"""

        # 引用部分
        quote_section = ""
        if quoted:
            quote_section = f"""
【对方引用了之前的发言】
被引用的内容："{quoted}"
"""

        # 对说话者的印象
        impression = state.impressions.get(speaker, "初次见面，不太了解")

        return f"""你是 {config.name}，正在与 {speaker} 对话。

【你的身份】
{config.occupation}
{config.description}

【你的秘密（不要直接透露）】
{config.secret}

【你的目标】
{config.goal}

【你对 {speaker} 的印象】
{impression}

【对话历史】
{history if history else "（对话刚开始）"}

【对方刚才说的话】
{message}
{clue_section}
{quote_section}
---

请以你的角色身份回复这段对话。
要求：
1. 符合你的性格：{", ".join(config.traits)}
2. 说话风格：{config.speaking_style}
3. 如果涉及你的秘密，要谨慎回避或巧妙撒谎
4. 如果对方出示了证据，根据证据内容做出适当反应
5. 保持自然的对话节奏，回复长度适中

直接回复对话内容："""

    def update_impression(
        self,
        actor_state: ActorState,
        target_id: str,
        interaction_summary: str,
    ) -> None:
        """更新 NPC 对某人的印象（简单版本，不使用 LLM）"""
        current = actor_state.impressions.get(target_id, "")
        if current:
            # 追加新印象
            actor_state.impressions[target_id] = f"{current}; {interaction_summary}"
        else:
            actor_state.impressions[target_id] = interaction_summary

