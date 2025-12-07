"""AI modules for the detective game."""

from .llm_client import LLMClient, OpenRouterClient, get_llm_client

__all__ = [
    "LLMClient",
    "OpenRouterClient",
    "get_llm_client"
]

