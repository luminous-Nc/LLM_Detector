"""鹅鸭杀游戏核心逻辑"""

from __future__ import annotations

import random
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models.identity import Role, RoleType, Team, PlayerIdentity
from .models.event import GameEvent, EventType
from .ai import get_llm_client, ActorBrain


class GamePhase(str, Enum):
    """游戏阶段"""
    LOBBY = "lobby"           # 等待开始
    FREE_ROAM = "free_roam"   # 自由活动
    DISCUSSION = "discussion" # 讨论阶段
    VOTING = "voting"         # 投票阶段
    GAME_OVER = "game_over"   # 游戏结束


@dataclass
class Room:
    """房间"""
    id: str
    name: str
    description: str
    connections: List[str]  # 连接的房间 ID
    tasks: List[str] = field(default_factory=list)
    is_meeting_room: bool = False
    is_dangerous: bool = False
    position: Optional[Tuple[int, int]] = None  # (x, y) for map rendering
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "connections": self.connections,
            "tasks": self.tasks,
            "is_meeting_room": self.is_meeting_room,
            "is_dangerous": self.is_dangerous,
            "position": self.position,
        }


@dataclass
class Player:
    """玩家/NPC 状态"""
    id: str
    name: str
    is_human: bool
    identity: Optional[PlayerIdentity] = None
    location: str = ""
    personality: str = ""
    avatar: str = "👤"
    last_action: str = "idle"
    
    # 游戏状态
    tasks_completed: List[str] = field(default_factory=list)
    tasks_assigned: List[str] = field(default_factory=list)
    emergency_meetings_left: int = 1
    
    # 记忆（NPC 用）
    observations: List[str] = field(default_factory=list)
    
    @property
    def is_alive(self) -> bool:
        return self.identity.is_alive if self.identity else True
    
    def to_dict(self, reveal_role: bool = False) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "name": self.name,
            "is_human": self.is_human,
            "location": self.location,
            "avatar": self.avatar,
            "is_alive": self.is_alive,
            "last_action": self.last_action,
            "tasks_completed": len(self.tasks_completed),
            "tasks_total": len(self.tasks_assigned),
        }
        if self.identity and reveal_role:
            result["role"] = self.identity.role.to_dict()
        return result


@dataclass 
class GameState:
    """游戏状态"""
    phase: GamePhase = GamePhase.LOBBY
    round_number: int = 0
    
    # 讨论相关
    reporter: Optional[str] = None  # 报警/召集会议的人
    body_location: Optional[str] = None  # 尸体位置
    current_speaker_index: int = 0
    discussion_messages: List[Dict[str, Any]] = field(default_factory=list)
    votes: Dict[str, Optional[str]] = field(default_factory=dict)  # voter_id -> target_id
    
    # 胜利状态
    winner: Optional[Team] = None
    winner_reason: str = ""


