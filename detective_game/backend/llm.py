"""Abstractions for talking to large language model providers."""

from __future__ import annotations

import abc
import os
from typing import Any, Optional

# Try imports to handle missing dependencies gracefully if not installed yet
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
except ImportError:
    genai = None  # type: ignore

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


class EchoLLMClient(LLMClient):
    """Simple fallback client used when no real LLM is configured."""

    async def complete(self, prompt: str, **params: Any) -> str:
        # Return a mock response based on the last line of the prompt
        lines = prompt.strip().splitlines()
        last_line = lines[-1] if lines else "..."
        return f"[Echo] 收到：{last_line[:20]}..."


class GeminiLLMClient(LLMClient):
    """Client for Google's Gemini models via google-generativeai SDK."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        if not genai:
            raise ImportError("Please install `google-generativeai` to use Gemini client.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    async def complete(self, prompt: str, **params: Any) -> str:
        # Configure safety settings to be permissive for game context if needed
        # For now using defaults, but can be tuned via generation_config
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            return f"[Gemini Error] {str(e)}"


class OpenRouterClient(LLMClient):
    """Client for OpenRouter (compatible with OpenAI SDK), targeting DeepSeek etc."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "deepseek/deepseek-chat",
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        if not AsyncOpenAI:
            raise ImportError("Please install `openai` to use OpenRouter client.")
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model_name = model_name

    async def complete(self, prompt: str, **params: Any) -> str:
        try:
            # DeepSeek and many OpenRouter models are Chat models
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 256),
            )
            content = response.choices[0].message.content
            return content if content else ""
        except Exception as e:
            return f"[OpenRouter Error] {str(e)}"


def get_llm_client() -> LLMClient:
    """Factory function to create an LLM client based on environment variables."""
    provider = os.getenv("LLM_PROVIDER", "echo").lower()
    
    # Allow looking up specific keys if the generic LLM_API_KEY is not set
    # Priority: LLM_API_KEY -> {PROVIDER}_API_KEY -> {PROVIDER}_KEY
    def get_key(prefix: str) -> str:
        return (
            os.getenv("LLM_API_KEY")
            or os.getenv(f"{prefix.upper()}_API_KEY")
            or os.getenv(f"{prefix.upper()}_KEY")
            or ""
        )

    model_name = os.getenv("LLM_MODEL") or os.getenv(f"{provider.upper()}_MODEL") # Optional override

    if provider == "gemini":
        api_key = get_key("gemini")
        if not api_key:
            print("Warning: LLM_PROVIDER is gemini but no valid API key found (LLM_API_KEY or GEMINI_API_KEY/GEMINI_KEY).")
            return EchoLLMClient()
        # Use default if model_name is not set
        name = model_name or "gemini-2.0-flash-exp"
        return GeminiLLMClient(api_key=api_key, model_name=name)

    elif provider == "deepseek" or provider == "openrouter":
        api_key = get_key("deepseek") or get_key("openrouter")
        if not api_key:
            print("Warning: LLM_PROVIDER is deepseek/openrouter but no valid API key found.")
            return EchoLLMClient()
        # Default to deepseek/deepseek-chat (V3) if not specified
        name = model_name or "deepseek/deepseek-chat"
        return OpenRouterClient(api_key=api_key, model_name=name)

    elif provider == "echo":
        return EchoLLMClient()

    else:
        print(f"Warning: Unknown LLM_PROVIDER '{provider}', defaulting to Echo.")
        return EchoLLMClient()
