"""
Anthropic Claude provider using official SDK.
"""
from typing import AsyncIterator, List, Dict, Any, Optional
import tiktoken
from anthropic import AsyncAnthropic

from .base import BaseLLMProvider


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        default_max_tokens: int = 4096
    ):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.default_max_tokens = default_max_tokens
        self.encoding = tiktoken.get_encoding("cl100k_base")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """Non-streaming generation."""
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
            **kwargs
        )

        return {
            "content": response.content[0].text if response.content else "",
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }

    async def stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """Streaming generation."""
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
            **kwargs
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    yield {
                        "type": "content_delta",
                        "delta": event.delta.text
                    }
                elif event.type == "message_stop":
                    yield {"type": "message_stop"}

    async def count_tokens(self, text: str) -> int:
        """Token counting using tiktoken."""
        return len(self.encoding.encode(text))
