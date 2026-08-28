"""
FastAPI application entry point for Lenny Growth Assistant.
Author: khichar-monika15
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.v1 import chat, health, sessions, ship30
from app.config import get_settings
from app.database import dispose_engine, ping as db_ping
from app.logging_config import configure_logging, request_id_middleware
from app.rag.chroma import heartbeat as chroma_heartbeat

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


async def _report_dependencies() -> None:
    """
    Log dependency state at boot.

    Startup never blocks on these: the API must come up so its health
    endpoints can explain what is broken, rather than crash-looping.
    """
    if await db_ping():
        logger.info("PostgreSQL reachable")
    else:
        logger.error("PostgreSQL unreachable - sessions and history will fail")

    if await run_in_threadpool(chroma_heartbeat):
        logger.info("ChromaDB reachable")
    else:
        logger.error("ChromaDB unreachable - answers cannot be grounded")

    if not settings.ANTHROPIC_API_KEY:
        logger.info("No ANTHROPIC_API_KEY set; Claude requests will fall back to Ollama")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting Lenny Growth Assistant")
    logger.info("Environment: %s | default model: %s", settings.ENVIRONMENT, settings.DEFAULT_MODEL)
    await _report_dependencies()

    yield

    logger.info("Shutting down Lenny Growth Assistant")
    await dispose_engine()


app = FastAPI(
    title="Lenny Growth Assistant API",
    description=(
        "RAG-powered assistant for Lenny's Podcast transcripts. "
        "Answers are grounded in retrieved transcript chunks and cite their sources."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.middleware("http")(request_id_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log the detail, return a safe body."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": "Something went wrong handling this request.",
            "hint": "Check the backend logs with: docker compose logs backend",
        },
    )


@app.get("/", tags=["health"], summary="Service metadata")
async def root() -> dict:
    return {
        "service": "Lenny Growth Assistant API",
        "version": app.version,
        "docs": "/docs",
        "health": "/health",
    }


app.include_router(health.router)
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(ship30.router, prefix="/api/v1", tags=["ship30"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.ENVIRONMENT == "development",
    )
