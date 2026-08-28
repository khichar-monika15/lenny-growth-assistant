# Architecture Document: The Lenny Growth Assistant

**Author:** Monika Kumari (khichar-monika15)  
**Date:** August 28, 2026

---

## System Overview

```
┌─────────────┐
│   Browser   │
│  (React)    │
└──────┬──────┘
       │ HTTP/SSE
       ▼
┌─────────────┐       ┌──────────────┐       ┌──────────────┐
│   FastAPI   │◄─────►│  PostgreSQL  │       │   ChromaDB   │
│   Backend   │       │   (Metadata) │       │   (Vectors)  │
└──────┬──────┘       └──────────────┘       └──────────────┘
       │
       ▼
┌─────────────────────────────┐
│   LLM Providers             │
│  ┌────────────┬──────────┐  │
│  │   Claude   │  Ollama  │  │
│  │   (Cloud)  │  (Local) │  │
│  └────────────┴──────────┘  │
└─────────────────────────────┘
```

**Data Flow:**
1. User query → React frontend
2. Frontend sends SSE request → FastAPI
3. Backend generates query embedding → Ollama
4. Backend retrieves chunks → ChromaDB (vector search)
5. Backend fetches chunk metadata → PostgreSQL
6. Backend assembles context → LLM (Claude or Ollama)
7. LLM streams response → Frontend via SSE
8. Frontend displays message + sources

---

## Database Schema

### PostgreSQL Tables

```sql
-- Sessions: Independent chat conversations
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) DEFAULT 'anonymous',
    title VARCHAR(255),
    model_provider VARCHAR(50) DEFAULT 'ollama',
    model_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

-- Messages: Conversation history
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]',  -- [{chunk_id, title, similarity, ...}]
    token_count INTEGER,
    model_provider VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_messages_session_id ON messages(session_id);

-- Transcripts: Source podcast episodes
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_path VARCHAR(500) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    publication_date VARCHAR(50),
    guests TEXT[],
    word_count INTEGER,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,  -- SHA256 for change detection
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- Chunks: Semantically chunked segments
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id UUID REFERENCES transcripts(id) ON DELETE CASCADE,
    chroma_id VARCHAR(255) UNIQUE NOT NULL,  -- Links to ChromaDB doc
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    start_char INTEGER,  -- Character offset for precise citation
    end_char INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_chunks_transcript_id ON chunks(transcript_id);
CREATE INDEX idx_chunks_chroma_id ON chunks(chroma_id);
```

**Why Dual Storage (PostgreSQL + ChromaDB)?**
- PostgreSQL: Relational metadata, full-text search, transactions
- ChromaDB: Fast vector similarity search
- Future: Migrate to pgvector for single-database simplicity

---

## API Specifications

### Chat Endpoints

#### `POST /api/v1/chat/stream`
**SSE streaming chat response**

**Request:**
```json
{
  "message": "What did Lenny say about product-market fit?",
  "session_id": "uuid-optional",
  "model_provider": "ollama"  // or "claude"
}
```

**Response (SSE stream):**
```
data: {"type": "retrieval_start"}

data: {"type": "sources", "sources": [
  {"transcript_title": "...", "similarity": 0.85, ...},
  ...
]}

data: {"type": "content_delta", "delta": "Product-market fit..."}
data: {"type": "content_delta", "delta": " is when..."}

data: [DONE]
```

**Error Response:**
```
data: {"type": "error", "error": "Ollama unavailable"}
```

#### `POST /api/v1/chat`
**Non-streaming chat (for testing)**

**Response:**
```json
{
  "message": "Product-market fit is...",
  "sources": [...],
  "usage": {"input_tokens": 150, "output_tokens": 200}
}
```

### Ship 30 Endpoint

#### `POST /api/v1/ship30/generate`
**Generate Ship 30 for 30 essay**

**Request:**
```json
{
  "topic": "Finding product-market fit",
  "word_count": 300,
  "hook_style": "question",  // question | stat | story | contrarian
  "model_provider": "claude"
}
```

**Response:**
```json
{
  "essay": "How do you know when...\n\n[Body]\n\n[CTA]",
  "word_count": 298,
  "target_word_count": 300,
  "sources": [...],
  "model_provider": "claude"
}
```

### Health Endpoints

#### `GET /health`
```json
{
  "status": "healthy",
  "environment": "development",
  "default_model": "ollama"
}
```

