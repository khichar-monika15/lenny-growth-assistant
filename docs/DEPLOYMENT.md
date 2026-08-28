# Deployment Guide

## Prerequisites
- Docker & Docker Compose
- 8GB+ RAM (for Ollama models)
- 10GB+ disk space

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/khichar-monika15/lenny-growth-assistant.git
cd lenny-growth-assistant

# 2. Start all services
docker compose up -d

# 3. Pull Ollama models (one-time, 10-15 min)
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull nomic-embed-text

# 4. Verify services
curl http://localhost:8080/health
curl http://localhost:3000

# 5. Test chat
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Test"}'
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | React UI |
| Backend | 8080 | FastAPI server |
| PostgreSQL | 5432 | Database |
| ChromaDB | 8000 | Vector store |
| Ollama | 11434 | Local LLM |

## Configuration

Create `.env` file (use `.env.example` as template):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://lenny:lenny_dev_password@postgres:5432/lenny

# LLM Providers
ANTHROPIC_API_KEY=  # Optional
OLLAMA_BASE_URL=http://ollama:11434
DEFAULT_MODEL=ollama

# ChromaDB
CHROMA_HOST=chromadb
CHROMA_PORT=8000
```

## Production Considerations

1. **Security:**
   - Change default database credentials
   - Enable API authentication
   - Use HTTPS/TLS
   - Set CORS origins

2. **Scaling:**
   - Use managed PostgreSQL (Supabase/Railway)
   - Consider pgvector instead of ChromaDB
   - Add Redis for caching
   - Horizontal scaling for backend

3. **Monitoring:**
   - Add Prometheus metrics
   - Set up error tracking (Sentry)
   - Enable structured logging
   - Health check endpoints

4. **Data:**
   - Run ingestion pipeline
   - Set up backup schedule
   - Monitor vector store size

## Troubleshooting

**Models not found:**
```bash
docker compose exec ollama ollama list
# Re-pull if missing
```

**Backend crashes:**
```bash
docker compose logs backend --tail=50
# Check ChromaDB connection
docker compose restart chromadb backend
```

**Frontend blank:**
```bash
docker compose logs frontend
# Rebuild if needed
docker compose up -d --build frontend
```
