"""
Base LLM provider interface.
Ensures consistent interface across Claude and Ollama.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Non-streaming generation.

        Returns:
            {
                "content": str,
                "stop_reason": str,
                "usage": {"input_tokens": int, "output_tokens": int}
            }
        """
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming generation.

        Yields:
            {"type": "content_delta", "delta": str}
            {"type": "message_stop"}
        """
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        pass
