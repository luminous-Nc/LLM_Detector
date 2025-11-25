"""LLM client abstraction for AI-powered responses."""

from __future__ import annotations

import abc
import os
from typing import Any, Optional

# Try imports to handle missing dependencies gracefully
try:
    import google.generativeai as genai
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
        # 解析 prompt 中的角色名
        name = "NPC"
        if "姓名：" in prompt:
            try:
                name = prompt.split("姓名：")[1].split("\n")[0].strip()
            except:
                pass
        
        # 返回简单的模拟回复
        return f"[{name}思考中...]"


class GeminiLLMClient(LLMClient):
    """Client for Google's Gemini models."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        if not genai:
            raise ImportError("Please install `google-generativeai` to use Gemini client.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    async def complete(self, prompt: str, **params: Any) -> str:
        try:
            response = await self.model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            return f"[Gemini Error] {str(e)}"


class OpenRouterClient(LLMClient):
    """Client for OpenRouter (compatible with OpenAI SDK)."""

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
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 512),
            )
            content = response.choices[0].message.content
            return content if content else ""
        except Exception as e:
            return f"[OpenRouter Error] {str(e)}"


def get_llm_client() -> LLMClient:
    """Factory function to create an LLM client based on environment variables."""
    provider = os.getenv("LLM_PROVIDER", "echo").lower()
    
    def get_key(prefix: str) -> str:
        return (
            os.getenv("LLM_API_KEY")
            or os.getenv(f"{prefix.upper()}_API_KEY")
            or os.getenv(f"{prefix.upper()}_KEY")
            or ""
        )

    model_name = os.getenv("LLM_MODEL") or os.getenv(f"{provider.upper()}_MODEL")

    if provider == "gemini":
        api_key = get_key("gemini")
        if not api_key:
            print("Warning: LLM_PROVIDER is gemini but no API key found.")
            return EchoLLMClient()
        name = model_name or "gemini-2.0-flash-exp"
        return GeminiLLMClient(api_key=api_key, model_name=name)

    elif provider == "deepseek" or provider == "openrouter":
        api_key = get_key("deepseek") or get_key("openrouter")
        if not api_key:
            print("Warning: LLM_PROVIDER is deepseek/openrouter but no API key found.")
            return EchoLLMClient()
        name = model_name or "deepseek/deepseek-chat"
        return OpenRouterClient(api_key=api_key, model_name=name)

    elif provider == "echo":
        return EchoLLMClient()

    else:
        print(f"Warning: Unknown LLM_PROVIDER '{provider}', defaulting to Echo.")
        return EchoLLMClient()

