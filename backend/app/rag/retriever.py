"""RAG retriever - vector search over transcript chunks."""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.rag.chroma import VectorStoreUnavailable, get_chroma_client, get_or_create_collection

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """Retrieved chunk with citation metadata."""
    chunk_id: str
    content: str
    similarity_score: float
    transcript_title: str
    transcript_date: str
    guests: List[str] = field(default_factory=list)
    chunk_index: int = 0
    source_url: str = ""


class VectorRetriever:
    """Retrieves relevant chunks via vector similarity search."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        min_similarity: Optional[float] = None,
    ):
        settings = get_settings()
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.min_similarity = (
            settings.MIN_SIMILARITY_SCORE if min_similarity is None else min_similarity
        )
        self.collection = None

    async def initialize(self) -> None:
        """
        Bind to the ChromaDB collection.

        A missing collection means nothing has been ingested yet, which is a
        recoverable empty-index state. An unreachable ChromaDB is an
        infrastructure failure and must not be silently reported as "no
        results" - that used to make an outage look like an ungrounded answer.
        """
        try:
            client = get_chroma_client()
            self.collection = await run_in_threadpool(
                get_or_create_collection, client, self.collection_name
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a typed error below
            logger.error("ChromaDB unreachable: %s", exc)
            raise VectorStoreUnavailable(
                "Vector store is unavailable, so answers cannot be grounded in transcripts"
            ) from exc

    async def count(self) -> int:
        """Number of indexed chunks."""
        if self.collection is None:
            await self.initialize()
        return await run_in_threadpool(self.collection.count)

    async def retrieve(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[dict] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks via vector search.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of chunks to retrieve
            filters: Optional ChromaDB metadata filter

        Returns:
            Chunks above the similarity floor, best first
        """
        if self.collection is None:
            await self.initialize()

        if await self.count() == 0:
            logger.warning("Vector store is empty - has ingestion been run?")
            return []

        results = await run_in_threadpool(
            lambda: self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filters,
            )
        )

        ids = (results.get("ids") or [[]])[0]
        if not ids:
            return []

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        chunks = []
        for chunk_id, content, metadata, distance in zip(ids, documents, metadatas, distances):
            metadata = metadata or {}
            # Collections are created with hnsw:space=cosine, so distance is in
            # 0..2 and similarity is its complement.
            similarity = 1.0 - float(distance)
            if similarity < self.min_similarity:
                continue

            guests = [g.strip() for g in str(metadata.get("guests", "")).split(",") if g.strip()]

            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    content=content,
                    similarity_score=round(max(0.0, min(1.0, similarity)), 4),
                    transcript_title=metadata.get("transcript_title", "Unknown"),
                    transcript_date=metadata.get("transcript_date", ""),
                    guests=guests,
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    source_url=metadata.get("source_url", ""),
                )
            )

        return chunks
