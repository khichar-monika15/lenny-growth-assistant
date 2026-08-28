"""
LLM provider factory and selection policy.

Selection is centralised here so every caller resolves providers the same way
and the fallback rule is stated in one place.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.config import get_settings

from .providers.base import BaseLLMProvider
from .providers.claude import ClaudeProvider
from .providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)

CLOUD = "claude"
LOCAL = "ollama"
SUPPORTED = (CLOUD, LOCAL)


class ProviderUnavailable(RuntimeError):
    """Raised when no usable provider could be selected."""


@dataclass
class ResolvedProvider:
    """A provider plus how it was chosen, so the UI can show what actually ran."""
    provider: BaseLLMProvider
    name: str
    model: str
    requested: str
    fallback_reason: Optional[str] = None

    @property
    def did_fallback(self) -> bool:
        return self.fallback_reason is not None


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create_provider(provider_name: str, config: Dict[str, Any]) -> BaseLLMProvider:
        """
        Create a provider from an explicit config.

        Args:
            provider_name: 'claude' or 'ollama'
            config: Provider-specific configuration
        """
        settings = get_settings()

        if provider_name == CLOUD:
            api_key = config.get("api_key")
            if not api_key:
                raise ProviderUnavailable("Anthropic API key is not configured")
            return ClaudeProvider(
                api_key=api_key,
                model=config.get("model") or settings.ANTHROPIC_MODEL,
            )

        if provider_name == LOCAL:
            return OllamaProvider(
                base_url=config.get("base_url") or settings.OLLAMA_BASE_URL,
                model=config.get("model") or settings.OLLAMA_CHAT_MODEL,
                timeout=config.get("timeout") or settings.OLLAMA_TIMEOUT_SECONDS,
            )

        raise ValueError(f"Unknown provider: {provider_name}. Expected one of {SUPPORTED}.")


def resolve_provider(requested: Optional[str] = None) -> ResolvedProvider:
    """
    Select a provider, falling back to local when the cloud one is unusable.

    Claude needs an API key that the local demo does not require, so a Claude
    request without a key degrades to Ollama with the reason recorded rather
    than failing the turn.
    """
    settings = get_settings()
    requested = (requested or settings.DEFAULT_MODEL or LOCAL).lower()

    if requested not in SUPPORTED:
        raise ValueError(f"Unknown provider: {requested}. Expected one of {SUPPORTED}.")

    fallback_reason = None
    selected = requested

    if requested == CLOUD and not settings.ANTHROPIC_API_KEY:
        fallback_reason = "ANTHROPIC_API_KEY is not set, so the local model was used instead"
        selected = LOCAL
        logger.warning("Claude requested without an API key; falling back to Ollama")

    if selected == CLOUD:
        provider = LLMProviderFactory.create_provider(
            CLOUD, {"api_key": settings.ANTHROPIC_API_KEY, "model": settings.ANTHROPIC_MODEL}
        )
        model = settings.ANTHROPIC_MODEL
    else:
        provider = LLMProviderFactory.create_provider(
            LOCAL, {"base_url": settings.OLLAMA_BASE_URL, "model": settings.OLLAMA_CHAT_MODEL}
        )
        model = settings.OLLAMA_CHAT_MODEL

    return ResolvedProvider(
        provider=provider,
        name=selected,
        model=model,
        requested=requested,
        fallback_reason=fallback_reason,
    )
