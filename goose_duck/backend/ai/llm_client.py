"""LLM client - Unified access to all models through OpenRouter."""

from __future__ import annotations

import abc
import os
from typing import Any

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore


class LLMClient(abc.ABC):
    """Abstract base class for LLM clients."""

    @abc.abstractmethod
    async def complete(self, prompt: str, **params: Any) -> str:
        """Generate a completion for the given prompt."""
        pass


class OpenRouterClient(LLMClient):
    """Unified OpenRouter client, supporting all models."""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        if not AsyncOpenAI:
            raise ImportError("Please install openai: pip install openai")
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model_name = model_name
        print(f"[LLM] OpenRouter initialized: model={model_name}")

    async def complete(self, prompt: str, **params: Any) -> str:
        print(f"[LLM] Calling API: model={self.model_name}")
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 512),
            )
            content = response.choices[0].message.content
            print(f"[LLM] Response successful, length={len(content) if content else 0}")
            return content if content else ""
        except Exception as e:
            print(f"[LLM] API call failed: {e}")
            raise RuntimeError(f"OpenRouter API call failed: {str(e)}")


def get_llm_client() -> LLMClient:
    """Create LLM client based on environment variables.
    
    Required settings:
      - API_KEY: OpenRouter API key
      - MODEL: Model name (e.g., x-ai/grok-3-mini-beta, deepseek/deepseek-chat, etc.)
    """
    api_key = os.getenv("API_KEY", "")
    model = os.getenv("MODEL", "")
    
    print(f"[LLM] Config: MODEL={model}, API_KEY={'*' * 8 if api_key else 'Not set'}")
    
    if not api_key:
        raise RuntimeError(
            "API_KEY not configured! Please set in .env file:\n"
            "  API_KEY=your_openrouter_api_key\n"
            "  MODEL=x-ai/grok-3-mini-beta"
        )
    
    if not model:
        raise RuntimeError(
            "MODEL not configured! Please set in .env file:\n"
            "  MODEL=x-ai/grok-3-mini-beta\n"
            "Common models: x-ai/grok-3-mini-beta, deepseek/deepseek-chat, google/gemini-2.0-flash-exp"
        )
    
    return OpenRouterClient(api_key=api_key, model_name=model)

