"""
Ingestion pipeline tests.

These cover the decisions that broke in production: what makes a transcript
skippable, and what metadata the vector store is given.
"""
from datetime import date

import pytest

from app.ingestion.pipeline import _parse_date, _vector_chunk_count


class FakeCollection:
    """Minimal stand-in for a ChromaDB collection."""

    def __init__(self, ids_by_transcript: dict | None = None, raises: bool = False):
        self._ids = ids_by_transcript or {}
        self._raises = raises

    def get(self, where=None, include=None):
        if self._raises:
            raise RuntimeError("vector store unreachable")
        transcript_id = (where or {}).get("transcript_id")
        return {"ids": self._ids.get(transcript_id, [])}


class TestSkipRequiresVectorsToExist:
    """
    A matching content hash is not sufficient to skip a transcript.

    The vector store can be rebuilt or lost independently of PostgreSQL. When
    that happened, every hash still matched, every transcript was skipped, and
    the index stayed permanently empty.
    """

    async def test_counts_vectors_present_for_a_transcript(self):
        collection = FakeCollection({"t1": ["t1_0", "t1_1", "t1_2"]})

        assert await _vector_chunk_count(collection, "t1") == 3

    async def test_reports_zero_when_the_vector_store_was_emptied(self):
        collection = FakeCollection({})

        assert await _vector_chunk_count(collection, "t1") == 0

    async def test_unreadable_vector_store_counts_as_zero_so_it_reindexes(self):
        """Failing closed here means a recoverable reindex, not a silent skip."""
        collection = FakeCollection(raises=True)

        assert await _vector_chunk_count(collection, "t1") == 0

    async def test_counts_are_scoped_per_transcript(self):
        collection = FakeCollection({"t1": ["a", "b"], "t2": ["c"]})

        assert await _vector_chunk_count(collection, "t1") == 2
        assert await _vector_chunk_count(collection, "t2") == 1


class TestDateParsing:
    def test_parses_the_index_date_format(self):
        assert _parse_date("2026-08-23") == date(2026, 8, 23)

    @pytest.mark.parametrize("value", [None, "", "not-a-date", "23/08/2026"])
    def test_unparseable_dates_become_null_rather_than_raising(self, value):
        """One malformed date must not fail the whole transcript."""
        assert _parse_date(value) is None
