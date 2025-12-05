"""AI modules for the detective game."""

from .llm_client import LLMClient, OpenRouterClient, get_llm_client
from .actor_brain import ActorBrain, NPCAction

__all__ = [
    "LLMClient",
    "OpenRouterClient",
    "get_llm_client",
    "ActorBrain",
    "NPCAction",
]

