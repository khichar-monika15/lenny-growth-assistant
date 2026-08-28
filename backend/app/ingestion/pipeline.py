"""Transcript ingestion pipeline: fetch -> chunk -> embed -> store."""
import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import delete, select
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.database import get_session
from app.ingestion.chunker import chunk_text
from app.ingestion.github_fetcher import GitHubFetcher
from app.models import Chunk, Transcript
from app.rag.chroma import get_chroma_client, get_or_create_collection
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def _parse_date(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Unparseable publication date %r, storing null", value)
        return None


async def ingest_transcripts(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Ingest transcripts from Lenny's public transcript repository.

    Idempotent: a transcript whose content hash is unchanged is skipped, and a
    transcript whose content changed is updated in place with its old chunks
    removed from both PostgreSQL and ChromaDB.

    Args:
        limit: Maximum transcripts to process. None or 0 means all.

    Returns:
        Dict with ingestion statistics
    """
    settings = get_settings()
    stats: Dict[str, Any] = {
        "transcripts_processed": 0,
        "transcripts_skipped": 0,
        "chunks_created": 0,
        "errors": [],
    }

    fetcher = GitHubFetcher()
    embedding_service = EmbeddingService()
    chroma = get_chroma_client()
    collection = await run_in_threadpool(
        get_or_create_collection, chroma, settings.CHROMA_COLLECTION_NAME
    )

    try:
        index = await fetcher.fetch_index()
        if limit:
            index = index[:limit]

        logger.info("Ingesting %d transcripts", len(index))

        for position, entry in enumerate(index, start=1):
            title = entry.get("title", "Untitled")
            try:
                async with get_session() as session:
                    created = await _ingest_one(
                        session, collection, fetcher, embedding_service, entry, settings
                    )

                if created is None:
                    stats["transcripts_skipped"] += 1
                    logger.info("[%d/%d] unchanged, skipped: %s", position, len(index), title)
                else:
                    stats["transcripts_processed"] += 1
                    stats["chunks_created"] += created
                    logger.info(
                        "[%d/%d] ingested: %s (%d chunks)", position, len(index), title, created
                    )

            except Exception as exc:  # noqa: BLE001 - one bad transcript must not stop the run
                stats["errors"].append({"transcript": title, "error": str(exc)})
                logger.exception("[%d/%d] failed: %s", position, len(index), title)

    finally:
        await fetcher.close()
        await embedding_service.close()

    return stats


async def _ingest_one(
    session,
    collection,
    fetcher: GitHubFetcher,
    embedding_service: EmbeddingService,
    entry: Dict[str, Any],
    settings,
) -> Optional[int]:
    """
    Ingest a single transcript. Returns chunk count, or None if unchanged.

    Runs inside its own transaction so a failure rolls back cleanly instead of
    poisoning the session for the transcripts that follow.
    """
    github_path = entry.get("filename", "")
    if not github_path:
        raise ValueError("index entry has no filename")

    content = await fetcher.fetch_transcript(github_path)
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    existing = (
        await session.execute(select(Transcript).where(Transcript.github_path == github_path))
    ).scalar_one_or_none()

    if existing and existing.content_hash == content_hash:
        return None

    title = entry.get("title", "Untitled")
    publication_date = _parse_date(entry.get("date"))
    guest = entry.get("guest", "") or ""
    guests = [guest] if guest else []
    source_url = entry.get("post_url", "") or ""

    if existing:
        # Refresh in place: reusing the row keeps the unique github_path valid.
        await _drop_existing_chunks(session, collection, existing.id)
        existing.title = title
        existing.publication_date = publication_date
        existing.guests = guests
        existing.word_count = len(content.split())
        existing.content = content
        existing.content_hash = content_hash
        existing.extra_metadata = {"source_url": source_url}
        transcript = existing
    else:
        transcript = Transcript(
            id=uuid4(),
            github_path=github_path,
            title=title,
            publication_date=publication_date,
            guests=guests,
            word_count=len(content.split()),
            content=content,
            content_hash=content_hash,
            extra_metadata={"source_url": source_url},
        )
        session.add(transcript)

    await session.flush()

    chunks = chunk_text(
        content,
        min_tokens=settings.CHUNK_MIN_TOKENS,
        max_tokens=settings.CHUNK_MAX_TOKENS,
        overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
    )
    if not chunks:
        return 0

    embeddings = await _embed_in_batches(
        embedding_service, [c.content for c in chunks], settings.EMBEDDING_BATCH_SIZE
    )

    transcript_id = str(transcript.id)
    metadata_base = {
        "transcript_id": transcript_id,
        "transcript_title": title,
        # Key must match what VectorRetriever reads back. ChromaDB metadata
        # only accepts str/int/float/bool, so the date is stored as ISO text.
        "transcript_date": publication_date.isoformat() if publication_date else "",
        "guests": ", ".join(guests),
        "source_url": source_url,
        "github_path": github_path,
    }

    chroma_ids: List[str] = []
    metadatas: List[Dict[str, Any]] = []
    for chunk in chunks:
        chroma_ids.append(f"{transcript_id}_{chunk.chunk_index}")
        metadatas.append({**metadata_base, "chunk_index": chunk.chunk_index})

    await run_in_threadpool(
        collection.upsert,
        ids=chroma_ids,
        embeddings=embeddings,
        documents=[c.content for c in chunks],
        metadatas=metadatas,
    )

    session.add_all(
        [
            Chunk(
                id=uuid4(),
                transcript_id=transcript.id,
                chroma_id=chroma_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                token_count=chunk.token_count,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
            )
            for chunk, chroma_id in zip(chunks, chroma_ids)
        ]
    )

    await session.commit()
    return len(chunks)


async def _drop_existing_chunks(session, collection, transcript_id) -> None:
    """Remove a transcript's chunks from PostgreSQL and ChromaDB before reindexing."""
    stale_ids = (
        (await session.execute(select(Chunk.chroma_id).where(Chunk.transcript_id == transcript_id)))
        .scalars()
        .all()
    )
    if stale_ids:
        await run_in_threadpool(collection.delete, ids=list(stale_ids))

    await session.execute(delete(Chunk).where(Chunk.transcript_id == transcript_id))


async def _embed_in_batches(
    embedding_service: EmbeddingService, texts: List[str], batch_size: int
) -> List[List[float]]:
    """Embed in bounded batches so a long transcript cannot exhaust memory."""
    embeddings: List[List[float]] = []
    for start in range(0, len(texts), batch_size):
        embeddings.extend(await embedding_service.generate_embeddings(texts[start : start + batch_size]))
    return embeddings


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = asyncio.run(ingest_transcripts(limit=get_settings().INGEST_LIMIT))
    print(result)
