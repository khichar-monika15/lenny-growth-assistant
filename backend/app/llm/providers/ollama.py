"""
Ollama local LLM provider.

Uses Ollama's /api/chat endpoint so the model's own chat template is applied.
The previous implementation flattened messages into a single "User:/Assistant:"
string against /api/generate, which bypassed the template and degraded
instruction following on chat-tuned models like llama3.1.
"""
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
import tiktoken

from .base import BaseLLMProvider, LLMError, LLMTimeout, LLMUnavailable

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2:3b",
        timeout: int = 180,
        context_window: int = 8192,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.context_window = context_window
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=timeout)
        self.encoding = tiktoken.get_encoding("cl100k_base")

    async def aclose(self) -> None:
        await self.client.aclose()

    def _payload(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        stream: bool,
    ) -> Dict[str, Any]:
        chat_messages: List[Dict[str, str]] = []
        if system_prompt:
            chat_messages.append({"role": "system", "content": system_prompt})
        chat_messages.extend(messages)

        return {
            "model": self.model,
            "messages": chat_messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                # Ollama defaults num_ctx to 2048 regardless of what the model
                # supports. Retrieved context alone is up to 4000 tokens, so
                # the default silently truncated the transcript excerpts out of
                # the prompt and the model answered as if it had no sources.
                "num_ctx": self.context_window,
            },
        }

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> Dict[str, Any]:
        """Non-streaming generation."""
        payload = self._payload(messages, system_prompt, max_tokens, temperature, stream=False)

        try:
            response = await self.client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMTimeout(f"Ollama timed out after {self.timeout}s") from exc
        except httpx.HTTPStatusError as exc:
            raise self._status_error(exc) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc

        data = response.json()
        return {
            "content": (data.get("message") or {}).get("content", ""),
            "stop_reason": data.get("done_reason") or "stop",
            "usage": {
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0),
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
        payload = self._payload(messages, system_prompt, max_tokens, temperature, stream=True)

        try:
            async with self.client.stream("POST", "/api/chat", json=payload) as response:
                if response.status_code >= 400:
                    await response.aread()
                    raise self._status_error(
                        httpx.HTTPStatusError(
                            "ollama error", request=response.request, response=response
                        )
                    )

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed line from Ollama: %r", line[:200])
                        continue

                    delta = (data.get("message") or {}).get("content", "")
                    if delta:
                        yield {"type": "content_delta", "delta": delta}

                    if data.get("done"):
                        yield {
                            "type": "message_stop",
                            "usage": {
                                "input_tokens": data.get("prompt_eval_count", 0),
                                "output_tokens": data.get("eval_count", 0),
                            },
                        }

        except httpx.TimeoutException as exc:
            raise LLMTimeout(f"Ollama timed out after {self.timeout}s") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc

    def _status_error(self, exc: httpx.HTTPStatusError) -> LLMError:
        if exc.response.status_code == 404:
            return LLMUnavailable(
                f"Ollama has no model named '{self.model}'. "
                f"Pull it with: ollama pull {self.model}"
            )
        return LLMError(f"Ollama returned HTTP {exc.response.status_code}")

    async def count_tokens(self, text: str) -> int:
        """Approximate token count. Exact only for OpenAI-family tokenizers."""
        return len(self.encoding.encode(text))
