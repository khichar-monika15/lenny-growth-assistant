"""
Shared ChromaDB client.

The client is created once per process rather than per request: each HttpClient
opens its own connection pool and performs a handshake on construction, which
was previously paid on every chat turn.
"""
import logging
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings

logger = logging.getLogger(__name__)

# Cosine must be set at creation time. ChromaDB otherwise defaults to squared
# L2, whose distances are unbounded and cannot be turned into a 0..1 score.
COSINE_SPACE = {"hnsw:space": "cosine"}


class VectorStoreUnavailable(RuntimeError):
    """Raised when ChromaDB cannot be reached."""


@lru_cache
def get_chroma_client() -> chromadb.api.ClientAPI:
    """Get the process-wide ChromaDB HTTP client."""
    settings = get_settings()
    return chromadb.HttpClient(
        host=settings.CHROMA_HOST,
        port=settings.CHROMA_PORT,
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_or_create_collection(client: chromadb.api.ClientAPI, name: str):
    """Get the collection, creating it with cosine distance if absent."""
    return client.get_or_create_collection(
        name=name,
        metadata={"description": "Lenny's Podcast transcript chunks", **COSINE_SPACE},
    )


def heartbeat() -> bool:
    """True when ChromaDB answers. Used by the health endpoints."""
    try:
        get_chroma_client().heartbeat()
        return True
    except Exception:  # noqa: BLE001 - any failure means unavailable
        logger.warning("ChromaDB heartbeat failed", exc_info=True)
        return False
