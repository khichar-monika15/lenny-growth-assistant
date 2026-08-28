"""
Health endpoints.

Split by dependency so a failure points at the thing that broke rather than
returning one opaque "unhealthy".
"""
import asyncio
import logging

import httpx
from fastapi import APIRouter, Response, status
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.database import ping as db_ping
from app.rag.chroma import heartbeat as chroma_heartbeat
from app.rag.retriever import VectorRetriever

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
async def health() -> dict:
    """Cheap check that the process is up. Never touches a dependency."""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "lenny-backend",
        "environment": settings.ENVIRONMENT,
        "default_model": settings.DEFAULT_MODEL,
    }


@router.get("/health/db", summary="PostgreSQL connectivity")
async def health_db(response: Response) -> dict:
    reachable = await db_ping()
    if not reachable:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "postgres": "available" if reachable else "unavailable",
        "hint": None if reachable else "Check with: docker compose ps postgres",
    }


@router.get("/health/retrieval", summary="Vector store and index state")
async def health_retrieval(response: Response) -> dict:
    """Reports both reachability and whether anything has been ingested."""
    if not await run_in_threadpool(chroma_heartbeat):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "chromadb": "unavailable",
            "indexed_chunks": 0,
            "hint": "Check with: docker compose ps chromadb",
        }

    try:
        retriever = VectorRetriever()
        await retriever.initialize()
        count = await retriever.count()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Retrieval health check failed: %s", exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"chromadb": "available", "indexed_chunks": 0, "hint": str(exc)}

    return {
        "chromadb": "available",
        "indexed_chunks": count,
        "hint": None
        if count
        else "Index is empty. Run: docker compose exec backend python -m app.scripts.ingest_transcripts",
    }


@router.get("/health/llm", summary="LLM provider availability")
async def health_llm() -> dict:
    """
    Provider status for the model toggle.

    Reports which models Ollama actually has pulled, since a missing model
    fails at generation time rather than at connection time.
    """
    settings = get_settings()
    result = {
        "default": settings.DEFAULT_MODEL,
        "ollama": {"status": "unavailable", "model": settings.OLLAMA_CHAT_MODEL},
        "anthropic": {
            "status": "configured" if settings.ANTHROPIC_API_KEY else "not_configured",
            "model": settings.ANTHROPIC_MODEL,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            available = {m["name"] for m in response.json().get("models", [])}
    except (httpx.HTTPError, asyncio.TimeoutError, KeyError, ValueError):
        result["ollama"]["hint"] = f"Cannot reach Ollama at {settings.OLLAMA_BASE_URL}"
        return result

    chat_ready = _has_model(available, settings.OLLAMA_CHAT_MODEL)
    embed_ready = _has_model(available, settings.OLLAMA_EMBEDDING_MODEL)

    result["ollama"] = {
        "status": "available" if chat_ready else "model_missing",
        "model": settings.OLLAMA_CHAT_MODEL,
        "chat_model_pulled": chat_ready,
        "embedding_model_pulled": embed_ready,
    }
    if not (chat_ready and embed_ready):
        missing = [
            name
            for name, ready in (
                (settings.OLLAMA_CHAT_MODEL, chat_ready),
                (settings.OLLAMA_EMBEDDING_MODEL, embed_ready),
            )
            if not ready
        ]
        result["ollama"]["hint"] = "Pull with: " + "; ".join(
            f"ollama pull {name}" for name in missing
        )

    return result


def _has_model(available: set, wanted: str) -> bool:
    """Ollama reports ':latest' explicitly; treat a bare name as matching it."""
    return wanted in available or f"{wanted}:latest" in available
