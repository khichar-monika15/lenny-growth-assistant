"""
FastAPI application entry point for Lenny Growth Assistant.
Author: khichar-monika15
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("🚀 Starting Lenny Growth Assistant")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Default LLM: {settings.DEFAULT_MODEL}")

    # TODO: Initialize database connection pool
    # TODO: Initialize ChromaDB client
    # TODO: Check Ollama connection

    yield

    # Shutdown
    logger.info("👋 Shutting down Lenny Growth Assistant")
    # TODO: Close database connections
    # TODO: Close ChromaDB client


# Create FastAPI app
app = FastAPI(
    title="Lenny Growth Assistant API",
    description="RAG-powered assistant for Lenny's Podcast transcripts",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
origins = settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "default_model": settings.DEFAULT_MODEL
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Lenny Growth Assistant API",
        "docs": "/docs",
        "health": "/health"
    }


# Mount API routers
from app.api.v1 import chat, health, ship30

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(ship30.router, prefix="/api/v1", tags=["ship30"])
app.include_router(health.router, tags=["health"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True if settings.ENVIRONMENT == "development" else False
    )
