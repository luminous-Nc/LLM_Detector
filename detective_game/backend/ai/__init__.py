"""AI modules for the detective game."""

from .llm_client import LLMClient, EchoLLMClient, get_llm_client
from .actor_brain import ActorBrain, NPCAction

__all__ = [
    "LLMClient",
    "EchoLLMClient",
    "get_llm_client",
    "ActorBrain",
    "NPCAction",
]

