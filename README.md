# The Lenny Growth Assistant

A full-stack AI-powered RAG application that answers product and growth questions grounded in Lenny's Podcast transcripts, generates Ship 30 for 30 style essays, and renders artifacts in-app.

**Built for:** Oogway Labs Forward Deployed Engineer Take-Home Assignment  
**Author:** Monika Kumari ([khichar-monika15](https://github.com/khichar-monika15))  
**Demo video:** [Watch the walkthrough](https://drive.google.com/drive/folders/1nEUu2DIuA-pRUdbAcvgDioIW5y804f_m?usp=sharing)

## Features

✨ **RAG-Powered Q&A** - Ask questions, get answers grounded in 50+ Lenny's Podcast transcripts with source citations  
💬 **Conversational Chat** - Session-based chat with streaming responses  
📝 **Ship 30 Essay Generator** - Generate 250-1250 word essays in Ship 30 for 30 style  
🎨 **Artifact Viewer** - Render Markdown/HTML artifacts securely in-app  
🔄 **Model Toggle** - Switch between Anthropic Claude (cloud) and Ollama (local)  
🐳 **One-Command Setup** - Docker Compose orchestration for instant deployment

## Quick Start

### Prerequisites

- Docker Desktop (with Docker Compose)
- 8GB+ RAM (for Ollama models)
- 10GB+ free disk space

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/khichar-monika15/lenny-growth-assistant.git
cd lenny-growth-assistant
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env if you want to use Anthropic Claude (add ANTHROPIC_API_KEY)
# For demo, Ollama works out of the box
```

3. **Start the application**
```bash
chmod +x startup.sh
./startup.sh
```

This will:
- Pull required Docker images
- Download Ollama models (llama3.1:8b, nomic-embed-text)
- Start all services (Postgres, ChromaDB, Ollama, Backend, Frontend)
- Ingest Lenny's podcast transcripts
- Launch the app at http://localhost:3000

### Manual Start (if startup.sh fails)

```bash
# Start all services
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Pull Ollama models
docker-compose exec ollama ollama pull llama3.1:8b
docker-compose exec ollama ollama pull nomic-embed-text

# Ingest transcripts (first time only)
docker-compose exec backend python -m app.scripts.ingest_transcripts

# Check logs
docker-compose logs -f backend
```

## Usage

### Web Interface

Open http://localhost:3000

1. **Ask a question:** "What did Lenny say about product-market fit?"
2. **View sources:** Click source citations to see transcript details
3. **Generate essay:** Click "Generate Ship 30" and enter a topic
4. **Switch models:** Use the model toggle in the header

### API Documentation

Interactive API docs: http://localhost:8080/docs

Key endpoints:
- `POST /api/v1/sessions` - Create chat session
- `POST /api/v1/sessions/{id}/messages/stream` - Send message (SSE)
- `POST /api/v1/ship30/generate` - Generate Ship 30 essay
- `GET /api/health` - Health check

## Architecture

### Tech Stack

**Backend:**
- FastAPI (Python 3.11)
- PostgreSQL (sessions, messages, transcripts)
- ChromaDB (vector embeddings)
- Anthropic Claude SDK
- Ollama (local LLMs)

**Frontend:**
- React 18 + Vite + TypeScript
- Zustand (state management)
- Server-Sent Events (SSE streaming)
- DOMPurify + Sandboxed iframes (artifact security)

**Deployment:**
- Docker Compose
- 5 services: Postgres, ChromaDB, Ollama, Backend, Frontend

### Data Flow

```
User Query
    ↓
FastAPI Backend
    ↓
RAG Retrieval (ChromaDB vector search → PostgreSQL metadata)
    ↓
LLM Generation (Claude SDK or Ollama)
    ↓
SSE Stream → React Frontend
    ↓
Display: Chat + Sources + Artifact Viewer
```

See [architecture.md](architecture.md) for detailed architecture documentation.

## Development

### Backend Development

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8080
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### Running Tests

**Backend:**
```bash
cd backend
pytest
```

**Frontend:**
```bash
cd frontend
npm test
```

## Troubleshooting

### Ollama not starting

```bash
# Check Ollama status
docker-compose logs ollama

# Restart Ollama
docker-compose restart ollama

# Verify models are pulled
docker-compose exec ollama ollama list
```

### Frontend can't connect to backend

```bash
# Check backend health
curl http://localhost:8080/health

# Check backend logs
docker-compose logs backend

# Verify CORS settings in .env
```

### Transcript ingestion failed

```bash
# Check ingestion logs
docker-compose exec backend python -m app.scripts.ingest_transcripts

# Verify GitHub repo is accessible
curl https://api.github.com/repos/LennysNewsletter/lennys-newsletterpodcastdata

# Check database connection
docker-compose exec postgres psql -U lenny -d lenny -c "SELECT COUNT(*) FROM transcripts;"
```

### ChromaDB connection issues

```bash
# Check ChromaDB health
curl http://localhost:8000/api/v1/heartbeat

# Restart ChromaDB
docker-compose restart chromadb
```

## Documentation

- [PRD.md](PRD.md) - Product Requirements Document
- [architecture.md](architecture.md) - Technical Architecture
- [design.md](design.md) - UI/UX Design Decisions
- [TESTING.md](TESTING.md) - Manual Test Plan

## Project Structure

```
lenny-growth-assistant/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── ingestion/       # Transcript ingestion
│   │   ├── rag/             # RAG retrieval system
│   │   ├── llm/             # LLM providers
│   │   ├── services/        # Business logic
│   │   ├── models/          # Database models
│   │   └── main.py          # FastAPI app
│   ├── migrations/          # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── store/           # Zustand store
│   │   └── services/        # API client
│   ├── package.json
│   └── Dockerfile.dev
├── data/
│   └── transcripts/         # Lenny's podcast transcripts
├── docs/                    # Documentation
├── docker-compose.yml
├── startup.sh
└── README.md
```

## Contributing

This is a take-home assignment project. Not accepting contributions.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- [Lenny's Podcast](https://www.lennysnewsletter.com/podcast) for the transcripts
- [Oogway Labs](https://oogwaylabs.com) for the opportunity
- [Anthropic](https://www.anthropic.com) for Claude
- [Ollama](https://ollama.ai) for local LLM inference

---

**Questions?** Open an issue or contact Monika at [GitHub](https://github.com/khichar-monika15)
