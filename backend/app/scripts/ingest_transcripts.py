"""
Run transcript ingestion from the command line.

    python -m app.scripts.ingest_transcripts            # uses INGEST_LIMIT
    python -m app.scripts.ingest_transcripts --limit 5
    python -m app.scripts.ingest_transcripts --all
"""
import argparse
import asyncio
import sys

from app.config import get_settings
from app.ingestion.pipeline import ingest_transcripts
from app.logging_config import configure_logging


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Ingest Lenny's Podcast transcripts")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--limit",
        type=int,
        default=settings.INGEST_LIMIT,
        help=f"Number of transcripts to ingest (default: {settings.INGEST_LIMIT})",
    )
    group.add_argument("--all", action="store_true", help="Ingest the full catalogue")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    configure_logging(get_settings().LOG_LEVEL)

    limit = None if args.all else (args.limit or None)
    print(f"Ingesting {'all' if limit is None else limit} transcripts...", flush=True)

    result = await ingest_transcripts(limit=limit)

    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"Transcripts processed: {result['transcripts_processed']}")
    print(f"Transcripts skipped:   {result['transcripts_skipped']}")
    print(f"Chunks created:        {result['chunks_created']}")

    if result["errors"]:
        print(f"\nErrors: {len(result['errors'])}")
        for error in result["errors"][:5]:
            print(f"  - {error['transcript']}: {error['error']}")
        return 1

    print("\nReady to answer questions.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