#### `GET /health/llm`
```json
{
  "ollama": "available",
  "anthropic": "configured"  // or "not_configured"
}
```

---

## Component Architecture

### Backend Layers

```
┌─────────────────────────────────────────┐
│          API Layer (FastAPI)            │
│  /api/v1/chat, /api/v1/ship30, /health  │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│         Service Layer                   │
│  ChatService, Ship30Service             │
└────────────────┬────────────────────────┘
                 │
      ┌──────────┴──────────┐
      │                     │
┌─────▼─────────┐    ┌──────▼──────────┐
│   RAG Layer   │    │   LLM Layer     │
│  Retriever    │    │  ClaudeProvider │
│  ContextAsm   │    │  OllamaProvider │
└───────────────┘    └─────────────────┘
      │                     │
┌─────▼─────────────────────▼─────────┐
│      Data Layer                     │
│  PostgreSQL, ChromaDB, Ollama API   │
└─────────────────────────────────────┘
```

**Dependency Flow:**
- API → Services (orchestration)
- Services → RAG + LLM (specialized logic)
- RAG/LLM → Data (storage & compute)

---

## RAG Pipeline

### Ingestion Flow

```
GitHub Repo
    ↓
Fetch Transcripts (GitHubFetcher)
    ↓
Parse Markdown + Metadata
    ↓
Semantic Chunking (800-1200 tokens, 200 overlap)
    ↓
Generate Embeddings (Ollama nomic-embed-text)
    ↓
Store in PostgreSQL (chunks table) + ChromaDB (vectors)
```

**Chunking Strategy:**
- Min tokens: 800, Max tokens: 1200, Overlap: 200
- Tokenizer: tiktoken (cl100k_base encoding)
- Respects paragraph boundaries (split on `\n\n` first)
- Tracks character offsets for precise citation

**Embedding Model:**
- `nomic-embed-text` via Ollama
- 768 dimensions
- Cosine similarity distance metric

### Retrieval Flow

```
User Query
    ↓
Generate Query Embedding
    ↓
ChromaDB Vector Search (top-k=10)
    ↓
Fetch Chunk Metadata from PostgreSQL
    ↓
Deduplicate Overlapping Chunks
    ↓
Sort by Similarity Score
    ↓
Fit Within Token Budget (4000 tokens)
    ↓
Format Context with Citations
```

**Context Assembly:**
```
[Source 1: "Rahul Vohra on PMF" (similarity: 0.87)]
Product-market fit is when your users would be very disappointed if...

[Source 2: "Lenny on Growth Loops" (similarity: 0.82)]
The best indicator of PMF is retention, not growth...

[Retrieved 8 chunks, 3,245 tokens]
```

---

## LLM Provider Abstraction

### Interface

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(messages, system_prompt, max_tokens, temperature) -> Dict
    
    @abstractmethod
    async def stream(messages, system_prompt, max_tokens, temperature) -> AsyncIterator
    
    @abstractmethod
    async def count_tokens(text: str) -> int
```

### Implementations

**ClaudeProvider:**
- Uses `anthropic` SDK directly (NOT LangChain)
- Model: `claude-3-5-sonnet-20241022`
- Streaming via `client.messages.stream()`

**OllamaProvider:**
- HTTP client to `http://ollama:11434`
- Model: `llama3.1:8b`
- Streaming via `/api/generate` endpoint

**Factory Pattern:**
```python
LLMProviderFactory.create_provider("claude", config) -> ClaudeProvider
LLMProviderFactory.create_provider("ollama", config) -> OllamaProvider
```

---

## Security Measures

### Artifact Rendering
**Problem:** Ship 30 essays may contain HTML/CSS that could execute scripts

**Solution:**
1. **DOMPurify Sanitization:** Remove `<script>`, event handlers, dangerous attributes
2. **Iframe Sandbox:** Render in `<iframe sandbox="allow-same-origin">` (no `allow-scripts`)
3. **CSP Headers:** `Content-Security-Policy: default-src 'self'`

**Code:**
```tsx
import DOMPurify from 'dompurify'

const sanitizedHTML = DOMPurify.sanitize(essayContent)
<iframe sandbox="allow-same-origin" srcDoc={sanitizedHTML} />
```

### Input Validation
- Pydantic models validate all request bodies
- Max message length: 2000 chars
- Word count range: 250-1250 (enforced)

