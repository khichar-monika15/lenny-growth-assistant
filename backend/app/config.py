"""
Application configuration using Pydantic Settings.
Loads from environment variables with validation.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://lenny:lenny_dev_password@localhost:5432/lenny"

    # LLM Providers
    ANTHROPIC_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_CHAT_MODEL: str = "llama3.1:8b"
    DEFAULT_MODEL: str = "ollama"

    # ChromaDB
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION_NAME: str = "lenny_transcripts"
    CHROMADB_HOST: str = "chromadb"
    CHROMADB_PORT: int = 8000

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

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance for dependency injection."""
    return settings
