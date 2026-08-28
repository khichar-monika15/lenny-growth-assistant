# Data Directory

This directory is for runtime data storage:

- `/transcripts/` - Downloaded podcast transcripts (created during ingestion)
- `/logs/` - Application logs (if file logging enabled)
- `/cache/` - Temporary cache files

**Note:** This directory is excluded from git via `.gitignore` and from the deployment package.
Files here are created at runtime and should not be committed to version control.

## Ingestion

To populate the database with transcripts:

```bash
docker compose exec backend python -m app.ingestion.pipeline
```

Or use the ingestion script:

```bash
docker compose exec backend python -m app.scripts.ingest_transcripts
```
