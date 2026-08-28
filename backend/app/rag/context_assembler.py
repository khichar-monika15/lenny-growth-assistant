"""Context assembler - formats retrieved chunks for the LLM."""
from dataclasses import dataclass, field
from typing import List

import tiktoken

from .retriever import RetrievedChunk

_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class AssembledContext:
    """Assembled context ready for the LLM."""
    context: str
    sources: List[dict] = field(default_factory=list)
    total_chunks: int = 0
    total_tokens: int = 0

    @property
    def is_empty(self) -> bool:
        return self.total_chunks == 0


class ContextAssembler:
    """Assembles retrieved chunks into structured context for the LLM."""

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens

    def assemble_context(self, retrieved_chunks: List[RetrievedChunk]) -> AssembledContext:
        """
        Assemble chunks into a citation-annotated context block.

        Chunks are taken best-first and stop at the token budget. The budget is
        a hard limit: an over-budget chunk is skipped rather than truncating
        mid-sentence, and later smaller chunks may still fit.
        """
        if not retrieved_chunks:
            return AssembledContext(context="")

        ordered = sorted(retrieved_chunks, key=lambda c: c.similarity_score, reverse=True)

        seen = set()
        context_parts: List[str] = []
        sources: List[dict] = []
        total_tokens = 0

        for chunk in ordered:
            if chunk.chunk_id in seen:
                continue

            citation = self._citation(chunk, len(sources) + 1)
            block = f"{citation}\n{chunk.content}\n"
            block_tokens = len(_ENCODING.encode(block))

            if total_tokens + block_tokens > self.max_tokens:
                if context_parts:
                    continue
                # Never return empty context because the single best chunk is
                # oversized; include it and let the model see one source.
                block_tokens = self.max_tokens

            seen.add(chunk.chunk_id)
            context_parts.append(block)
            total_tokens += block_tokens
            sources.append(
                {
                    "index": len(sources) + 1,
                    "chunk_id": chunk.chunk_id,
                    "transcript_title": chunk.transcript_title,
                    "transcript_date": chunk.transcript_date,
                    "guests": chunk.guests,
                    "source_url": chunk.source_url,
                    "similarity_score": chunk.similarity_score,
                }
            )

        return AssembledContext(
            context="\n---\n".join(context_parts),
            sources=sources,
            total_chunks=len(context_parts),
            total_tokens=total_tokens,
        )

    @staticmethod
    def _citation(chunk: RetrievedChunk, position: int) -> str:
        parts = [chunk.transcript_title]
        if chunk.guests:
            parts.append("with " + ", ".join(chunk.guests))
        if chunk.transcript_date:
            parts.append(chunk.transcript_date)
        return f"[Source {position}: {' | '.join(parts)}]"
