"""Game manager that orchestrates all game systems."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .loaders import load_all_settings
from .models import (
    ActorConfig, ActorState, ActorRole,
    SceneConfig, SceneState,
    ClueConfig,
    GameState, GameTime, TimePeriod, PlayerState,
    GameEvent, EventType, TimelineEvent,
    Conversation, Message,
)
from .systems import (
    TimeSystem,
    EventSystem,
    SceneSystem,
    ClueSystem,
    ConversationSystem,
)
from .ai import ActorBrain, NPCAction, get_llm_client


class GameManager:
    """游戏主控制器 - 整合所有子系统"""

    def __init__(self):
        # 加载配置
        self.settings = load_all_settings()
        self.config = self.settings["config"]
        
        # 初始化游戏状态
        game_config = self.config.get("game", {})
        starting_time = game_config.get("starting_time", {})
        
        self.game_state = GameState(
            time=GameTime(
                day=starting_time.get("day", 1),
                period=TimePeriod(starting_time.get("period", "morning")),
            ),
            player=PlayerState(
                name=self.config.get("player", {}).get("name", "玩家"),
                location=game_config.get("starting_location", "entrance_hall"),
            ),
        )
        
        # 初始化子系统
        self.time_system = TimeSystem(
            max_days=game_config.get("max_days", 3)
        )
        self.event_system = EventSystem(self.settings["timeline"])
        self.scene_system = SceneSystem(self.settings["scenes"])
        self.clue_system = ClueSystem(self.settings["clues"])
        self.conversation_system = ConversationSystem()
        
        # 初始化 NPC
        self.actor_configs: Dict[str, ActorConfig] = {}
        self.actor_states: Dict[str, ActorState] = {}
        self._init_actors()
        
        # 初始化 AI
        self.llm_client = get_llm_client()
        self.actor_brain = ActorBrain(self.llm_client)
        
        # 事件日志
        self.current_turn_events: List[GameEvent] = []

    def _init_actors(self) -> None:
        """初始化所有 NPC"""
        for actor_id, actor_data in self.settings["actors"].items():
            config = ActorConfig.from_dict(actor_data)
            self.actor_configs[actor_id] = config
            
            # 创建状态
            default_location = config.schedule.get("morning", "entrance_hall")
            state = ActorState(
                id=actor_id,
                location=default_location,
            )
            self.actor_states[actor_id] = state
            
            # 添加到场景
            self.scene_system.move_actor_to_scene(actor_id, "", default_location)

    # ============================================================
    # 游戏状态查询
    # ============================================================

    def get_game_state_snapshot(self) -> Dict[str, Any]:
        """获取游戏状态快照"""
        player_loc = self.game_state.player.location
        
        return {
            "time": self.game_state.time.to_dict(),
            "player": {
                "name": self.game_state.player.name,
                "location": player_loc,
                "location_name": self._get_scene_name(player_loc),
                "clues_count": len(self.game_state.player.clues),
            },
            "current_scene": self._get_scene_info(player_loc),
            "available_actions": self._get_available_actions(),
            "recent_events": [e.to_dict() for e in self.current_turn_events[-10:]],
            "actors": self._get_visible_actors(),
            "flags": dict(self.game_state.flags),
        }

    def _get_scene_name(self, scene_id: str) -> str:
        """获取场景名称"""
        config = self.scene_system.get_scene_config(scene_id)
        return config.name if config else scene_id

    def _get_scene_info(self, scene_id: str) -> Dict[str, Any]:
        """获取场景信息"""
        config = self.scene_system.get_scene_config(scene_id)
        if not config:
            return {}
        
        return {
            "id": scene_id,
            "name": config.name,
            "description": config.description.strip(),
            "investigation_points": self.scene_system.get_investigation_points(
                scene_id, self.game_state
            ),
            "connected_scenes": self.scene_system.get_connected_scenes(
                scene_id, self.game_state
            ),
            "occupants": self._get_actors_at_location(scene_id),
        }

    def _get_actors_at_location(self, location: str) -> List[Dict[str, Any]]:
        """获取在某地点的 NPC"""
        actors = []
        for actor_id, state in self.actor_states.items():
            if state.location == location and state.is_alive:
                config = self.actor_configs.get(actor_id)
                if config:
                    actors.append({
                        "id": actor_id,
                        "name": config.name,
                        "description": config.description,
                    })
        return actors

    def _get_visible_actors(self) -> List[Dict[str, Any]]:
        """获取玩家可见的 NPC（同一地点）"""
        return self._get_actors_at_location(self.game_state.player.location)

    def _get_available_actions(self) -> List[Dict[str, Any]]:
        """获取玩家可执行的动作"""
        actions = []
        player_loc = self.game_state.player.location
        
        # 移动动作
        for scene in self.scene_system.get_connected_scenes(player_loc, self.game_state):
            if scene["accessible"]:
                actions.append({
                    "type": "move",
                    "label": f"前往 {scene['name']}",
                    "target": scene["id"],
                })
        
        # 对话动作
        for actor in self._get_actors_at_location(player_loc):
            actions.append({
                "type": "talk",
                "label": f"与 {actor['name']} 对话",
                "target": actor["id"],
            })
        
        # 调查动作
        for point in self.scene_system.get_investigation_points(player_loc, self.game_state):
            if point["can_investigate"]:
                actions.append({
                    "type": "investigate",
                    "label": f"调查 {point['name']}",
                    "target": point["id"],
                    "description": point["description"],
                })
        
        # 查看线索
        if self.game_state.player.clues:
            actions.append({
                "type": "view_clues",
                "label": "查看线索",
                "target": None,
            })
        
        # 等待（推进时间）
        actions.append({
            "type": "wait",
            "label": "等待（时间推进）",
            "target": None,
        })
        
        return actions

    # ============================================================
    # 玩家动作
    # ============================================================

    async def execute_player_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行玩家动作"""
        action_type = action.get("type")
        target = action.get("target")
        
        self.current_turn_events = []
        
        if action_type == "move":
            await self._player_move(target)
        elif action_type == "talk":
            await self._player_start_talk(target)
        elif action_type == "investigate":
            await self._player_investigate(target)
        elif action_type == "wait":
            await self._player_wait()
        elif action_type == "view_clues":
            return self._get_player_clues()
        
        # 推进时间
        self._advance_time()
        
        # 触发世界事件
        triggered_events = self.event_system.check_and_trigger_events(
            self.game_state, self.actor_states
        )
        self.current_turn_events.extend(triggered_events)
        
        # NPC 行动
        await self._execute_npc_turns()
        
        return self.get_game_state_snapshot()

    async def _player_move(self, destination: str) -> None:
        """玩家移动"""
        is_accessible, message = self.scene_system.check_accessibility(
            destination, self.game_state
        )
        
        if not is_accessible:
            self.current_turn_events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=message or f"无法前往 {destination}",
                day=self.game_state.time.day,
                time=self.game_state.time.period.value,
            ))
            return
        
        old_location = self.game_state.player.location
        self.game_state.player.location = destination
        
        scene_name = self._get_scene_name(destination)
        self.current_turn_events.append(GameEvent(
            event_type=EventType.PLAYER_ACTION,
            text=f"你来到了 {scene_name}。",
            day=self.game_state.time.day,
            time=self.game_state.time.period.value,
            location=destination,
        ))

    async def _player_start_talk(self, actor_id: str) -> None:
        """玩家开始对话"""
        actor_state = self.actor_states.get(actor_id)
        actor_config = self.actor_configs.get(actor_id)
        
        if not actor_state or not actor_config:
            return
        
        if actor_state.location != self.game_state.player.location:
            self.current_turn_events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=f"{actor_config.name} 不在这里。",
                day=self.game_state.time.day,
                time=self.game_state.time.period.value,
            ))
            return
        
        # 创建对话
        conv = self.conversation_system.start_conversation(
            "player",
            actor_id,
            self.game_state.player.location,
            self.game_state.time,
        )
        
        self.current_turn_events.append(GameEvent(
            event_type=EventType.PLAYER_ACTION,
            text=f"你开始与 {actor_config.name} 交谈。",
            day=self.game_state.time.day,
            time=self.game_state.time.period.value,
            location=self.game_state.player.location,
            metadata={"conversation_id": conv.id},
        ))

    async def _player_investigate(self, point_id: str) -> None:
        """玩家调查"""
        player_loc = self.game_state.player.location
        clue_id = self.scene_system.investigate_point(
            player_loc, point_id, self.game_state
        )
        
        if clue_id:
            clue_info = self.clue_system.discover_clue(
                clue_id, "player", self.game_state
            )
            if clue_info:
                self.current_turn_events.append(GameEvent(
                    event_type=EventType.PLAYER_ACTION,
                    text=f"你发现了 {clue_info['name']}！\n{clue_info['description']}",
                    day=self.game_state.time.day,
                    time=self.game_state.time.period.value,
                    location=player_loc,
                    metadata={"clue_id": clue_id},
                ))
                return
        
        self.current_turn_events.append(GameEvent(
            event_type=EventType.PLAYER_ACTION,
            text="你仔细调查了一番，但没有发现什么特别的东西。",
            day=self.game_state.time.day,
            time=self.game_state.time.period.value,
            location=player_loc,
        ))

    async def _player_wait(self) -> None:
        """玩家等待"""
        self.current_turn_events.append(GameEvent(
            event_type=EventType.PLAYER_ACTION,
            text="你决定观察一下周围的情况...",
            day=self.game_state.time.day,
            time=self.game_state.time.period.value,
            location=self.game_state.player.location,
        ))

    def _get_player_clues(self) -> Dict[str, Any]:
        """获取玩家线索列表"""
        return {
            "type": "clues_view",
            "clues": self.clue_system.get_player_clues(self.game_state),
            "key_evidence": self.clue_system.get_key_evidence(self.game_state),
        }

    # ============================================================
    # 对话系统
    # ============================================================

    async def send_message_in_conversation(
        self,
        conversation_id: str,
        content: str,
        attached_clue: Optional[str] = None,
        quoted_message_idx: Optional[int] = None,
    ) -> Dict[str, Any]:
        """在对话中发送消息"""
        conv = self.conversation_system.get_conversation(conversation_id)
        if not conv or conv.ended:
            return {"error": "对话不存在或已结束"}
        
        # 添加玩家消息
        self.conversation_system.add_message(
            conversation_id,
            "player",
            content,
            self.game_state.time,
            attached_clue,
            quoted_message_idx,
        )
        
        # 获取 NPC 回复
        other_id = conv.get_other_participant("player")
        if other_id and other_id != "player":
            actor_config = self.actor_configs.get(other_id)
            actor_state = self.actor_states.get(other_id)
            
            if actor_config and actor_state:
                # 获取证据信息
                clue_info = None
                if attached_clue:
                    clue_info = self.clue_system.get_clue_info(attached_clue)
                
                # 获取引用消息
                quoted = None
                if quoted_message_idx is not None:
                    quoted_msg = conv.get_message_by_idx(quoted_message_idx)
                    if quoted_msg:
                        quoted = quoted_msg.content
                
                # 生成回复
                history = conv.format_history(10)
                response = await self.actor_brain.generate_dialogue_response(
                    actor_config,
                    actor_state,
                    history,
                    content,
                    "player",
                    clue_info,
                    quoted,
                )
                
                # 添加 NPC 回复
                self.conversation_system.add_message(
                    conversation_id,
                    other_id,
                    response,
                    self.game_state.time,
                )
                
                # 更新记忆
                actor_state.add_memory(
                    self.game_state.time.day,
                    self.game_state.time.period.value,
                    f"与玩家交谈: {content[:50]}...",
                    actor_state.location,
                    ["player"],
                )
        
        return {
            "conversation": conv.to_dict(),
        }

    def end_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """结束对话"""
        success = self.conversation_system.end_conversation(conversation_id)
        return {"success": success}

    def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """获取对话详情"""
        conv = self.conversation_system.get_conversation(conversation_id)
        if conv:
            return conv.to_dict()
        return {"error": "对话不存在"}

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """获取玩家的对话历史"""
        return self.conversation_system.get_conversation_history("player")

    # ============================================================
    # 时间和 NPC 系统
    # ============================================================

    def _advance_time(self) -> None:
        """推进时间"""
        is_new_day = self.time_system.advance_time(self.game_state)
        
        if is_new_day:
            self.current_turn_events.append(GameEvent(
                event_type=EventType.NARRATIVE,
                text=f"新的一天开始了... 第{self.game_state.time.day}天",
                day=self.game_state.time.day,
                time=self.game_state.time.period.value,
            ))

    async def _execute_npc_turns(self) -> None:
        """执行所有 NPC 的回合"""
        for actor_id, actor_state in self.actor_states.items():
            if not actor_state.is_alive:
                continue
            
            actor_config = self.actor_configs.get(actor_id)
            if not actor_config:
                continue
            
            # 检查特殊行动计划（凶手）
            if actor_config.action_plan:
                special_event = self._check_special_action(actor_id, actor_config)
                if special_event:
                    self.current_turn_events.append(special_event)
                    continue
            
            # 正常 NPC 决策
            await self._execute_single_npc_turn(actor_id, actor_config, actor_state)

    def _check_special_action(
        self, 
        actor_id: str, 
        config: ActorConfig
    ) -> Optional[GameEvent]:
        """检查凶手的特殊行动"""
        current_time = self.game_state.time
        
        for plan in config.action_plan:
            if plan.trigger_day == current_time.day and plan.trigger_time == current_time.period.value:
                # 检查条件
                if plan.condition and not self.game_state.has_flag(plan.condition):
                    continue
                
                if plan.action == "kill" and plan.target:
                    victim_state = self.actor_states.get(plan.target)
                    if victim_state and victim_state.is_alive:
                        victim_state.is_alive = False
                        self.game_state.set_flag(f"{plan.target}_dead", True)
                        
                        # 设置线索可发现
                        if plan.clue_left:
                            self.game_state.set_flag(f"clue_available_{plan.clue_left}", True)
                        
                        return GameEvent(
                            event_type=EventType.CRIME,
                            text=f"[隐藏] {config.name} 对 {plan.target} 采取了行动",
                            day=current_time.day,
                            time=current_time.period.value,
                            actor=actor_id,
                            location=plan.location,
                            metadata={"victim": plan.target, "method": plan.method},
                        )
        
        return None

    async def _execute_single_npc_turn(
        self,
        actor_id: str,
        config: ActorConfig,
        state: ActorState,
    ) -> None:
        """执行单个 NPC 的回合"""
        # 获取场景信息
        scene_desc = self.scene_system.get_scene_description(state.location)
        people_at_location = [
            a for a in self.scene_system.get_scene_occupants(state.location)
            if a != actor_id
        ]
        
        # 如果玩家在同一地点
        if self.game_state.player.location == state.location:
            people_at_location.append("player")
        
        # 收集观察
        observations = self.actor_brain.gather_observations(
            config,
            state,
            self.game_state,
            scene_desc,
            people_at_location,
            self.current_turn_events,
        )
        
        # 获取可前往的地点
        available_locations = self.scene_system.get_accessible_scenes(self.game_state)
        
        # 决策
        decision = await self.actor_brain.decide_action(
            config, state, observations, available_locations
        )
        
        # 执行决策
        if decision.action == NPCAction.MOVE and decision.target:
            old_loc = state.location
            state.location = decision.target
            self.scene_system.move_actor_to_scene(actor_id, old_loc, decision.target)
            
            # 如果玩家在同一地点，显示 NPC 离开的消息
            if self.game_state.player.location == old_loc:
                self.current_turn_events.append(GameEvent(
                    event_type=EventType.NPC_ACTION,
                    text=f"{config.name} 离开了。",
                    day=self.game_state.time.day,
                    time=self.game_state.time.period.value,
                    actor=actor_id,
                    location=old_loc,
                ))
            
            # 添加记忆
            state.add_memory(
                self.game_state.time.day,
                self.game_state.time.period.value,
                f"前往 {decision.target}：{decision.reason}",
                decision.target,
            )

        elif decision.action == NPCAction.TALK_TO_PLAYER:
            if self.game_state.player.location == state.location:
                self.current_turn_events.append(GameEvent(
                    event_type=EventType.NPC_ACTION,
                    text=f"{config.name} 向你走来，似乎想说些什么...",
                    day=self.game_state.time.day,
                    time=self.game_state.time.period.value,
                    actor=actor_id,
                    location=state.location,
                ))

    # ============================================================
    # 辅助方法
    # ============================================================

    def get_all_actors_info(self) -> List[Dict[str, Any]]:
        """获取所有 NPC 信息（调试用）"""
        result = []
        for actor_id, config in self.actor_configs.items():
            state = self.actor_states.get(actor_id)
            result.append({
                "id": actor_id,
                "name": config.name,
                "role": config.role.value,
                "location": state.location if state else "unknown",
                "is_alive": state.is_alive if state else False,
            })
        return result

    def is_game_over(self) -> bool:
        """检查游戏是否结束"""
        return self.time_system.is_game_over(self.game_state)

