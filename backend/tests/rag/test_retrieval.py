"""
Retrieval and context assembly tests.

Scoring and the similarity floor decide what the model is allowed to see, and
a wrong score silently degrades every answer, so both are pinned here.
"""
import pytest

from app.rag.context_assembler import ContextAssembler
from app.rag.retriever import RetrievedChunk, VectorRetriever


def chunk(chunk_id: str, score: float = 0.8, content: str = "content", **kwargs) -> RetrievedChunk:
    defaults = {
        "transcript_title": "Episode",
        "transcript_date": "2026-01-01",
        "guests": ["Guest"],
        "chunk_index": 0,
        "source_url": "https://example.test/ep",
    }
    defaults.update(kwargs)
    return RetrievedChunk(
        chunk_id=chunk_id, content=content, similarity_score=score, **defaults
    )


class FakeCollection:
    """Stands in for a ChromaDB collection."""

    def __init__(self, results: dict, count: int = 10):
        self._results = results
        self._count = count

    def count(self) -> int:
        return self._count

    def query(self, **_kwargs) -> dict:
        return self._results


def retriever_with(collection: FakeCollection, min_similarity: float = 0.25) -> VectorRetriever:
    retriever = VectorRetriever(min_similarity=min_similarity)
    retriever.collection = collection
    return retriever


class TestScoring:
    async def test_cosine_distance_becomes_similarity(self):
        """Collections use hnsw:space=cosine, so similarity is 1 - distance."""
        retriever = retriever_with(
            FakeCollection(
                {
                    "ids": [["a"]],
                    "documents": [["text"]],
                    "metadatas": [[{"transcript_title": "Ep", "transcript_date": "2026-01-01"}]],
                    "distances": [[0.25]],
                }
            )
        )

        chunks = await retriever.retrieve([0.1] * 8)

        assert chunks[0].similarity_score == pytest.approx(0.75)

    async def test_scores_stay_within_zero_and_one(self):
        retriever = retriever_with(
            FakeCollection(
                {
                    "ids": [["a"]],
                    "documents": [["text"]],
                    "metadatas": [[{}]],
                    "distances": [[-0.1]],
                }
            )
        )

        chunks = await retriever.retrieve([0.1] * 8)

        assert 0.0 <= chunks[0].similarity_score <= 1.0

    async def test_weak_matches_are_dropped(self):
        retriever = retriever_with(
            FakeCollection(
                {
                    "ids": [["strong", "weak"]],
                    "documents": [["a", "b"]],
                    "metadatas": [[{}, {}]],
                    "distances": [[0.1, 0.95]],
                }
            ),
            min_similarity=0.5,
        )

        chunks = await retriever.retrieve([0.1] * 8)

        assert [c.chunk_id for c in chunks] == ["strong"]


class TestEmptyIndex:
    async def test_empty_collection_returns_nothing(self):
        retriever = retriever_with(FakeCollection({}, count=0))

        assert await retriever.retrieve([0.1] * 8) == []

    async def test_no_matches_returns_nothing(self):
        retriever = retriever_with(
            FakeCollection({"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]})
        )

        assert await retriever.retrieve([0.1] * 8) == []


class TestMetadata:
    async def test_guests_are_parsed_back_into_a_list(self):
        """Chroma cannot store lists, so guests round-trip as a joined string."""
        retriever = retriever_with(
            FakeCollection(
                {
                    "ids": [["a"]],
                    "documents": [["text"]],
                    "metadatas": [[{"guests": "Jen Abel, Adam Ward"}]],
                    "distances": [[0.2]],
                }
            )
        )

        chunks = await retriever.retrieve([0.1] * 8)

        assert chunks[0].guests == ["Jen Abel", "Adam Ward"]

    async def test_missing_metadata_does_not_crash(self):
        retriever = retriever_with(
            FakeCollection(
                {
                    "ids": [["a"]],
                    "documents": [["text"]],
                    "metadatas": [[{}]],
                    "distances": [[0.2]],
                }
            )
        )

        chunks = await retriever.retrieve([0.1] * 8)

        assert chunks[0].transcript_title == "Unknown"
        assert chunks[0].guests == []


class TestContextAssembly:
    def test_empty_input_produces_empty_context(self):
        assembled = ContextAssembler().assemble_context([])

        assert assembled.is_empty
        assert assembled.sources == []

    def test_chunks_are_ordered_best_first(self):
        assembled = ContextAssembler().assemble_context(
            [chunk("low", 0.4), chunk("high", 0.9), chunk("mid", 0.6)]
        )

        assert [s["chunk_id"] for s in assembled.sources] == ["high", "mid", "low"]

    def test_duplicate_chunks_are_dropped(self):
        assembled = ContextAssembler().assemble_context([chunk("a"), chunk("a"), chunk("b")])

        assert assembled.total_chunks == 2

    def test_token_budget_is_respected(self):
        big = [chunk(f"c{i}", content="word " * 2000) for i in range(10)]

        assembled = ContextAssembler(max_tokens=1000).assemble_context(big)

        assert assembled.total_chunks < 10

    def test_one_oversized_chunk_is_still_returned(self):
        """Better one source than none when the best match is long."""
        assembled = ContextAssembler(max_tokens=100).assemble_context(
            [chunk("big", content="word " * 5000)]
        )

        assert assembled.total_chunks == 1

    def test_citations_are_numbered_and_carry_attribution(self):
        assembled = ContextAssembler().assemble_context(
            [chunk("a", transcript_title="Growth loops", guests=["Jen Abel"])]
        )

        assert "[Source 1: Growth loops | with Jen Abel | 2026-01-01]" in assembled.context
        assert assembled.sources[0]["index"] == 1

    def test_sources_expose_the_link_back_to_the_episode(self):
        assembled = ContextAssembler().assemble_context([chunk("a")])

        assert assembled.sources[0]["source_url"] == "https://example.test/ep"
