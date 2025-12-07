"""Goose Duck Game Core Logic"""

from __future__ import annotations

import random
import re
import json
import yaml
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models.identity import Role, RoleType, Team, PlayerIdentity
from .models.event import GameEvent, EventType
from .ai import get_llm_client
from .ai.prompts.action_prompts import build_decision_prompt
from .ai.prompts.meeting_prompts import build_meeting_prompt
from .ai.prompts.vote_prompts import build_vote_prompt
from .ai.prompts.chat_prompts import build_chat_prompt


class GamePhase(str, Enum):
    """Game Phase"""
    LOBBY = "lobby"           # Waiting to start
    FREE_ROAM = "free_roam"   # Free roam
    DISCUSSION = "discussion" # Discussion phase
    VOTING = "voting"         # Voting phase
    GAME_OVER = "game_over"   # Game over


@dataclass
class Room:
    """Room"""
    id: str
    name: str
    description: str
    connections: List[str]  # Connected room IDs
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
    """Player/NPC State"""
    id: str
    name: str
    is_human: bool
    identity: Optional[PlayerIdentity] = None
    location: str = ""
    personality: str = ""
    avatar: str = "👤"
    last_action: str = "idle"
    memories: List[str] = field(default_factory=list)
    has_acted: bool = False
    last_prompt: Optional[str] = None  # Most recent action/meeting/vote/chat prompt
    last_response: Optional[str] = None
    last_prompts: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "action": None,
        "chat": None,
        "meeting": None,
        "vote": None,
    })
    last_responses: Dict[str, Optional[str]] = field(default_factory=lambda: {
        "action": None,
        "chat": None,
        "meeting": None,
        "vote": None,
    })
    tasks_progress: Dict[str, int] = field(default_factory=dict)
    
    # Game state
    tasks_completed: List[str] = field(default_factory=list)
    tasks_assigned: List[str] = field(default_factory=list)
    emergency_meetings_left: int = 1
    
    # Memories (for NPCs)
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
    """Game State"""
    phase: GamePhase = GamePhase.LOBBY
    round_number: int = 0
    # Conversation
    conversation_active: bool = False
    conversation_participants: List[str] = field(default_factory=list)
    conversation_messages: List[Dict[str, Any]] = field(default_factory=list)
    conversation_room: Optional[str] = None
    
    # Discussion related
    reporter: Optional[str] = None  # Person who reported/called meeting
    body_location: Optional[str] = None  # Body location
    current_speaker_index: int = 0
    speaker_order: List[str] = field(default_factory=list)
    discussion_messages: List[Dict[str, Any]] = field(default_factory=list)
    votes: Dict[str, Optional[str]] = field(default_factory=dict)  # voter_id -> target_id
    
    # Victory state
    winner: Optional[Team] = None
    winner_reason: str = ""


