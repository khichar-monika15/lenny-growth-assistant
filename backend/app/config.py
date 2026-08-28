"""
Application configuration using Pydantic Settings.
Loads from environment variables with validation.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://lenny:lenny_dev_password@localhost:5432/lenny"

    # LLM Providers
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_CHAT_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT_SECONDS: int = 180
    # Must exceed CONTEXT_MAX_TOKENS plus instructions and history.
    # Ollama defaults to 2048, which truncates retrieved context away.
    OLLAMA_CONTEXT_WINDOW: int = 8192
    DEFAULT_MODEL: str = "ollama"

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "lenny_transcripts"

    # Application
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # RAG Configuration
    CHUNK_MIN_TOKENS: int = 800
    CHUNK_MAX_TOKENS: int = 1200
    CHUNK_OVERLAP_TOKENS: int = 200
    RETRIEVAL_TOP_K: int = 10
    CONTEXT_MAX_TOKENS: int = 4000
    MIN_SIMILARITY_SCORE: float = 0.25

    # Ingestion. Default to a subset so a first run finishes in minutes;
    # set to 0 to ingest the full catalogue.
    INGEST_LIMIT: int = 15
    EMBEDDING_BATCH_SIZE: int = 16

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance for dependency injection."""
    return Settings()


settings = get_settings()
