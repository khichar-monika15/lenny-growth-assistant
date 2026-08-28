"""Embedding generation service using Ollama."""
import asyncio
import logging
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Raised when embeddings cannot be produced."""


class EmbeddingService:
    """Generate embeddings via Ollama."""

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        model: Optional[str] = None,
        concurrency: int = 4,
    ):
        settings = get_settings()
        self.base_url = ollama_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_EMBEDDING_MODEL
        self.client = httpx.AsyncClient(timeout=120.0)
        self._semaphore = asyncio.Semaphore(concurrency)

    async def __aenter__(self) -> "EmbeddingService":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return (await self.generate_embeddings([text]))[0]

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Ollama's embeddings endpoint takes one prompt per call, so requests are
        issued concurrently with a bounded semaphore rather than serially.
        """
        if not texts:
            return []

        return list(await asyncio.gather(*(self._embed_one(text) for text in texts)))

    async def _embed_one(self, text: str) -> List[float]:
        async with self._semaphore:
            try:
                response = await self.client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise EmbeddingError(
                    f"Ollama rejected embedding request for model '{self.model}' "
                    f"(HTTP {exc.response.status_code}). Is the model pulled?"
                ) from exc
            except httpx.HTTPError as exc:
                raise EmbeddingError(
                    f"Cannot reach Ollama at {self.base_url}: {exc}"
                ) from exc

            embedding = response.json().get("embedding")
            if not embedding:
                raise EmbeddingError(
                    f"Ollama returned an empty embedding for model '{self.model}'"
                )
            return embedding

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
