"""Transcript ingestion pipeline: fetch → chunk → embed → store."""
import hashlib
import asyncio
from typing import List, Dict, Any
from datetime import datetime, date
from uuid import uuid4

from sqlalchemy import select

from app.database import get_session
from app.models import Transcript, Chunk
from app.ingestion.github_fetcher import GitHubFetcher
from app.ingestion.chunker import chunk_text
from app.services.embedding_service import EmbeddingService
from app.config import get_settings

import chromadb


async def ingest_transcripts(limit: int = None) -> Dict[str, Any]:
    """
    Ingest transcripts from GitHub.

    Args:
        limit: Optional limit on number of transcripts to process

    Returns:
        Dict with ingestion statistics
    """
    settings = get_settings()
    stats = {
        "transcripts_processed": 0,
        "transcripts_skipped": 0,
        "chunks_created": 0,
        "errors": []
    }

    # Initialize services
    fetcher = GitHubFetcher()
    embedding_service = EmbeddingService()

    # ChromaDB client
    chroma_client = chromadb.HttpClient(
        host=settings.CHROMADB_HOST,
        port=settings.CHROMADB_PORT
    )

    # Get or create collection
    try:
        collection = chroma_client.get_collection(name="lenny_transcripts")
    except Exception:
        collection = chroma_client.create_collection(
            name="lenny_transcripts",
            metadata={"description": "Lenny's Podcast transcript chunks"}
        )

    try:
        # Fetch transcript index
        index_data = await fetcher.fetch_index()
        index = index_data.get("podcasts", [])

        if limit:
            index = index[:limit]

        async with get_session() as session:
            for entry in index:
                try:
                    # Extract metadata
                    title = entry.get("title", "Untitled")
                    file_path = entry.get("filename", "")
                    date_str = entry.get("date")
                    publication_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
                    guest = entry.get("guest", "")
                    guests = [guest] if guest else []

                    # Fetch transcript content
                    content = await fetcher.fetch_transcript(file_path)

                    # Calculate content hash for change detection
                    content_hash = hashlib.sha256(content.encode()).hexdigest()

                    # Check if already ingested with same content
                    stmt = select(Transcript).where(Transcript.github_path == file_path)
                    result = await session.execute(stmt)
                    existing_row = result.scalar_one_or_none()

                    if existing_row and existing_row.content_hash == content_hash:
                        stats["transcripts_skipped"] += 1
                        continue

                    # Create transcript record
                    transcript_id = str(uuid4())
                    transcript = Transcript(
                        id=transcript_id,
                        github_path=file_path,
                        title=title,
                        publication_date=publication_date,
                        guests=guests,
                        word_count=len(content.split()),
                        content=content,
                        content_hash=content_hash
                    )

                    session.add(transcript)
                    await session.flush()

                    # Chunk the content
                    chunks = chunk_text(
                        content,
                        min_tokens=settings.CHUNK_MIN_TOKENS,
                        max_tokens=settings.CHUNK_MAX_TOKENS,
                        overlap_tokens=settings.CHUNK_OVERLAP_TOKENS
                    )

                    # Batch process chunks
                    chunk_texts = [c.content for c in chunks]
                    embeddings = await embedding_service.generate_embeddings(chunk_texts)

                    # Store chunks
                    for chunk_obj, embedding in zip(chunks, embeddings):
                        chunk_id = str(uuid4())
                        chroma_id = f"{transcript_id}_{chunk_obj.chunk_index}"

                        # Store in ChromaDB
                        collection.add(
                            ids=[chroma_id],
                            embeddings=[embedding],
                            documents=[chunk_obj.content],
                            metadatas=[{
                                "transcript_id": transcript_id,
                                "transcript_title": title,
                                "publication_date": publication_date or "",
                                "guests": ",".join(guests) if guests else "",
                                "chunk_index": chunk_obj.chunk_index
                            }]
                        )

                        # Store in PostgreSQL
                        chunk_record = Chunk(
                            id=chunk_id,
                            transcript_id=transcript_id,
                            chroma_id=chroma_id,
                            chunk_index=chunk_obj.chunk_index,
                            content=chunk_obj.content,
                            token_count=chunk_obj.token_count,
                            start_char=chunk_obj.start_char,
                            end_char=chunk_obj.end_char
                        )
                        session.add(chunk_record)
                        stats["chunks_created"] += len(chunks)

                    await session.commit()
                    stats["transcripts_processed"] += 1

                    print(f"✓ Ingested: {title} ({len(chunks)} chunks)")

                except Exception as e:
                    stats["errors"].append({
                        "transcript": entry.get("title", "Unknown"),
                        "error": str(e)
                    })
                    print(f"✗ Error ingesting {entry.get('title')}: {e}")
                    continue

    finally:
        await fetcher.close()
        await embedding_service.close()

    return stats


if __name__ == "__main__":
    # Run ingestion
    result = asyncio.run(ingest_transcripts(limit=1))  # Test with 1 transcript
    print("\nIngestion complete:")
    print(f"- Processed: {result['transcripts_processed']}")
    print(f"- Skipped: {result['transcripts_skipped']}")
    print(f"- Chunks created: {result['chunks_created']}")
    if result['errors']:
        print(f"- Errors: {len(result['errors'])}")
