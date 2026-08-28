"""
Ollama local LLM provider.
Adapts Ollama API to match Claude SDK interface.
"""
from typing import AsyncIterator, List, Dict, Any, Optional
import httpx
import json
import tiktoken

from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        timeout: int = 120
    ):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout
        )
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
        prompt = self._construct_prompt(messages, system_prompt)

        response = await self.client.post(
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
        )

        data = response.json()

        return {
            "content": data.get("response", ""),
            "stop_reason": "stop",
            "usage": {
                "input_tokens": data.get("prompt_eval_count", 0),
                "output_tokens": data.get("eval_count", 0)
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
        prompt = self._construct_prompt(messages, system_prompt)

        async with self.client.stream(
            "POST",
            "/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)

                    if "response" in data:
                        yield {
                            "type": "content_delta",
                            "delta": data["response"]
                        }

                    if data.get("done"):
                        yield {"type": "message_stop"}

    async def count_tokens(self, text: str) -> int:
        """Approximate token counting."""
        return len(self.encoding.encode(text))

    def _construct_prompt(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> str:
        """Convert Claude-style messages to Ollama prompt format."""
        parts = []

        if system_prompt:
            parts.append(f"System: {system_prompt}\n")

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if role == "user":
                parts.append(f"User: {content}\n")
            elif role == "assistant":
                parts.append(f"Assistant: {content}\n")

        parts.append("Assistant: ")

        return "\n".join(parts)
