"""
LLM Provider Factory.
Creates appropriate provider based on configuration.
"""
from typing import Dict, Any
from .providers.base import BaseLLMProvider
from .providers.claude import ClaudeProvider
from .providers.ollama import OllamaProvider


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create_provider(
        provider_name: str,
        config: Dict[str, Any]
    ) -> BaseLLMProvider:
        """
        Create provider based on name.

        Args:
            provider_name: 'claude' or 'ollama'
            config: Provider-specific configuration

        Returns:
            BaseLLMProvider instance
        """
        if provider_name == "claude":
            return ClaudeProvider(
                api_key=config.get("api_key"),
                model=config.get("model", "claude-3-5-sonnet-20241022"),
                default_max_tokens=config.get("max_tokens", 4096)
            )

        elif provider_name == "ollama":
            return OllamaProvider(
                base_url=config.get("base_url", "http://localhost:11434"),
                model=config.get("model", "llama3.1:8b"),
                timeout=config.get("timeout", 120)
            )

        else:
            raise ValueError(f"Unknown provider: {provider_name}")
