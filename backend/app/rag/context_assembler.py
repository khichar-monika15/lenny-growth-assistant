"""
Context assembler - formats retrieved chunks for LLM.
"""
from dataclasses import dataclass
from typing import List
from .retriever import RetrievedChunk


@dataclass
class AssembledContext:
    """Assembled context ready for LLM."""
    context: str
    sources: List[dict]
    total_chunks: int
    total_tokens: int


class ContextAssembler:
    """Assembles retrieved chunks into structured context for LLM."""

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens

    def assemble_context(
        self,
        retrieved_chunks: List[RetrievedChunk],
        min_chunks: int = 3
    ) -> AssembledContext:
        """
        Assemble chunks into formatted context.

        Args:
            retrieved_chunks: List of retrieved chunks
            min_chunks: Minimum chunks to include

        Returns:
            AssembledContext object
        """
        if not retrieved_chunks:
            return AssembledContext(
                context="",
                sources=[],
                total_chunks=0,
                total_tokens=0
            )

        # Sort by similarity (already sorted, but ensure)
        chunks = sorted(
            retrieved_chunks,
            key=lambda x: x.similarity_score,
            reverse=True
        )

        # Deduplicate by chunk_id
        seen_ids = set()
        unique_chunks = []
        for chunk in chunks:
            if chunk.chunk_id not in seen_ids:
                unique_chunks.append(chunk)
                seen_ids.add(chunk.chunk_id)

        # Build context within token budget
        context_parts = []
        sources = []
        total_tokens = 0

        for i, chunk in enumerate(unique_chunks):
            # Estimate tokens (rough: 1 token ≈ 4 chars)
            chunk_tokens = len(chunk.content) // 4

            if total_tokens + chunk_tokens > self.max_tokens and len(context_parts) >= min_chunks:
                break

            # Format with citation
            citation = f"[Source {i+1}: {chunk.transcript_title}]"
            formatted = f"{citation}\n{chunk.content}\n"
            context_parts.append(formatted)

            # Track source
            sources.append({
                "chunk_id": chunk.chunk_id,
                "transcript_title": chunk.transcript_title,
                "transcript_date": chunk.transcript_date,
                "guests": chunk.guests,
                "similarity_score": round(chunk.similarity_score, 3)
            })

            total_tokens += chunk_tokens

        # Join all parts
        context = "\n---\n".join(context_parts)

        return AssembledContext(
            context=context,
            sources=sources,
            total_chunks=len(context_parts),
            total_tokens=total_tokens
        )
