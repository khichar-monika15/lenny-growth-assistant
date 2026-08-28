"""Health check endpoints."""
from fastapi import APIRouter
from app.config import get_settings
import httpx

router = APIRouter()


@router.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy", "service": "lenny-backend"}


@router.get("/health/llm")
async def health_llm():
    """Check LLM provider availability."""
    settings = get_settings()
    status = {}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                status["ollama"] = "available"
            else:
                status["ollama"] = "unavailable"
    except Exception:
        status["ollama"] = "unavailable"

    # Check Anthropic (if key configured)
    if settings.ANTHROPIC_API_KEY:
        status["anthropic"] = "configured"
    else:
        status["anthropic"] = "not_configured"

    return status