class GooseDuckGame:
    """Goose Duck Game Manager"""
    
    def __init__(self):
        self.settings_dir = Path(__file__).parent.parent / "settings" / "goose_duck"
        
        # Load configuration
        self.map_config = self._load_yaml("map.yaml")
        self.roles_config = self._load_yaml("roles.yaml")
        self.game_config = self._load_yaml("config.yaml")
        
        # Initialize rooms
        self.rooms: Dict[str, Room] = {}
        self.task_locations: Dict[str, str] = {}
        self._init_rooms()
        
        # Player list
        self.players: Dict[str, Player] = {}
        self.player_order: List[str] = []  # Speaking order
        
        # Game state
        self.state = GameState()
        
        # Event log
        self.events: List[GameEvent] = []
        
        # LLM
        self.llm_client = get_llm_client()
        self._debug("Game initialized")
    
    def _load_yaml(self, filename: str) -> Dict:
        """Load YAML configuration"""
        path = self.settings_dir / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}
    
    def _init_rooms(self) -> None:
        """Initialize rooms"""
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
            for task in data.get("tasks", []):
                self.task_locations[task] = room_id
    
    def _init_players(self) -> None:
        """Initialize players"""
        spawn_room = self.map_config.get("spawn_room", "cafeteria")
        all_tasks = []
        for room in self.map_config.get("rooms", {}).values():
            all_tasks.extend(room.get("tasks", []))
        
        # Human player
        player_config = self.game_config.get("player", {})
        human_player = Player(
            id="player",
            name=player_config.get("name", "Player"),
            is_human=True,
            location=spawn_room,
            avatar="🎮",
            tasks_assigned=list(all_tasks),
            tasks_progress={t: 0 for t in all_tasks},
        )
        self.players["player"] = human_player
        self.player_order.append("player")
        
        # NPCs
        for npc_data in self.game_config.get("npcs", []):
            npc = Player(
                id=npc_data["id"],
                name=npc_data["name"],
                is_human=False,
                location=spawn_room,
                personality=npc_data.get("personality", ""),
                avatar=npc_data.get("avatar", "👤"),
                tasks_assigned=list(all_tasks),
                tasks_progress={t: 0 for t in all_tasks},
            )
            self.players[npc.id] = npc
            self.player_order.append(npc.id)
        
        # Randomize turn order, player goes first
        import random
        self.turn_order = list(self.player_order)
        random.shuffle(self.turn_order)
        if "player" in self.turn_order:
            self.turn_order.remove("player")
            self.turn_order.insert(0, "player")
        self.turn_index = 0
    
    def _assign_roles(self) -> None:
        """Assign roles"""
        setup = self.roles_config.get("default_setup", {})
        role_list: List[RoleType] = []
        
        for role_config in setup.get("roles", []):
            role_type = RoleType(role_config["role"])
            count = role_config["count"]
            role_list.extend([role_type] * count)
        
        # Shuffle roles
        random.shuffle(role_list)
        
        # Assign to players
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
        """Start game"""
        self._init_players()
        self._assign_roles()
        
        self.state.phase = GamePhase.FREE_ROAM
        self.state.round_number = 1
        self._reset_turn_flags()
        self._debug("Game started -> FREE_ROAM")
        
        # Add start event
        self.events.append(GameEvent(
            event_type=EventType.SYSTEM,
            text="Game started! Find the ducks hidden among the crew!",
            day=1,
            time="round_1",
        ))
        
        return self.get_game_snapshot()
    
    def get_game_snapshot(self, player_id: str = "player") -> Dict[str, Any]:
        """Get game state snapshot"""
        player = self.players.get(player_id)
        if not player:
            return {"error": "Player does not exist"}
        
        # Current room
        current_room = self.rooms.get(player.location)
        
        # People in the same room
        players_here = [
            p.to_dict() for p in self.players.values()
            if p.location == player.location and p.id != player_id and p.is_alive
        ]
        
        # Available actions
        actions = self._get_available_actions(player_id)
        
        # Player's own role (only visible to themselves)
        my_role = None
        if player.identity:
            my_role = player.identity.role.to_dict()
        
        # Event visibility: only see current location or unlocated events
        visible_events = self._get_visible_events(player.id, player.location)
        known_deaths = self._extract_known_deaths(visible_events)

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
                "tasks": [
                    {
                        "name": t,
                        "progress": player.tasks_progress.get(t, 0),
                        "required": 2,
                        "location": (room_id := self.task_locations.get(t)),
                        "location_name": self.rooms[room_id].name if room_id in self.rooms else None,
                    }
                    for t in player.tasks_assigned
                ],
            },
            "current_room": current_room.to_dict() if current_room else None,
            "players_here": players_here,
            "available_actions": actions,
            "events": [e.to_dict() for e in visible_events[-10:]],
            "all_players": [
                p.to_dict(reveal_role=False) 
                for p in self.players.values()
            ],
            "known_deaths": known_deaths,
            "conversation_active": self.state.conversation_active,
            "alive_count": sum(1 for p in self.players.values() if p.is_alive),
            "dead_count": sum(1 for p in self.players.values() if not p.is_alive),
        }
    
    def _get_available_actions(self, player_id: str) -> List[Dict[str, Any]]:
        """Get player available actions"""
        player = self.players.get(player_id)
        if not player or not player.is_alive:
            return []
        
        actions = []
        current_room = self.rooms.get(player.location)
        
        if self.state.phase == GamePhase.FREE_ROAM:
            # Move actions
            if current_room:
                for conn_id in current_room.connections:
                    conn_room = self.rooms.get(conn_id)
                    if conn_room:
                        actions.append({
                            "type": "move",
                            "target": conn_id,
                            "label": f"Go to {conn_room.name}",
                        })
            
            # Interact with people in same room
            for other in self.players.values():
                if other.id != player_id and other.location == player.location and other.is_alive:
                    actions.append({
                        "type": "talk",
                        "target": other.id,
                        "label": f"Talk with {other.name}",
                    })
                    
                    # Kill (if duck and cooldown complete)
                    if player.identity and player.identity.can_use_kill():
                        actions.append({
                            "type": "kill",
                            "target": other.id,
                            "label": f"🔪 Kill {other.name}",
                        })
            
            # Emergency meeting (if in meeting room)
            if current_room and current_room.is_meeting_room:
                if player.emergency_meetings_left > 0:
                    actions.append({
                        "type": "emergency",
                        "target": None,
                        "label": "🚨 Call Emergency Meeting",
                    })
            
            # Report body (if room has body)
            dead_here = [p for p in self.players.values() 
                        if p.location == player.location and not p.is_alive]
            if dead_here:
                actions.append({
                    "type": "report",
                    "target": dead_here[0].id,
                    "label": f"☠️ Report {dead_here[0].name}'s body",
                })
            
            # Do tasks
            if current_room:
                for task in current_room.tasks:
                    progress = player.tasks_progress.get(task, 0)
                    if progress < 2:
                        label_progress = "Not started" if progress == 0 else "In progress (1/2)"
                        actions.append({
                            "type": "task",
                            "target": task,
                            "label": f"🛠️ {task} - {label_progress}",
                        })
        
        elif self.state.phase == GamePhase.VOTING:
            # Voting
            for other in self.players.values():
                if other.is_alive and other.id != player_id:
                    actions.append({
                        "type": "vote",
                        "target": other.id,
                        "label": f"Vote for {other.name}",
                    })
            actions.append({
                "type": "vote",
                "target": "skip",
                "label": "Skip vote",
            })
        
        return actions
    
    async def execute_action(self, player_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute player action"""
        player = self.players.get(player_id)
        if not player:
            return {"error": "Player does not exist"}
        
        action_type = action.get("type")
        target = action.get("target")
        self._debug(f"Player {player_id} action={action_type} target={target}, phase={self.state.phase}")

        if self.state.conversation_active and action_type != "talk":
            return {"error": "Currently in conversation, cannot perform other actions"}
        
        if action_type == "move":
            result = await self._do_move(player_id, target)
        elif action_type == "kill":
            result = await self._do_kill(player_id, target)
        elif action_type == "report":
            result = await self._do_report(player_id, target)
        elif action_type == "emergency":
            result = await self._do_emergency(player_id)
        elif action_type == "vote":
            result = await self._do_vote(player_id, target)
        elif action_type == "task":
            result = await self._do_task(player_id, target)
        elif action_type == "talk":
            result = await self._do_talk(player_id, target, auto=False)
        else:
            result = {"error": "Unknown action"}

        if result.get("error"):
            return result

        if action_type == "talk":
            # Conversation will pause action loop, return directly
            return result

        # Mark player as acted, advance NPC actions
        player.has_acted = True
        await self._process_turns()
        return self.get_game_snapshot(player_id)
    
    async def _do_move(self, player_id: str, room_id: str) -> Dict[str, Any]:
        """Move to another room"""
        player = self.players.get(player_id)
        current_room = self.rooms.get(player.location)
        target_room = self.rooms.get(room_id)
        
        if not target_room:
            return {"error": "Target room does not exist"}
        
        if room_id not in current_room.connections:
            return {"error": "Cannot reach this room"}
        
        old_location = player.location
        player.location = room_id
        player.last_action = f"Moved to {target_room.name}"
        
        # Leave old room event (only visible in old room)
        self.events.append(GameEvent(
            event_type=EventType.PLAYER_ACTION,
            text=f"{player.name} left the room",
            day=self.state.round_number,
            time=f"round_{self.state.round_number}",
            location=old_location,
        ))
        self.events.append(GameEvent(
            event_type=EventType.PLAYER_ACTION,
            text=f"{player.name} moved to {target_room.name}",
            day=self.state.round_number,
            time=f"round_{self.state.round_number}",
            location=room_id,
        ))
        self._record_memory_for_room(room_id, f"{player.name} arrived at {target_room.name}")
        self._debug(f"{player.name} moved {old_location}->{room_id}")
        
        return {"ok": True}
    
    async def _do_kill(self, killer_id: str, victim_id: str) -> Dict[str, Any]:
        """Kill"""
        killer = self.players.get(killer_id)
        victim = self.players.get(victim_id)
        trigger_canadian_report = False
        
        if not killer or not victim:
            return {"error": "Player does not exist"}
        
        if not killer.identity or not killer.identity.can_use_kill():
            return {"error": "Cannot use kill ability"}
        
        if killer.location != victim.location:
            return {"error": "Target is not in the same room"}
        
        if victim.identity.is_protected:
            # Protected by doctor
            victim.identity.is_protected = False
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=f"Someone tried to attack {victim.name}, but they were protected!",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
        else:
            # Kill successful
            victim.identity.is_alive = False
            killer.identity.use_kill()
            trigger_canadian_report = False
            killer.last_action = f"Killed {victim.name}"
            victim.last_action = f"Killed by {killer.name}"
            
            self.events.append(GameEvent(
                event_type=EventType.CRIME,
                text=f"💀 {victim.name} was found dead in {self.rooms[victim.location].name}!",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
                location=victim.location,
            ))
            self._record_memory_for_room(victim.location, f"{victim.name} was killed by {killer.name}")

            # Sheriff killing a goose causes mutual destruction
            if (
                killer.identity.role.role_type == RoleType.SHERIFF
                and victim.identity.role.team == Team.GOOD
            ):
                killer.identity.is_alive = False
                self.events.append(GameEvent(
                    event_type=EventType.CRITICAL,
                    text=f"⚖️ {killer.name} mistakenly killed a goose and died together with {victim.name}!",
                    day=self.state.round_number,
                    time=f"round_{self.state.round_number}",
                    location=victim.location,
                ))

            # Canadian goose forces report when killed (ignore 1 second delay)
            if (
                victim.identity.role.role_type == RoleType.CANADIAN
                and killer.identity.is_alive
            ):
                trigger_canadian_report = True
        
        # Check win condition
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
        
        return {"ok": True}
    
    async def _do_report(self, reporter_id: str, body_id: str) -> Dict[str, Any]:
        """Report body"""
        reporter = self.players.get(reporter_id)
        if reporter:
            reporter.last_action = f"Reported {body_id}'s body"
        return await self._start_discussion(reporter_id, is_emergency=False, body_id=body_id)
    
    async def _do_emergency(self, caller_id: str) -> Dict[str, Any]:
        """Call emergency meeting"""
        player = self.players.get(caller_id)
        if player.emergency_meetings_left <= 0:
            return {"error": "No emergency meetings left"}
        
        player.emergency_meetings_left -= 1
        player.last_action = "Called emergency meeting"
        return await self._start_discussion(caller_id, is_emergency=True)
    
    async def _start_discussion(
        self, 
        reporter_id: str, 
        is_emergency: bool = False,
        body_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start discussion phase"""
        self.state.phase = GamePhase.DISCUSSION
        self.state.reporter = reporter_id
        self.state.discussion_messages = []
        self.state.votes = {}
        self.state.current_speaker_index = 0
        # Speaking order: reporter first, then cycle through turn order
        alive_ids = [pid for pid in self.turn_order if (p := self.players.get(pid)) and p.is_alive]
        if reporter_id in alive_ids:
            start = alive_ids.index(reporter_id)
            self.state.speaker_order = alive_ids[start:] + alive_ids[:start]
        else:
            self.state.speaker_order = alive_ids
        self._debug(f"Enter DISCUSSION, speaker order={self.state.speaker_order}")
        
        reporter = self.players.get(reporter_id)
        
        if is_emergency:
            self.events.append(GameEvent(
                event_type=EventType.CRITICAL,
                text=f"🚨 {reporter.name} called an emergency meeting!",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
            self._record_memory_for_all(f"{reporter.name} called an emergency meeting")
        else:
            body = self.players.get(body_id)
            self.state.body_location = body.location if body else None
            self.events.append(GameEvent(
                event_type=EventType.CRITICAL,
                text=f"☠️ {reporter.name} found {body.name}'s body!",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
            self._record_memory_for_all(f"{reporter.name} reported {body.name}'s body")
        
        # Teleport everyone to meeting room
        meeting_room = self.map_config.get("emergency_button_room", "cafeteria")
        for player in self.players.values():
            if player.is_alive:
                player.location = meeting_room

        # Let current speaker (if NPC) speak first until player's turn or end
        await self.advance_discussion()
        return self.get_game_snapshot(reporter_id)
    
    async def _do_vote(self, voter_id: str, target_id: str) -> Dict[str, Any]:
        """Vote"""
        if self.state.phase != GamePhase.VOTING:
            return {"error": "Not currently in voting phase"}
        
        self.state.votes[voter_id] = target_id if target_id != "skip" else None
        
        voter = self.players.get(voter_id)
        if target_id and target_id != "skip":
            target = self.players.get(target_id)
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=f"{voter.name} voted for {target.name}",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
            voter.last_action = f"Voted for {target.name}"
            self._record_memory_for_all(f"{voter.name} voted for {target.name}")
            self._debug(f"{voter.name} voted for {target.name}")
        else:
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text=f"{voter.name} chose to skip vote",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
            voter.last_action = "Skipped vote"
            self._record_memory_for_all(f"{voter.name} chose to skip vote")
            self._debug(f"{voter.name} skipped vote")
        
        # Check if everyone has voted
        alive_players = [p for p in self.players.values() if p.is_alive]
        if len(self.state.votes) >= len(alive_players):
            await self._resolve_votes()
            self._debug("All votes collected, resolving")
        
        return {"ok": True}
    
    async def _resolve_votes(self) -> None:
        """Resolve votes"""
        # Count votes
        vote_counts: Dict[str, int] = {}
        for target_id in self.state.votes.values():
            if target_id:
                vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
        
        if not vote_counts:
            # All skipped
            self.events.append(GameEvent(
                event_type=EventType.SYSTEM,
                text="Voting result: No one was ejected",
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
            ))
        else:
            # Find highest votes
            max_votes = max(vote_counts.values())
            top_voted = [pid for pid, cnt in vote_counts.items() if cnt == max_votes]
            
            if len(top_voted) > 1:
                # Tie
                self.events.append(GameEvent(
                    event_type=EventType.SYSTEM,
                    text="Voting result: Tie, no one was ejected",
                    day=self.state.round_number,
                    time=f"round_{self.state.round_number}",
                ))
            else:
                # Eject
                ejected_id = top_voted[0]
                ejected = self.players.get(ejected_id)
                ejected.identity.is_alive = False
                
                # Show identity
                role_name = ejected.identity.role.name
                self.events.append(GameEvent(
                    event_type=EventType.CRITICAL,
                    text=f"🗳️ {ejected.name} was ejected! Their identity is: {role_name}",
                    day=self.state.round_number,
                    time=f"round_{self.state.round_number}",
                ))
                
                # Check dodo victory
                if ejected.identity.role.role_type == RoleType.DODO:
                    self.state.winner = Team.NEUTRAL
                    self.state.winner_reason = f"Dodo {ejected.name} was successfully ejected and wins!"
                    self.state.phase = GamePhase.GAME_OVER
                    return
        
        # Check win condition
        self._check_win_condition()
        
        if self.state.phase != GamePhase.GAME_OVER:
            # Return to free roam
            self.state.phase = GamePhase.FREE_ROAM
            self.state.round_number += 1
            self._reset_turn_flags()
    
    def _check_win_condition(self) -> None:
        """Check win condition"""
        alive_players = [p for p in self.players.values() if p.is_alive]
        
        good_alive = sum(1 for p in alive_players 
                        if p.identity and p.identity.role.team == Team.GOOD)
        evil_alive = sum(1 for p in alive_players 
                        if p.identity and p.identity.role.team == Team.EVIL)
        
        # Evil victory: evil count >= good count
        if evil_alive >= good_alive and evil_alive > 0:
            self.state.winner = Team.EVIL
            self.state.winner_reason = "Duck count reached or exceeded good players, duck team wins!"
            self.state.phase = GamePhase.GAME_OVER
            return
        
        # Good victory: all evil eliminated
        if evil_alive == 0:
            self.state.winner = Team.GOOD
            self.state.winner_reason = "All ducks have been found, good team wins!"
            self.state.phase = GamePhase.GAME_OVER
            return
    
    async def _npc_actions(self) -> None:
        """Deprecated"""
        return

    async def _decide_npc_action(self, npc: Player) -> Dict[str, Any]:
        """Call LLM to decide NPC action"""
        
        obs = self._build_observation(npc)
        prompt = self._build_decision_prompt(npc, obs)
        response = await self.llm_client.complete(prompt, max_tokens=256)
        npc.last_prompt = prompt
        npc.last_response = response
        npc.last_prompts["action"] = prompt
        npc.last_responses["action"] = response
        action = self._parse_decision_response(response, obs)
        return action
 

    def _build_observation(self, npc: Player) -> Dict[str, Any]:
        current_room = self.rooms.get(npc.location)
        connections = current_room.connections if current_room else []
        people_here = [
            {"id": p.id, "name": p.name, "is_alive": p.is_alive}
            for p in self.players.values()
            if p.location == npc.location
        ]
        available = self._get_available_actions(npc.id)
        tasks_info = []
        for task, prog in npc.tasks_progress.items():
            room_id = self.task_locations.get(task)
            room_name = self.rooms.get(room_id).name if room_id in self.rooms else room_id
            tasks_info.append(
                {
                    "name": task,
                    "progress": prog,
                    "room_id": room_id,
                    "room_name": room_name,
                }
            )
        return {
            "phase": self.state.phase.value,
            "round": self.state.round_number,
            "room": current_room,
            "connections": connections,
            "people_here": people_here,
            "available_actions": available,
            "memories": npc.memories[-8:],
            "role": npc.identity.role if npc.identity else None,
            "tasks_progress": npc.tasks_progress,
            "tasks_info": tasks_info,
        }

    def _build_decision_prompt(self, npc: Player, obs: Dict[str, Any]) -> str:
        role = obs["role"]
        role_hint = ""
        if role:
            role_hint = self.roles_config.get("roles", {}).get(role.role_type.value, {}).get("prompt_hint", "").strip()
        win_text = self._get_role_win_text(role)
        return build_decision_prompt(npc.name, obs, role_hint, win_text)

    def _parse_decision_response(self, text: str, obs: Dict[str, Any]) -> Dict[str, Any]:
        try:
            import json
            data = json.loads(text.strip())
            action = data.get("action", "wait")
            target = data.get("target")
        except Exception:
            return {"action": "wait", "target": None}

        valid_actions = {a["type"]: a for a in obs["available_actions"]}
        if action not in valid_actions:
            return {"action": "wait", "target": None}
        if action == "move" and target not in obs["connections"]:
            return {"action": "wait", "target": None}
        if action in ("kill", "vote") and target and target not in [p["id"] for p in obs["people_here"]]:
            return {"action": "wait", "target": None}
        return {"action": action, "target": target}

    def _build_meeting_prompt(self, npc: Player) -> str:
        role = npc.identity.role if npc.identity else None
        role_info = f"{role.name} (Team: {role.team.value})" if role else "Unknown"
        team_goals = {
            "good": "Complete tasks or eliminate evil players.",
            "evil": "Hide identity and make evil count exceed good count.",
            "neutral": "Meet your special win condition.",
        }
        goal = team_goals.get(role.team.value, "") if role else ""
        abilities = ", ".join(role.abilities) if role and role.abilities else "None"
        win_text = self._get_role_win_text(role)
        memories = "\n".join(npc.memories[-8:]) if npc.memories else "None"
        msg_history = "\n".join(
            f"- {m.get('speaker_name')}: {m.get('content')}"
            for m in self.state.discussion_messages[-10:]
        )
        return build_meeting_prompt(npc.name, role_info, goal, abilities, win_text, memories, msg_history)

    async def _apply_npc_decision(self, npc: Player, decision: Dict[str, Any]) -> None:
        action = decision.get("action")
        target = decision.get("target")
        npc.has_acted = True
        self._debug(f"NPC {npc.name} acts: {action} -> {target}")
        if action == "move" and target:
            await self._do_move(npc.id, target)
        elif action == "kill" and target:
            await self._do_kill(npc.id, target)
        elif action == "report" and target:
            await self._do_report(npc.id, target)
        elif action == "emergency":
            await self._do_emergency(npc.id)
        elif action == "vote" and target:
            await self._do_vote(npc.id, target)
        elif action == "talk" and target:
            await self._do_talk(npc.id, target, auto=True)
        else:
            npc.last_action = "Waiting"

    async def _process_turns(self) -> None:
        """Let NPCs act in order, one action per round"""
        while True:
            # Immediately stop NPC actions when phase changes (e.g., discussion/voting), wait for frontend
            if self.state.phase != GamePhase.FREE_ROAM:
                self._debug("Stop turn processing, phase changed")
                return
            if self.state.conversation_active:
                self._debug("Stop turn processing, conversation active")
                return
            pending = [
                pid for pid in self.turn_order
                if (p := self.players.get(pid)) and p.is_alive and not p.has_acted
            ]
            if not pending:
                if self.state.phase != GamePhase.FREE_ROAM:
                    return
                self._start_new_round()
                # New round, player acts first
                return
            # Find next unacted from turn_order
            length = len(self.turn_order)
            for _ in range(length):
                self.turn_index = (self.turn_index + 1) % length
                candidate_id = self.turn_order[self.turn_index]
                cand = self.players.get(candidate_id)
                if cand and cand.is_alive and not cand.has_acted:
                    next_id = candidate_id
                    break
            else:
                return
            next_player = self.players.get(next_id)
            if next_player.is_human:
                return  # Wait for player action
            # NPC action
            decision = await self._decide_npc_action(next_player)
            await self._apply_npc_decision(next_player, decision)
            # Loop continues until next unacted human or all have acted

    def _start_new_round(self) -> None:
        self.state.round_number += 1
        self.turn_index = 0
        self._reset_turn_flags()
        self._debug(f"Start new round {self.state.round_number}")

    def _reset_turn_flags(self) -> None:
        for p in self.players.values():
            p.has_acted = False
    
    def get_discussion_state(self) -> Dict[str, Any]:
        """Get discussion state"""
        current_id = None
        if self.state.current_speaker_index < len(self.state.speaker_order):
            current_id = self.state.speaker_order[self.state.current_speaker_index]
        return {
            "phase": self.state.phase.value,
            "reporter": self.state.reporter,
            "messages": self.state.discussion_messages,
            "current_speaker": current_id,
            "votes": {k: v for k, v in self.state.votes.items()},
        }
    
    async def add_discussion_message(
        self, 
        player_id: str, 
        content: str
    ) -> Dict[str, Any]:
        """Add discussion message"""
        player = self.players.get(player_id)
        if not player:
            return {"error": "Player does not exist"}
        
        self.state.discussion_messages.append({
            "speaker_id": player_id,
            "speaker_name": player.name,
            "content": content,
        })
        # Advance to next speaker
        await self.advance_discussion()
        return self.get_discussion_state()
    
    def start_voting(self) -> Dict[str, Any]:
        """Start voting"""
        self.state.phase = GamePhase.VOTING
        self.state.votes = {}
        self._debug("Enter VOTING phase")
        self.events.append(GameEvent(
            event_type=EventType.SYSTEM,
            text="Discussion ended, voting begins!",
            day=self.state.round_number,
            time=f"round_{self.state.round_number}",
        ))
        
        return self.get_game_snapshot()
    
    def get_map_info(self) -> Dict[str, Any]:
        """Get map information"""
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
        """Reset game"""
        self.players = {}
        self.player_order = []
        self.state = GameState()
        self.events = []
        self.turn_order: List[str] = []
        self.turn_index: int = 0
        return {"message": "Game has been reset"}

    def _record_memory_for_room(self, room_id: str, text: str) -> None:
        """Record event in memories of players in the same room"""
        for p in self.players.values():
            if p.location == room_id:
                p.memories.append(text)
                if len(p.memories) > 20:
                    p.memories = p.memories[-20:]

    def _record_memory_for_all(self, text: str) -> None:
        """Record in all players' memories (public events like meetings, votes)"""
        for p in self.players.values():
            p.memories.append(text)
            if len(p.memories) > 20:
                p.memories = p.memories[-20:]

    def _get_visible_events(self, player_id: str, location: Optional[str]) -> List[GameEvent]:
        """Filter events by player perspective: current room or unlocated events, and add body discovery info"""
        events = [
            e for e in self.events[-50:]
            if e.location is None or e.location == location
        ]
        if location:
            corpses_here = [
                p for p in self.players.values() if not p.is_alive and p.location == location
            ]
            for corpse in corpses_here:
                events.append(GameEvent(
                    event_type=EventType.CRIME,
                    text=f"☠️ Body found: {corpse.name}",
                    day=self.state.round_number,
                    time=f"round_{self.state.round_number}",
                    location=location,
                ))
        return events

    def _extract_known_deaths(self, events: List[GameEvent]) -> List[Dict[str, Any]]:
        """Extract known death info from visible events (only within player's view)"""
        known = {}
        for ev in events:
            if ev.event_type not in (EventType.CRIME, EventType.CRITICAL):
                continue
            text = ev.text or ""
            name = None
            if "found" in text and "body" in text.lower():
                # e.g., "A found B's body"
                try:
                    part = text.split("found", 1)[1]
                    name = part.split("'s body")[0].split("body:")[-1].strip(" :：!！")
                except Exception:
                    name = None
            if not name and "was found dead in" in text:
                name = text.replace("💀", "").split("was found dead in")[0].strip(" :：!！")
            if not name and "Body found:" in text:
                m = re.search(r"Body found:\s*([^\s!]+)", text)
                if m:
                    name = m.group(1)
            if not name:
                continue
            if name not in known:
                known[name] = {
                    "name": name,
                    "location": ev.location,
                    "location_name": self.rooms.get(ev.location).name if ev.location in self.rooms else None,
                    "text": text,
                }
        return list(known.values())

    def _get_role_win_text(self, role: Optional[Role]) -> str:
        """Return win condition description based on role and config"""
        if not role:
            return ""
        win_cfg = self.roles_config.get("win_conditions", {})
        # Role-specific priority (e.g., dodo)
        if role.role_type == RoleType.DODO:
            return win_cfg.get("neutral", {}).get("dodo", "Win by being voted out in voting phase.")
        team_key = role.team.value if role.team else None
        team_rules = win_cfg.get(team_key) if win_cfg else None
        if isinstance(team_rules, list):
            return "; ".join(team_rules)
        if isinstance(team_rules, str):
            return team_rules
        # fallback
        if role.team.value == "good":
            return "Complete all tasks or eliminate all evil players."
        if role.team.value == "evil":
            return "Evil count reaches or exceeds good count."
        return role.win_condition or "Meet your special win condition."

    async def _start_chat(self, initiator_id: str, target_id: str) -> None:
        """Initialize conversation context"""
        room = self.players.get(initiator_id).location if initiator_id in self.players else None
        self.state.conversation_active = True
        self.state.conversation_participants = [initiator_id, target_id]
        self.state.conversation_messages = []
        self.state.conversation_room = room
        self._debug(f"Conversation start: {initiator_id} <-> {target_id} @ {room}")

    def get_chat_state(self) -> Dict[str, Any]:
        """Get conversation state"""
        if not self.state.conversation_active:
            return {"active": False}
        participants = []
        for pid in self.state.conversation_participants:
            p = self.players.get(pid)
            if p:
                participants.append({
                    "id": p.id,
                    "name": p.name,
                    "is_human": p.is_human,
                    "is_alive": p.is_alive,
                    "avatar": p.avatar,
                })
        target_id = None
        for pid in self.state.conversation_participants:
            if pid != "player":
                target_id = pid
                break
        target = self.players.get(target_id) if target_id else None
        return {
            "active": True,
            "room": self.state.conversation_room,
            "room_name": self.rooms.get(self.state.conversation_room).name if self.state.conversation_room in self.rooms else None,
            "messages": self.state.conversation_messages,
            "participants": participants,
            "target": {
                "id": target.id if target else None,
                "name": target.name if target else None,
                "avatar": target.avatar if target else None,
            } if target else None,
        }

    async def add_chat_message(self, speaker_id: str, content: str, resume_turns: bool = True) -> Dict[str, Any]:
        """Player sends conversation message"""
        if not self.state.conversation_active:
            return {"error": "No active conversation"}
        if speaker_id not in self.state.conversation_participants:
            return {"error": "You are not in this conversation"}
        speaker = self.players.get(speaker_id)
        content = content.strip()
        if not content:
            return {"error": "Content is empty"}
        self.state.conversation_messages.append({
            "speaker_id": speaker_id,
            "speaker_name": speaker.name if speaker else speaker_id,
            "content": content,
            "round": self.state.round_number,
            "room": self.state.conversation_room,
        })
        partner_id = self._other_participant(speaker_id)
        # NPC auto-reply
        partner = self.players.get(partner_id) if partner_id else None
        if partner and not partner.is_human and self.state.conversation_active:
            await self._npc_chat_reply(partner_id, speaker_id, resume_turns=resume_turns)
        return self.get_chat_state()

    async def end_chat(self, reason: str = "") -> Dict[str, Any]:
        if not self.state.conversation_active:
            return {"active": False}
        await self._finalize_chat(reason or "Player ended conversation", resume_turns=True)
        return {"active": False}

    async def _npc_chat_reply(self, npc_id: str, target_id: str, resume_turns: bool = True) -> None:
        """NPC replies in conversation"""
        npc = self.players.get(npc_id)
        target = self.players.get(target_id)
        if not npc or not target:
            return
        role = npc.identity.role if npc.identity else None
        role_hint = ""
        if role:
            role_hint = self.roles_config.get("roles", {}).get(role.role_type.value, {}).get("prompt_hint", "").strip()
        team_goals = {
            "good": "Complete tasks or eliminate evil players.",
            "evil": "Hide identity and make evil count exceed good count.",
            "neutral": "Meet your special win condition.",
        }
        team_goal = team_goals.get(role.team.value, "") if role else ""
        tasks_info = []
        for task, prog in npc.tasks_progress.items():
            room_id = self.task_locations.get(task)
            room_name = self.rooms.get(room_id).name if room_id in self.rooms else room_id
            tasks_info.append(f"{task}@{room_name or 'Unknown'} {prog}/2")
        history = [
            f"{m.get('speaker_name')}: {m.get('content')}"
            for m in self.state.conversation_messages[-10:]
        ]
        prompt = build_chat_prompt(
            npc_name=npc.name,
            partner_name=target.name,
            role_text=f"{role.name} ({role.team.value})" if role else "Unknown",
            team_goal=team_goal,
            role_hint=role_hint,
            abilities_text=", ".join(role.abilities) if role and role.abilities else "None",
            win_text=self._get_role_win_text(role),
            memories=npc.memories[-8:],
            chat_history=history,
            tasks_info=tasks_info,
        )
        response = await self.llm_client.complete(prompt, max_tokens=120)
        npc.last_prompt = prompt
        npc.last_response = response
        npc.last_prompts["chat"] = prompt
        npc.last_responses["chat"] = response
        text = ""
        end_flag = False
        try:
            data = json.loads(response.strip())
            text = data.get("content") or ""
            end_flag = bool(data.get("end"))
        except Exception:
            text = response.strip() or "..."
        self.state.conversation_messages.append({
            "speaker_id": npc.id,
            "speaker_name": npc.name,
            "content": text,
            "round": self.state.round_number,
            "room": self.state.conversation_room,
        })
        if end_flag:
            await self._finalize_chat(f"{npc.name} ended the conversation", resume_turns=resume_turns)

    async def _auto_run_npc_chat(self, initiator_id: str, target_id: str) -> None:
        """NPC to NPC auto conversation until end or turn limit"""
        turns = 0
        speaker = initiator_id
        partner = target_id
        while self.state.conversation_active and turns < 6:
            await self._npc_chat_reply(speaker, partner, resume_turns=False)
            speaker, partner = partner, speaker
            turns += 1
        if self.state.conversation_active:
            await self._finalize_chat("Conversation reached limit, auto-ended", resume_turns=False)

    async def _finalize_chat(self, reason: str = "", resume_turns: bool = True) -> None:
        """End conversation, write to memory and optionally resume action loop"""
        summary = self._chat_summary_text()
        if summary:
            self.events.append(GameEvent(
                event_type=EventType.PLAYER_ACTION,
                text=summary,
                day=self.state.round_number,
                time=f"round_{self.state.round_number}",
                location=self.state.conversation_room,
            ))
            for pid in self.state.conversation_participants:
                player = self.players.get(pid)
                if player:
                    player.memories.append(summary)
                    if len(player.memories) > 20:
                        player.memories = player.memories[-20:]
        self.state.conversation_active = False
        self.state.conversation_participants = []
        self.state.conversation_messages = []
        self.state.conversation_room = None
        if resume_turns:
            await self._process_turns()

    def _chat_summary_text(self) -> Optional[str]:
        """Generate conversation summary"""
        if len(self.state.conversation_participants) < 2:
            return None
        p1 = self.players.get(self.state.conversation_participants[0])
        p2 = self.players.get(self.state.conversation_participants[1])
        if not p1 or not p2:
            return None
        room_name = self.rooms.get(self.state.conversation_room).name if self.state.conversation_room in self.rooms else "Unknown"
        snippet = "; ".join(
            f"{m.get('speaker_name')}: {m.get('content')}"
            for m in self.state.conversation_messages[-6:]
        )
        return f"Round {self.state.round_number}, {p1.name} and {p2.name} conversation in {room_name}: {snippet}"

    def _other_participant(self, speaker_id: str) -> Optional[str]:
        for pid in self.state.conversation_participants:
            if pid != speaker_id:
                return pid
        return None

    def _debug(self, msg: str) -> None:
        """Simple debug output"""
        print(f"[DEBUG][{self.state.phase.value}][round {self.state.round_number}] {msg}")
    
    async def _do_task(self, player_id: str, task: str) -> Dict[str, Any]:
        """Execute task, requires two completions"""
        player = self.players.get(player_id)
        room = self.rooms.get(player.location)
        if not room or task not in room.tasks:
            return {"error": "No such task here"}
        progress = player.tasks_progress.get(task, 0)
        if progress >= 2:
            return {"error": "Task already completed"}
        progress += 1
        player.tasks_progress[task] = progress
        player.last_action = f"Doing task {task} ({progress}/2)"
        if progress >= 2 and task not in player.tasks_completed:
            player.tasks_completed.append(task)
        # Record room memory (same room only)
        self._record_memory_for_room(player.location, f"{player.name} is doing task {task} ({progress}/2)")
        return {"ok": True}

    async def _do_talk(self, speaker_id: str, target_id: str, auto: bool = False) -> Dict[str, Any]:
        """Start conversation, pause action loop"""
        if self.state.conversation_active:
            return {"error": "A conversation is already in progress"}
        speaker = self.players.get(speaker_id)
        target = self.players.get(target_id)
        if not speaker or not target:
            return {"error": "Player does not exist"}
        if not speaker.is_alive or not target.is_alive:
            return {"error": "Target cannot be conversed with"}
        if speaker.location != target.location:
            return {"error": "Must be in the same room to converse"}
        if auto and (speaker.is_human or target.is_human):
            speaker.last_action = "Waiting"
            return {"ok": True}

        await self._start_chat(speaker_id, target_id)
        speaker.has_acted = True
        speaker.last_action = f"Talked with {target.name}"
        if auto:
            await self._auto_run_npc_chat(speaker_id, target_id)
            return {"ok": True}
        return {
            "chat_started": True,
            "target_id": target_id,
            "target_name": target.name,
        }

    async def advance_discussion(self) -> None:
        """Advance discussion speeches, auto NPC speeches, enter voting when done"""
        # If already voting or game over, don't process
        if self.state.phase != GamePhase.DISCUSSION:
            return

        # If current is NPC, auto speak until player's turn or end
        while True:
            if self.state.current_speaker_index >= len(self.state.speaker_order):
                # Speaking ended, start voting
                self.start_voting()
                return

            speaker_id = self.state.speaker_order[self.state.current_speaker_index]
            speaker = self.players.get(speaker_id)
            if not speaker or not speaker.is_alive:
                self.state.current_speaker_index += 1
                continue

            if speaker.is_human:
                # Player's turn, wait for player input
                return

            # NPC speaks
            try:
                prompt = self._build_meeting_prompt(speaker)
                response = await self.llm_client.complete(prompt, max_tokens=120)
                speaker.last_prompt = prompt
                speaker.last_response = response
                speaker.last_prompts["meeting"] = prompt
                speaker.last_responses["meeting"] = response
                self.state.discussion_messages.append({
                    "speaker_id": speaker_id,
                    "speaker_name": speaker.name,
                    "content": response,
                })
                self._debug(f"{speaker.name} speaks")
            except Exception:
                self.state.discussion_messages.append({
                    "speaker_id": speaker_id,
                    "speaker_name": speaker.name,
                    "content": "(silence)",
                })

            self.state.current_speaker_index += 1
            # Continue while loop, may have next NPC to speak
