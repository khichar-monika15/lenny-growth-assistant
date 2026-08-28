"""
Error translation.

Domain failures map to stable codes and safe messages. Internal detail is
logged, never returned: a stack trace or connection string in an HTTP body is
an information leak.
"""
import logging
from typing import Tuple

from fastapi import HTTPException, status

from app.llm.factory import ProviderUnavailable
from app.llm.providers.base import LLMTimeout, LLMUnavailable
from app.rag.chroma import VectorStoreUnavailable
from app.services.embedding_service import EmbeddingError
from app.services.session_service import SessionNotFound

logger = logging.getLogger(__name__)

GENERIC = (
    status.HTTP_500_INTERNAL_SERVER_ERROR,
    "internal_error",
    "Something went wrong handling this request.",
    "Check the backend logs with: docker compose logs backend",
)


def classify(exc: Exception) -> Tuple[int, str, str, str]:
    """Map an exception to (status, code, detail, hint)."""
    if isinstance(exc, SessionNotFound):
        return (
            status.HTTP_404_NOT_FOUND,
            "session_not_found",
            "That chat session does not exist.",
            "Start a new chat, or omit session_id to have one created.",
        )

    if isinstance(exc, VectorStoreUnavailable):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "vector_store_unavailable",
            "The transcript index is unreachable, so answers cannot be grounded.",
            "Check ChromaDB with: docker compose ps chromadb",
        )

    if isinstance(exc, EmbeddingError):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "embedding_unavailable",
            "The embedding model is unavailable, so the question could not be searched.",
            "Pull the model with: docker compose exec ollama ollama pull nomic-embed-text",
        )

    if isinstance(exc, LLMTimeout):
        return (
            status.HTTP_504_GATEWAY_TIMEOUT,
            "model_timeout",
            "The model took too long to respond.",
            "Local models are slow on first load. Retry, or raise OLLAMA_TIMEOUT_SECONDS.",
        )

    if isinstance(exc, (LLMUnavailable, ProviderUnavailable)):
        return (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "model_unavailable",
            str(exc),
            "Check the provider with: curl localhost:8080/health/llm",
        )

    if isinstance(exc, ValueError):
        return (
            status.HTTP_400_BAD_REQUEST,
            "invalid_request",
            str(exc),
            None,
        )

    return GENERIC


def to_http_exception(exc: Exception) -> HTTPException:
    """Convert a domain exception into a safe HTTPException."""
    status_code, code, detail, hint = classify(exc)

    if status_code >= 500:
        logger.exception("Unhandled error: %s", exc)
    else:
        logger.warning("%s: %s", code, exc)

    return HTTPException(
        status_code=status_code,
        detail={"error": code, "detail": detail, "hint": hint},
    )


def to_stream_event(exc: Exception) -> dict:
    """Convert a domain exception into an SSE error event."""
    status_code, code, detail, hint = classify(exc)

    if status_code >= 500:
        logger.exception("Unhandled error during stream: %s", exc)
    else:
        logger.warning("%s during stream: %s", code, exc)

    return {"type": "error", "error": code, "detail": detail, "hint": hint}