class GooseDuckGame:
    """鹅鸭杀游戏管理器"""
    
    def __init__(self):
        self.settings_dir = Path(__file__).parent.parent / "settings" / "goose_duck"
        
        # 加载配置
        self.map_config = self._load_yaml("map.yaml")
        self.roles_config = self._load_yaml("roles.yaml")
        self.game_config = self._load_yaml("config.yaml")
        
        # 初始化房间
        self.rooms: Dict[str, Room] = {}
        self._init_rooms()
        
        # 玩家列表
        self.players: Dict[str, Player] = {}
        self.player_order: List[str] = []  # 发言顺序
        
        # 游戏状态
        self.state = GameState()
        
        # 事件日志
        self.events: List[GameEvent] = []
        
        # LLM
        self.llm_client = get_llm_client()
    
    def _load_yaml(self, filename: str) -> Dict:
        """加载 YAML 配置"""
        path = self.settings_dir / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}
    
    def _init_rooms(self) -> None:
        """初始化房间"""
        rooms_data = self.map_config.get("rooms", {})
        for room_id, data in rooms_data.items():
            self.rooms[room_id] = Room(
                id=room_id,
                name=data.get("name", room_id),
                description=data.get("description", ""),
                connections=data.get("connections", []),
                tasks=data.get("tasks", []),
                is_meeting_room=data.get("is_meeting_room", False),
                is_dangerous=data.get("is_dangerous", False),
                position=tuple(data.get("position", [])) if data.get("position") else None,
            )
    
    def _init_players(self) -> None:
        """初始化玩家"""
        spawn_room = self.map_config.get("spawn_room", "cafeteria")
        
        # 人类玩家
        player_config = self.game_config.get("player", {})
        human_player = Player(
            id="player",
            name=player_config.get("name", "玩家"),
            is_human=True,
            location=spawn_room,
            avatar="🎮",
        )
        self.players["player"] = human_player
        self.player_order.append("player")
        
        # NPC
        for npc_data in self.game_config.get("npcs", []):
            npc = Player(
                id=npc_data["id"],
                name=npc_data["name"],
                is_human=False,
                location=spawn_room,
                personality=npc_data.get("personality", ""),
                avatar=npc_data.get("avatar", "👤"),
            )
            self.players[npc.id] = npc
            self.player_order.append(npc.id)
    
    def _assign_roles(self) -> None:
        """分配角色"""
        setup = self.roles_config.get("default_setup", {})
        role_list: List[RoleType] = []
        
        for role_config in setup.get("roles", []):
            role_type = RoleType(role_config["role"])
            count = role_config["count"]
            role_list.extend([role_type] * count)
        
        # 打乱角色
        random.shuffle(role_list)
        
        # 分配给玩家
        player_ids = list(self.players.keys())
        for i, player_id in enumerate(player_ids):
            if i < len(role_list):
                role = Role.from_type(role_list[i])
                self.players[player_id].identity = PlayerIdentity(
                    player_id=player_id,
                    player_name=self.players[player_id].name,
                    role=role,
                )
    
    def start_game(self) -> Dict[str, Any]:
        """开始游戏"""
        self._init_players()
        self._assign_roles()
        
        self.state.phase = GamePhase.FREE_ROAM
        self.state.round_number = 1
        
        # 添加开始事件
        self.events.append(GameEvent(
            event_type=EventType.SYSTEM,
            text="游戏开始！找出隐藏在船员中的鸭子！",
            day=1,
            time="round_1",
        ))
        
        return self.get_game_snapshot()
    
    def get_game_snapshot(self, player_id: str = "player") -> Dict[str, Any]:
        """获取游戏状态快照"""
        player = self.players.get(player_id)
        if not player:
            return {"error": "玩家不存在"}
        
        # 当前房间
        current_room = self.rooms.get(player.location)
        
        # 同房间的人
        players_here = [
            p.to_dict() for p in self.players.values()
            if p.location == player.location and p.id != player_id and p.is_alive
        ]
        
        # 可用动作
        actions = self._get_available_actions(player_id)
        
        # 玩家自己的角色（只有自己能看到）
        my_role = None
        if player.identity:
            my_role = player.identity.role.to_dict()
        
        return {
            "phase": self.state.phase.value,
            "round": self.state.round_number,
            "player": {
                "id": player_id,
                "name": player.name,
                "location": player.location,
                "is_alive": player.is_alive,
                "role": my_role,
                "can_kill": player.identity.can_use_kill() if player.identity else False,
            },
            "current_room": current_room.to_dict() if current_room else None,
            "players_here": players_here,
            "available_actions": actions,
            "events": [e.to_dict() for e in self.events[-10:]],
            "all_players": [
                p.to_dict(reveal_role=False) 
                for p in self.players.values()
            ],
            "alive_count": sum(1 for p in self.players.values() if p.is_alive),
            "dead_count": sum(1 for p in self.players.values() if not p.is_alive),
        }
    
    def _get_available_actions(self, player_id: str) -> List[Dict[str, Any]]:
        """获取玩家可用动作"""
        player = self.players.get(player_id)
        if not player or not player.is_alive:
            return []
        
        actions = []
        current_room = self.rooms.get(player.location)
        
        if self.state.phase == GamePhase.FREE_ROAM:
            # 移动动作
            if current_room:
                for conn_id in current_room.connections:
                    conn_room = self.rooms.get(conn_id)
                    if conn_room:
                        actions.append({
                            "type": "move",
                            "target": conn_id,
                            "label": f"前往 {conn_room.name}",
                        })
            
            # 与同房间的人互动
            for other in self.players.values():
                if other.id != player_id and other.location == player.location and other.is_alive:
                    actions.append({
                        "type": "talk",
                        "target": other.id,
                        "label": f"与 {other.name} 交谈",
                    })
                    
                    # 杀人（如果是鸭子且冷却完成）
                    if player.identity and player.identity.can_use_kill():
                        actions.append({
                            "type": "kill",
                            "target": other.id,
                            "label": f"🔪 击杀 {other.name}",
                        })
            
            # 报警（如果在会议室）
            if current_room and current_room.is_meeting_room:
                if player.emergency_meetings_left > 0:
                    actions.append({
                        "type": "emergency",
                        "target": None,
                        "label": "🚨 召开紧急会议",
                    })
            
            # 报告尸体（如果房间有尸体）
            dead_here = [p for p in self.players.values() 
                        if p.location == player.location and not p.is_alive]
            if dead_here:
                actions.append({
                    "type": "report",
                    "target": dead_here[0].id,
                    "label": f"☠️ 报告 {dead_here[0].name} 的尸体",
                })
        
        elif self.state.phase == GamePhase.VOTING:
            # 投票
            for other in self.players.values():
                if other.is_alive and other.id != player_id:
                    actions.append({
                        "type": "vote",
                        "target": other.id,
                        "label": f"投票给 {other.name}",
                    })
            actions.append({
                "type": "vote",
                "target": "skip",
                "label": "弃票",
            })
        
        return actions
    
    async def execute_action(self, player_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行玩家动作"""
        player = self.players.get(player_id)
        if not player:
            return {"error": "玩家不存在"}
        
        action_type = action.get("type")
        target = action.get("target")
        
        if action_type == "move":
            return await self._do_move(player_id, target)
        elif action_type == "kill":
            return await self._do_kill(player_id, target)
        elif action_type == "report":
            return await self._do_report(player_id, target)
        elif action_type == "emergency":
            return await self._do_emergency(player_id)
        elif action_type == "vote":
            return await self._do_vote(player_id, target)
        elif action_type == "talk":
            # 对话单独处理
            return {"error": "请使用对话 API"}
        
        return {"error": "未知动作"}
    
    async def _do_move(self, player_id: str, room_id: str) -> Dict[str, Any]:
        """移动到另一个房间"""
        player = self.players.get(player_id)
        current_room = self.rooms.get(player.location)
        target_room = self.rooms.get(room_id)
        
        if not target_room:
            return {"error": "目标房间不存在"}
        
        if room_id not in current_room.connections:
            return {"error": "无法到达该房间"}
        
        old_location = player.location
        player.location = room_id
        player.last_action = f"移动到 {target_room.name}"
        
        self.events.append(GameEvent(
            event_type=EventType.PLAYER_ACTION,
            text=f"{player.name} 移动到了 {target_room.name}",
            day=self.state.round_number,
            time=f"round_{self.state.round_number}",
            location=room_id,
        ))
        
        # NPC 也会行动
        await self._npc_actions()
        
        return self.get_game_snapshot(player_id)
    
    async def _do_kill(self, killer_id: str, victim_id: str) -> Dict[str, Any]:
        """杀人"""
        killer = self.players.get(killer_id)
        victim = self.players.get(victim_id)
        trigger_canadian_report = False
        
        if not killer or not victim:
            return {"error": "玩家不存在"}
        
        if not killer.identity or not killer.identity.can_use_kill():
            return {"error": "无法使用杀人能力"}
        
        if killer.location != victim.location:
            return {"error": "目标不在同一房间"}
        
        if victim.identity.is_protected:
            # 被医生保护
            victim.identity.is_protected = False
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=f"有人试图攻击 {victim.name}，但被保护了！",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
        else:
            # 击杀成功
            victim.identity.is_alive = False
            killer.identity.use_kill()
            trigger_canadian_report = False
            killer.last_action = f"击杀了 {victim.name}"
            victim.last_action = f"被 {killer.name} 击杀"
            
            self.events.append(GameEvent(
                event_type=EventType.CRIME,
                text=f"💀 {victim.name} 被发现死在了 {self.rooms[victim.location].name}！",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
                location=victim.location,
            ))

            # 警长误杀鹅会同归于尽
            if (
                killer.identity.role.role_type == RoleType.SHERIFF
                and victim.identity.role.team == Team.GOOD
            ):
                killer.identity.is_alive = False
                self.events.append(GameEvent(
                    event_type=EventType.CRITICAL,
                    text=f"⚖️ {killer.name} 误杀了鹅，与 {victim.name} 同归于尽！",
                    day=self.state.round_number,
                    time=f"round_{self.state.round_number}",
                    location=victim.location,
                ))

            # 加拿大鹅被杀后强制报警（忽略1秒延迟）
            if (
                victim.identity.role.role_type == RoleType.CANADIAN
                and killer.identity.is_alive
            ):
                trigger_canadian_report = True
        
        # 检查胜利条件
        self._check_win_condition()

        if (
            self.state.phase != GamePhase.GAME_OVER
            and trigger_canadian_report
        ):
            return await self._start_discussion(
                reporter_id=killer_id,
                is_emergency=False,
                body_id=victim_id,
            )
        
        return self.get_game_snapshot(killer_id)
    
    async def _do_report(self, reporter_id: str, body_id: str) -> Dict[str, Any]:
        """报告尸体"""
        reporter = self.players.get(reporter_id)
        if reporter:
            reporter.last_action = f"报告了 {body_id} 的尸体"
        return await self._start_discussion(reporter_id, is_emergency=False, body_id=body_id)
    
    async def _do_emergency(self, caller_id: str) -> Dict[str, Any]:
        """召开紧急会议"""
        player = self.players.get(caller_id)
        if player.emergency_meetings_left <= 0:
            return {"error": "没有剩余的紧急会议次数"}
        
        player.emergency_meetings_left -= 1
        player.last_action = "召开紧急会议"
        return await self._start_discussion(caller_id, is_emergency=True)
    
    async def _start_discussion(
        self, 
        reporter_id: str, 
        is_emergency: bool = False,
        body_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """开始讨论阶段"""
        self.state.phase = GamePhase.DISCUSSION
        self.state.reporter = reporter_id
        self.state.discussion_messages = []
        self.state.votes = {}
        self.state.current_speaker_index = 0
        
        reporter = self.players.get(reporter_id)
        
        if is_emergency:
            self.events.append(GameEvent(
                event_type=EventType.CRITICAL,
                text=f"🚨 {reporter.name} 召开了紧急会议！",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
        else:
            body = self.players.get(body_id)
            self.state.body_location = body.location if body else None
            self.events.append(GameEvent(
                event_type=EventType.CRITICAL,
                text=f"☠️ {reporter.name} 发现了 {body.name} 的尸体！",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
        
        # 所有人传送到会议室
        meeting_room = self.map_config.get("emergency_button_room", "cafeteria")
        for player in self.players.values():
            if player.is_alive:
                player.location = meeting_room
        
        return self.get_game_snapshot(reporter_id)
    
    async def _do_vote(self, voter_id: str, target_id: str) -> Dict[str, Any]:
        """投票"""
        if self.state.phase != GamePhase.VOTING:
            return {"error": "当前不是投票阶段"}
        
        self.state.votes[voter_id] = target_id if target_id != "skip" else None
        
        voter = self.players.get(voter_id)
        if target_id and target_id != "skip":
            target = self.players.get(target_id)
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=f"{voter.name} 投票给了 {target.name}",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
            voter.last_action = f"投票给 {target.name}"
        else:
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=f"{voter.name} 选择了弃票",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
            voter.last_action = "弃票"
        
        # 检查是否所有人都投票了
        alive_players = [p for p in self.players.values() if p.is_alive]
        if len(self.state.votes) >= len(alive_players):
            await self._resolve_votes()
        
        return self.get_game_snapshot(voter_id)
    
    async def _resolve_votes(self) -> None:
        """结算投票"""
        # 统计票数
        vote_counts: Dict[str, int] = {}
        for target_id in self.state.votes.values():
            if target_id:
                vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
        
        if not vote_counts:
            # 全部弃票
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text="投票结果：没有人被放逐",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
        else:
            # 找出最高票
            max_votes = max(vote_counts.values())
            top_voted = [pid for pid, cnt in vote_counts.items() if cnt == max_votes]
            
            if len(top_voted) > 1:
                # 平票
                self.events.append(GameEvent(
                    event_type=EventType.SYSTEM,
                    text="投票结果：平票，没有人被放逐",
                    day=self.state.round_number,
                    time=f"round_{self.state.round_number}",
                ))
            else:
                # 放逐
                ejected_id = top_voted[0]
                ejected = self.players.get(ejected_id)
                ejected.identity.is_alive = False
                
                # 显示身份
                role_name = ejected.identity.role.name
                self.events.append(GameEvent(
                    event_type=EventType.CRITICAL,
                    text=f"🗳️ {ejected.name} 被放逐了！他的身份是：{role_name}",
                    day=self.state.round_number,
                    time=f"round_{self.state.round_number}",
                ))
                
                # 检查呆呆鸟胜利
                if ejected.identity.role.role_type == RoleType.DODO:
                    self.state.winner = Team.NEUTRAL
                    self.state.winner_reason = f"呆呆鸟 {ejected.name} 成功被放逐，获得胜利！"
                    self.state.phase = GamePhase.GAME_OVER
                    return
        
        # 检查胜利条件
        self._check_win_condition()
        
        if self.state.phase != GamePhase.GAME_OVER:
            # 回到自由活动
            self.state.phase = GamePhase.FREE_ROAM
            self.state.round_number += 1
    
    def _check_win_condition(self) -> None:
        """检查胜利条件"""
        alive_players = [p for p in self.players.values() if p.is_alive]
        
        good_alive = sum(1 for p in alive_players 
                        if p.identity and p.identity.role.team == Team.GOOD)
        evil_alive = sum(1 for p in alive_players 
                        if p.identity and p.identity.role.team == Team.EVIL)
        
        # 坏人胜利：坏人数 >= 好人数
        if evil_alive >= good_alive and evil_alive > 0:
            self.state.winner = Team.EVIL
            self.state.winner_reason = "鸭子数量达到或超过了好人，鸭子阵营获胜！"
            self.state.phase = GamePhase.GAME_OVER
            return
        
        # 好人胜利：所有坏人被消灭
        if evil_alive == 0:
            self.state.winner = Team.GOOD
            self.state.winner_reason = "所有鸭子都被找出，好人阵营获胜！"
            self.state.phase = GamePhase.GAME_OVER
            return
    
    async def _npc_actions(self) -> None:
        """NPC 行动"""
        for player in self.players.values():
            if player.is_human or not player.is_alive:
                continue
            
            # 简单 AI：随机移动到相邻房间
            current_room = self.rooms.get(player.location)
            if current_room and current_room.connections:
                # 30% 概率移动
                if random.random() < 0.3:
                    new_location = random.choice(current_room.connections)
                    player.location = new_location
    
    def get_discussion_state(self) -> Dict[str, Any]:
        """获取讨论状态"""
        return {
            "phase": self.state.phase.value,
            "reporter": self.state.reporter,
            "messages": self.state.discussion_messages,
            "current_speaker": self.player_order[self.state.current_speaker_index] 
                              if self.state.current_speaker_index < len(self.player_order) else None,
            "votes": {k: v for k, v in self.state.votes.items()},
        }
    
    async def add_discussion_message(
        self, 
        player_id: str, 
        content: str
    ) -> Dict[str, Any]:
        """添加讨论发言"""
        player = self.players.get(player_id)
        if not player:
            return {"error": "玩家不存在"}
        
        self.state.discussion_messages.append({
            "speaker_id": player_id,
            "speaker_name": player.name,
            "content": content,
        })
        
        return self.get_discussion_state()
    
    def start_voting(self) -> Dict[str, Any]:
        """开始投票"""
        self.state.phase = GamePhase.VOTING
        self.state.votes = {}
        
        self.events.append(GameEvent(
            event_type=EventType.SYSTEM,
            text="讨论结束，开始投票！",
            day=self.state.round_number,
            time=f"round_{self.state.round_number}",
        ))
        
        return self.get_game_snapshot()
    
    def get_map_info(self) -> Dict[str, Any]:
        """获取地图信息"""
        rooms_info = {}
        for room_id, room in self.rooms.items():
            players_here = [
                {
                    "id": p.id,
                    "name": p.name,
                    "avatar": p.avatar,
                    "is_alive": p.is_alive,
                    "last_action": p.last_action,
                }
                for p in self.players.values()
                if p.location == room_id
            ]
            rooms_info[room_id] = {
                **room.to_dict(),
                "players": players_here,
            }
        
        return {
            "rooms": rooms_info,
            "spawn_room": self.map_config.get("spawn_room"),
            "meeting_room": self.map_config.get("emergency_button_room"),
        }
    
    def reset(self) -> Dict[str, Any]:
        """重置游戏"""
        self.players = {}
        self.player_order = []
        self.state = GameState()
        self.events = []
        return {"message": "游戏已重置"}