### Database
- Parameterized queries (SQLAlchemy ORM)
- No user-controlled SQL (no raw queries from input)

### Environment Secrets
- `.env` in `.gitignore`
- Anthropic API key never logged or exposed in errors

---

## Deployment Topology

### Docker Compose Services

```yaml
services:
  postgres:      # Port 5432
  chromadb:      # Port 8000
  ollama:        # Port 11434
  backend:       # Port 8080
  frontend:      # Port 3000
```

**Health Check Flow:**
```
1. Postgres ready (pg_isready)
2. ChromaDB ready (heartbeat endpoint)
3. Ollama ready (API tags endpoint)
4. Backend ready (depends on 1-3, /health endpoint)
5. Frontend ready (depends on 4)
```

**Startup Sequence:**
```bash
./startup.sh
  → Create .env if missing
  → docker-compose up -d
  → Wait for Ollama
  → Pull models (llama3.1:8b, nomic-embed-text)
  → Wait for backend /health
  → Ingest transcripts (if data/transcripts/ has files)
  → Show URLs
```

---

## Performance Characteristics

### Latency Targets
- Vector search: <100ms (top-10 from 800 chunks)
- Embedding generation: <200ms per query
- LLM first token (Ollama): <500ms
- LLM first token (Claude): <1s
- End-to-end response: <5s (local), <10s (cloud)

### Throughput
- Single-user demo: No concurrency limits
- Database: 10 connection pool, 20 max overflow
- ChromaDB: In-memory mode, ~1000 QPS

### Scaling Considerations
**Current Bottlenecks:**
- Ollama: Single-threaded, CPU-bound
- ChromaDB: Single-node, no replication

**Future Optimizations:**
- Add Redis cache for frequent queries
- Batch embedding generation (10-20 at once)
- Migrate to pgvector for unified database
- Add GPU acceleration for Ollama

---

## Error Handling

### Fallback Strategy
```python
try:
    provider = get_provider("claude")
except APIKeyMissing:
    provider = get_provider("ollama")  # Fallback
    warnings.append("Using Ollama (Claude key not configured)")
```

### Retry Logic
- Ship 30 word count miss: Retry once with explicit feedback
- Embedding generation: No retry (fail fast)
- Database queries: Retry on connection error (max 3 attempts)

### User-Facing Errors
- "I don't have enough context to answer that question"
- "Ollama is unavailable. Try again or switch to Claude."
- "Essay generation failed. Please try a different topic."

---

## Future Architecture

### V2 Enhancements
1. **Hybrid Search:** Vector + keyword (PostgreSQL full-text)
2. **Query Classification:** Route questions to specialized prompts
3. **Conversation Memory:** Multi-turn context tracking
4. **Analytics:** Track popular questions, response quality
5. **pgvector Migration:** Single-database architecture

### Scaling Path
```
Current: Single-node all services
V2: Separate backend/database tiers
V3: Horizontal backend scaling + Redis cache
V4: Multi-region deployment
```

---

## Trade-Off Decisions

| Decision | Alternative | Rationale |
|----------|-------------|-----------|
| **ChromaDB** | pgvector | Faster MVP, designed for migration |
| **Dual Storage** | Single DB | Separation of concerns, performance |
| **Claude SDK** | LangChain | Assignment requirement, more control |
| **SSE** | WebSockets | Simpler, sufficient for one-way streaming |
| **Zustand** | Redux | Less boilerplate, better TypeScript |
| **Docker Compose** | Kubernetes | Simpler for single-node demo |
| **Session DB** | LocalStorage | Persistent across restarts, multi-device |

---

## Monitoring & Observability

### Current State (MVP)
- Logs: Python logging to stdout (JSON in production)
- Health checks: `/health`, `/health/llm`
- Metrics: None

### Post-Demo Plan
- Structured logging (JSON with trace IDs)
- Prometheus metrics (request latency, error rates)
- Distributed tracing (OpenTelemetry)
- Error tracking (Sentry)

---

## Testing Strategy

### Current Coverage
- Manual testing of critical paths
- Docker health checks verify services start

### Future Tests
1. **Unit Tests:** Chunker, context assembler, LLM providers
2. **Integration Tests:** API endpoints with TestClient
3. **E2E Tests:** Playwright for frontend flows
4. **Load Tests:** Locust for concurrent users

**Target:** >80% backend coverage, >60% frontend coverage
