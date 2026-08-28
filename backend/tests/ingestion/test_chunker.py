"""
Tests for semantic chunker.
TDD approach: One test → one implementation → refactor.
"""
import pytest
from app.ingestion.chunker import chunk_text, Chunk


class TestSemanticChunker:
    """Test suite for semantic text chunking."""

    def test_chunks_stay_within_token_range(self):
        """
        RED Test 1: Chunks should respect min/max token boundaries.

        Given: A long text that requires multiple chunks
        When: chunk_text is called with default parameters (800-1200 tokens)
        Then: All chunks should have token_count between 800 and 1200
        """
        # Create a text that's definitely longer than 1200 tokens
        # Average: 1 token ≈ 4 characters, so 5000 tokens ≈ 20000 chars
        long_text = "This is a sample sentence. " * 1000  # ~5000 tokens

        chunks = chunk_text(long_text, min_tokens=800, max_tokens=1200, overlap_tokens=200)

        # Verify we got multiple chunks
        assert len(chunks) > 1, "Should produce multiple chunks for long text"

        # Verify each chunk is within bounds
        for i, chunk in enumerate(chunks):
            assert 800 <= chunk.token_count <= 1200, \
                f"Chunk {i} has {chunk.token_count} tokens, outside range [800, 1200]"
