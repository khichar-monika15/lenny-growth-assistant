"""
Base LLM provider interface.

Both providers present the same shape so the rest of the application never
branches on which model is in use. Failures are normalised into this small
error hierarchy so callers can distinguish "try again" from "misconfigured".
"""
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional


class LLMError(RuntimeError):
    """Base class for provider failures."""


class LLMUnavailable(LLMError):
    """Provider is unreachable, unauthenticated or missing the model."""


class LLMTimeout(LLMError):
    """Provider did not respond in time."""


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
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

    @abstractmethod
    def stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming generation.

        Yields:
            {"type": "content_delta", "delta": str}
            {"type": "message_stop", "usage": {...}}
        """

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Estimate token count for text."""

    async def aclose(self) -> None:
        """Release provider resources. Overridden where a client is held."""
        return None
