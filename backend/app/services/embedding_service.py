"""Embedding generation service using Ollama."""
import httpx
from typing import List
from app.config import get_settings


class EmbeddingService:
    """Generate embeddings via Ollama."""

    def __init__(self, ollama_url: str = None, model: str = None):
        self.settings = get_settings()
        self.base_url = ollama_url or self.settings.OLLAMA_BASE_URL
        self.model = model or self.settings.OLLAMA_EMBEDDING_MODEL
        self.client = httpx.AsyncClient(timeout=60.0)

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text."""
        embeddings = await self.generate_embeddings([text])
        return embeddings[0]

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        embeddings = []

        for text in texts:
            response = await self.client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text
                }
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data["embedding"])

        return embeddings

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
