"""Script to run transcript ingestion from command line."""
import asyncio
import sys
from app.ingestion.pipeline import ingest_transcripts


async def main():
    """Run ingestion."""
    print("Starting transcript ingestion...")
    print("This will take 10-15 minutes for all 50 transcripts.\n")

    # Run ingestion (no limit = all transcripts)
    result = await ingest_transcripts(limit=None)

    print("\n" + "="*60)
    print("INGESTION COMPLETE")
    print("="*60)
    print(f"Transcripts processed: {result['transcripts_processed']}")
    print(f"Transcripts skipped:   {result['transcripts_skipped']}")
    print(f"Chunks created:        {result['chunks_created']}")

    if result['errors']:
        print(f"\n⚠️  Errors encountered: {len(result['errors'])}")
        for error in result['errors'][:5]:  # Show first 5 errors
            print(f"  - {error['transcript']}: {error['error']}")

    print("\n✅ Ready to answer questions!")

    return 0 if not result['errors'] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
