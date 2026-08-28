"""Anthropic Claude provider using the official SDK."""
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import anthropic
import tiktoken
from anthropic import AsyncAnthropic

from .base import BaseLLMProvider, LLMError, LLMTimeout, LLMUnavailable

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-5",
        timeout: float = 120.0,
    ):
        self.client = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.encoding = tiktoken.get_encoding("cl100k_base")

    async def aclose(self) -> None:
        await self.client.close()

    def _system(self, system_prompt: Optional[str]):
        # The SDK rejects None for `system`; omit it instead.
        return system_prompt if system_prompt else anthropic.NOT_GIVEN

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> Dict[str, Any]:
        """Non-streaming generation."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=self._system(system_prompt),
                messages=messages,
                **kwargs,
            )
        except anthropic.APITimeoutError as exc:
            raise LLMTimeout("Anthropic request timed out") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailable("Anthropic rejected the API key") from exc
        except anthropic.RateLimitError as exc:
            raise LLMUnavailable("Anthropic rate limit reached") from exc
        except anthropic.APIError as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc

        text = "".join(block.text for block in response.content if block.type == "text")

        return {
            "content": text,
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }

    async def stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Streaming generation."""
        try:
            async with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=self._system(system_prompt),
                messages=messages,
                **kwargs,
            ) as stream:
                async for text in stream.text_stream:
                    yield {"type": "content_delta", "delta": text}

                final = await stream.get_final_message()
                yield {
                    "type": "message_stop",
                    "usage": {
                        "input_tokens": final.usage.input_tokens,
                        "output_tokens": final.usage.output_tokens,
                    },
                }

        except anthropic.APITimeoutError as exc:
            raise LLMTimeout("Anthropic request timed out") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailable("Anthropic rejected the API key") from exc
        except anthropic.RateLimitError as exc:
            raise LLMUnavailable("Anthropic rate limit reached") from exc
        except anthropic.APIError as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc

    async def count_tokens(self, text: str) -> int:
        """Approximate token count. Claude's tokenizer differs from cl100k."""
        return len(self.encoding.encode(text))
