"""LLM client - 统一通过 OpenRouter 访问所有模型。"""

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
    """统一的 OpenRouter 客户端，支持所有模型。"""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        if not AsyncOpenAI:
            raise ImportError("请安装 openai: pip install openai")
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        self.model_name = model_name
        print(f"[LLM] OpenRouter 初始化: model={model_name}")

    async def complete(self, prompt: str, **params: Any) -> str:
        print(f"[LLM] 调用 API: model={self.model_name}")
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=params.get("temperature", 0.7),
                max_tokens=params.get("max_tokens", 512),
            )
            content = response.choices[0].message.content
            print(f"[LLM] 响应成功, 长度={len(content) if content else 0}")
            return content if content else ""
        except Exception as e:
            print(f"[LLM] API 调用失败: {e}")
            raise RuntimeError(f"OpenRouter API 调用失败: {str(e)}")


def get_llm_client() -> LLMClient:
    """根据环境变量创建 LLM 客户端。
    
    需要设置:
      - API_KEY: OpenRouter API 密钥
      - MODEL: 模型名称 (如 x-ai/grok-3-mini-beta, deepseek/deepseek-chat 等)
    """
    api_key = os.getenv("API_KEY", "")
    model = os.getenv("MODEL", "")
    
    print(f"[LLM] 配置: MODEL={model}, API_KEY={'*' * 8 if api_key else '未设置'}")
    
    if not api_key:
        raise RuntimeError(
            "未配置 API_KEY！请在 .env 文件中设置:\n"
            "  API_KEY=your_openrouter_api_key\n"
            "  MODEL=x-ai/grok-3-mini-beta"
        )
    
    if not model:
        raise RuntimeError(
            "未配置 MODEL！请在 .env 文件中设置:\n"
            "  MODEL=x-ai/grok-3-mini-beta\n"
            "常用模型: x-ai/grok-3-mini-beta, deepseek/deepseek-chat, google/gemini-2.0-flash-exp"
        )
    
    return OpenRouterClient(api_key=api_key, model_name=model)

