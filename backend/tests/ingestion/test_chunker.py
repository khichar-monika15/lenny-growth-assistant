"""
Tests for the semantic chunker.

The chunker previously looped forever on any input longer than max_tokens,
which silently killed transcript ingestion. These tests pin the loop
termination contract first, then the quality guarantees.
"""
import pytest

from app.ingestion.chunker import chunk_text


def _long_text(sentence_count: int) -> str:
    """Build a paragraphed text of roughly sentence_count * 7 tokens."""
    paragraphs = []
    for i in range(sentence_count // 5):
        paragraphs.append(
            " ".join(f"Sentence number {i * 5 + j} about growth and retention." for j in range(5))
        )
    return "\n\n".join(paragraphs)


class TestTermination:
    """The chunker must always terminate and always advance."""

    @pytest.mark.parametrize("sentences", [200, 400, 900, 3000])
    def test_terminates_on_long_input(self, sentences):
        chunks = chunk_text(_long_text(sentences), min_tokens=800, max_tokens=1200, overlap_tokens=200)

        assert len(chunks) > 1

    def test_terminates_when_tail_is_shorter_than_overlap(self):
        """Regression: a tail shorter than overlap_tokens used to stall the cursor forever."""
        text = _long_text(230)  # lands just past one max_tokens window

        chunks = chunk_text(text, min_tokens=800, max_tokens=1200, overlap_tokens=200)

        assert chunks[-1].end_char == len(text)

    def test_start_offsets_strictly_increase(self):
        chunks = chunk_text(_long_text(900), min_tokens=800, max_tokens=1200, overlap_tokens=200)

        starts = [c.start_char for c in chunks]
        assert starts == sorted(starts)
        assert len(set(starts)) == len(starts)

    def test_overlap_larger_than_max_does_not_hang(self):
        chunks = chunk_text(_long_text(400), min_tokens=100, max_tokens=500, overlap_tokens=900)

        assert len(chunks) >= 1


class TestChunkSizing:
    def test_no_chunk_exceeds_max_tokens(self):
        chunks = chunk_text(_long_text(900), min_tokens=800, max_tokens=1200, overlap_tokens=200)

        for chunk in chunks:
            assert chunk.token_count <= 1200

    def test_all_but_final_chunk_reach_min_tokens(self):
        chunks = chunk_text(_long_text(900), min_tokens=800, max_tokens=1200, overlap_tokens=200)

        for chunk in chunks[:-1]:
            assert chunk.token_count >= 800

    def test_short_text_returns_single_chunk(self):
        text = "Product-market fit is the only thing that matters early on."

        chunks = chunk_text(text, min_tokens=800, max_tokens=1200, overlap_tokens=200)

        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len(text)

    def test_empty_text_returns_no_chunks(self):
        assert chunk_text("", min_tokens=800, max_tokens=1200, overlap_tokens=200) == []

    def test_paragraph_longer_than_max_tokens_is_split(self):
        wall_of_text = " ".join(f"word{i}" for i in range(4000))  # single paragraph, no blank lines

        chunks = chunk_text(wall_of_text, min_tokens=800, max_tokens=1200, overlap_tokens=200)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.token_count <= 1200


class TestContentIntegrity:
    def test_chunks_cover_the_whole_document(self):
        text = _long_text(900)

        chunks = chunk_text(text, min_tokens=800, max_tokens=1200, overlap_tokens=200)

        assert chunks[0].start_char == 0
        assert chunks[-1].end_char == len(text)

    def test_char_offsets_match_content(self):
        """Offsets must be real slices, not the old chars-per-token estimate."""
        text = _long_text(900)

        chunks = chunk_text(text, min_tokens=800, max_tokens=1200, overlap_tokens=200)

        for chunk in chunks:
            assert text[chunk.start_char:chunk.end_char] == chunk.content

    def test_consecutive_chunks_overlap(self):
        chunks = chunk_text(_long_text(900), min_tokens=800, max_tokens=1200, overlap_tokens=200)

        for previous, current in zip(chunks, chunks[1:]):
            assert current.start_char < previous.end_char

    def test_chunk_indexes_are_sequential(self):
        chunks = chunk_text(_long_text(900), min_tokens=800, max_tokens=1200, overlap_tokens=200)

        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
