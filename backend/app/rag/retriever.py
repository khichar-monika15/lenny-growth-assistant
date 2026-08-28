"""
RAG retriever - vector search with metadata enrichment.
"""
from dataclasses import dataclass
from typing import List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings


@dataclass
class RetrievedChunk:
    """Retrieved chunk with metadata."""
    chunk_id: str
    content: str
    similarity_score: float
    transcript_title: str
    transcript_date: str
    guests: List[str]
    chunk_index: int


class VectorRetriever:
    """Retrieves relevant chunks via vector similarity search."""

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        collection_name: str = "lenny_transcripts"
    ):
        self.client = chromadb.HttpClient(
            host=chroma_host,
            port=chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection_name = collection_name
        self.collection = None

    async def initialize(self):
        """Initialize ChromaDB collection."""
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name
            )
        except Exception:
            # Collection doesn't exist yet - will be created during ingestion
            self.collection = None

    async def retrieve(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filters: Optional[dict] = None
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks via vector search.

        Args:
            query_embedding: Query vector embedding
            top_k: Number of chunks to retrieve
            filters: Optional metadata filters

        Returns:
            List of RetrievedChunk objects
        """
        if not self.collection:
            await self.initialize()

        if not self.collection:
            return []  # No chunks indexed yet

        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filters
        )

        # Convert to RetrievedChunk objects
        chunks = []
        if results and results['ids']:
            for i, chunk_id in enumerate(results['ids'][0]):
                metadata = results['metadatas'][0][i]
                content = results['documents'][0][i]
                distance = results['distances'][0][i]

                # Convert distance to similarity (cosine distance to similarity)
                similarity_score = 1 - distance

                chunks.append(RetrievedChunk(
                    chunk_id=chunk_id,
                    content=content,
                    similarity_score=similarity_score,
                    transcript_title=metadata.get('transcript_title', 'Unknown'),
                    transcript_date=metadata.get('transcript_date', ''),
                    guests=metadata.get('guests', []),
                    chunk_index=metadata.get('chunk_index', 0)
                ))

        return chunks
