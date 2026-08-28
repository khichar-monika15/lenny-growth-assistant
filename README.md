# The Lenny Growth Assistant

An internal assistant that answers product and growth questions from Lenny's
Podcast transcripts, cites the episodes it drew from, writes Ship 30 for 30
essays, and renders Markdown and HTML artifacts in a sandboxed viewer beside
the chat.

Runs entirely on your machine. The demo uses Ollama and needs no API key.

**Author:** Monika Kumari ([khichar-monika15](https://github.com/khichar-monika15))
**Demo video:** [Watch the walkthrough](https://drive.google.com/drive/folders/1nEUu2DIuA-pRUdbAcvgDioIW5y804f_m?usp=sharing)

---

## Quick start

**Prerequisites:** Docker Desktop (with Compose), 8 GB RAM, 8 GB disk. Nothing
else. No Python, Node or API key needed.

On an 8 GB machine, give Docker Desktop at least 6 GB in **Settings →
Resources**; it defaults lower than people expect and the stack runs five
containers.

```bash
git clone https://github.com/khichar-monika15/lenny-growth-assistant.git
cd lenny-growth-assistant
./startup.sh
```

Then open **http://localhost:3000**.

`startup.sh` runs unattended and never prompts. It creates `.env` from
`.env.example`, starts all five services, pulls the two Ollama models, ingests
transcripts, and prints the URLs. First run takes roughly 10 to 20 minutes,
almost all of it downloading the 2 GB language model.

Ask something to confirm it works:

> What does Jen Abel say about closing enterprise deals?

You should get an answer with a **sources** row underneath naming real episodes.
If that row is missing, the index is empty; see [Troubleshooting](#troubleshooting).

### Options

```bash
INGEST_LIMIT=0 ./startup.sh    # ingest the full catalogue instead of 15 episodes
SKIP_INGEST=1 ./startup.sh     # start services only
```

### Manual start

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec backend python -m app.scripts.ingest_transcripts --limit 15
```

---

## What it does

**Grounded answers.** Questions are embedded, matched against transcript chunks
by cosine similarity, and answered only from what comes back. Chunks below the
similarity floor are discarded rather than shown as weak citations, and when
nothing clears the bar the assistant says so instead of answering from the
model's own memory. Every answer carries its sources, with guest, date, match
score and a link to the episode.

**Follow-up questions.** Each session keeps its own history, replayed to the
model on every turn. A short follow-up like "why does that matter?" also folds
in the previous turn when searching, since alone it has no meaning to embed.

**Ship 30 essays.** A dedicated skill encodes the Ship 30 for 30 method as
structured rules rather than one long prompt string: a hook taxonomy, voice and
formatting constraints, a section count derived from the target length, and a
word-count contract. Default 1,250 words, configurable from 250 to 1,250.

**Artifacts.** Ask for a document, checklist, one-pager or HTML page and it
renders in a viewer beside the chat, with preview and source tabs, copy and
download. Generated HTML is treated as hostile; see
[Security](#security-artifact-rendering).

**Model toggle.** Switch between local Ollama and cloud Claude in the header.
Live status is shown per provider, and if Claude is selected without an API key
the request falls back to Ollama and the UI says why.

---

## Architecture

```
                     ┌──────────────────────────────┐
  Browser  ─────────▶│  React + Vite (port 3000)    │
                     │  chat · artifact viewer      │
                     └──────────────┬───────────────┘
                                    │ SSE
                     ┌──────────────▼───────────────┐
                     │  FastAPI (port 8080)         │
                     │                              │
                     │  agent router                │
                     │    ├─ grounded answer        │
                     │    ├─ ship 30 essay          │
                     │    └─ artifact               │
                     │                              │
                     │  retrieval · providers       │
                     └───┬────────┬────────┬────────┘
                         │        │        │
              ┌──────────▼──┐ ┌───▼─────┐ ┌▼──────────────┐
              │ PostgreSQL  │ │ChromaDB │ │ Ollama        │
              │ sessions    │ │ vectors │ │ chat + embed  │
              │ messages    │ │         │ │               │
              │ transcripts │ └─────────┘ └───────────────┘
              └─────────────┘                    or
                                          Anthropic Claude
```

A turn flows: route to a skill → embed the query → search ChromaDB → assemble
context within a token budget → generate → persist the turn with its citations
→ stream back.

Full detail in **[architecture.md](architecture.md)**.

**Stack:** FastAPI, PostgreSQL 16, ChromaDB, Ollama, Anthropic SDK, React 18,
Vite, TypeScript, Docker Compose.

---

## Configuration

Copy `.env.example` to `.env`. Every value has a working local default, so the
stack runs unedited. The ones that matter most:

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(empty)* | Optional. Empty means local-only; Claude requests fall back to Ollama |
| `DEFAULT_MODEL` | `ollama` | Provider for requests that do not name one |
| `OLLAMA_CHAT_MODEL` | `llama3.2:3b` | Any Ollama chat model |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Changing this requires re-ingesting |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Raise on slower hardware |
| `INGEST_LIMIT` | `15` | Episodes to ingest. `0` means all |
| `MIN_SIMILARITY_SCORE` | `0.25` | Chunks below this are dropped, not cited |
| `RETRIEVAL_TOP_K` | `10` | Chunks fetched per query |
| `CONTEXT_MAX_TOKENS` | `4000` | Hard cap on assembled context |
| `BACKEND_PORT` etc. | standard | Remap if a port is already taken |

`.env` is gitignored. No secret is committed anywhere in this repository.

### Using Claude instead of Ollama

```bash
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
docker compose up -d backend
```

Then pick **Cloud · Claude** in the header. Embeddings still run locally through
Ollama, so the index does not change when you switch chat providers.

---

## API

Interactive docs at **http://localhost:8080/docs**.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/chat` | Send a message, wait for the full reply |
| `POST` | `/api/v1/chat/stream` | Same, streamed as SSE |
| `POST` | `/api/v1/sessions` | Start a session |
| `GET` | `/api/v1/sessions` | List sessions |
| `GET` | `/api/v1/sessions/{id}` | Session with full history |
| `GET` | `/api/v1/sessions/{id}/messages` | Messages only |
| `DELETE` | `/api/v1/sessions/{id}` | Delete a session and its messages |
| `POST` | `/api/v1/ship30/generate` | Generate an essay |
| `GET` | `/api/v1/ship30/hook-styles` | Available hook styles |
| `GET` | `/health` | Liveness |
| `GET` | `/health/db` | PostgreSQL |
| `GET` | `/health/retrieval` | ChromaDB and how many chunks are indexed |
| `GET` | `/health/llm` | Provider status and which models are pulled |

```bash
curl -s -X POST localhost:8080/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How do you get the first enterprise meeting?"}' | jq
```

Omit `session_id` and one is created; the response returns its id for follow-ups.

Errors are structured, never a stack trace:

```json
{
  "error": "model_unavailable",
  "detail": "Ollama has no model named 'llama3.2:3b'.",
  "hint": "Pull it with: ollama pull llama3.2:3b"
}
```

---

## Security: artifact rendering

Generated HTML is untrusted input. It is never inserted into the app's own DOM.
Three independent layers protect the viewer, so bypassing any one is not enough:

1. **DOMPurify** strips `<script>`, `<iframe>`, `<form>`, `<input>`, `<link>`,
   `<object>`, `<embed>`, every `on*` handler and `javascript:` URLs.
2. **A sandboxed iframe** with `sandbox=""` renders the result via `srcdoc`.
   Every capability is opt-in and none is granted, so scripting, forms, popups
   and navigation are disabled and the frame has an opaque origin with no access
   to the parent page.
3. **A Content Security Policy** of `default-src 'none'` inside that document
   blocks every network request, so nothing can call out even if it ran.

**Permitted:** structural markup, text, tables, lists, inline `<style>` and
`data:` images. **Blocked:** all scripting, all network access, all form input.
The viewer tells the user what it stripped rather than removing it silently.

Markdown takes a different path: `react-markdown` builds a React element tree
instead of setting `innerHTML`, and `rehype-raw` is deliberately not installed,
so HTML embedded in Markdown is inert by construction.

---

## Tests

```bash
docker compose exec backend python -m pytest       # 101 tests
cd frontend && npm test                            # 18 tests
cd frontend && npm run typecheck
```

Covering: chunker termination and boundaries, cosine scoring and the similarity
floor, context assembly within budget, agent routing in both directions, the
Ship 30 word-count contract, session persistence and cascade deletes, session
isolation, API contracts and validation, SSE ordering and guaranteed
termination, HTML sanitisation against concrete attack payloads, and SSE frame
reassembly.

Manual UI test plan in **[TESTING.md](TESTING.md)**.

---

## Troubleshooting

**Answers have no sources.** The index is empty.

```bash
curl -s localhost:8080/health/retrieval
docker compose exec backend python -m app.scripts.ingest_transcripts --limit 15
```

**"model_unavailable" or "Ollama has no model named…".**

```bash
docker compose exec ollama ollama list
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull nomic-embed-text
```

**First reply is very slow or times out.** The model loads into memory on the
first request. Raise `OLLAMA_TIMEOUT_SECONDS` in `.env` and restart the backend.

**A port is already in use.** Override it in `.env`: `BACKEND_PORT`,
`FRONTEND_PORT`, `POSTGRES_PORT`, `CHROMA_PORT`, `OLLAMA_PORT`.

**Something is unhealthy.** Each dependency has its own endpoint, so you do not
have to guess which one broke:

```bash
curl -s localhost:8080/health/db
curl -s localhost:8080/health/retrieval
curl -s localhost:8080/health/llm
docker compose ps
docker compose logs -f backend
```

Logs are JSON, one object per line, each tagged with the request id also
returned in the `X-Request-ID` header, so a single turn can be traced across
routing, retrieval, generation and persistence.

**Start completely fresh.**

```bash
docker compose down -v && ./startup.sh
```

---

## Development

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Frontend
cd frontend && npm install && npm run dev
```

The schema is applied from `backend/migrations/001_initial.sql` on first
Postgres start. There is no migration tool: for a schema change, edit that file
and recreate the volume with `docker compose down -v`.

### Extending it

**Add a skill:** subclass `Skill` in `backend/app/agent/skills/`, implement
`plan()` and optionally `finalize()`, register it in `AgentRouter.__init__` and
add its trigger patterns. Routing, retrieval, streaming and persistence work
unchanged.

**Add a model provider:** implement `BaseLLMProvider` in
`backend/app/llm/providers/`, then add a branch to `LLMProviderFactory`.

**Swap the vector store:** `backend/app/rag/retriever.py` and
`backend/app/rag/chroma.py` are the only modules that talk to ChromaDB.

---

## Documentation

- **[PRD.md](PRD.md)**, user, problem, success metrics, assumptions, scope, risks
- **[architecture.md](architecture.md)**, schema, endpoints, flows, routing, security, topology
- **[design.md](design.md)**, UI principles, states, responsive behaviour, accessibility
- **[TESTING.md](TESTING.md)**, manual test plan
- **[agent_transcripts/](agent_transcripts/)**, build logs, including what went wrong

---

## Project structure

```
backend/
  app/
    agent/          router and skills (grounded answer, ship30, artifact)
    api/v1/         endpoints, schemas, error translation
    ingestion/      GitHub fetcher, chunker, pipeline
    llm/            provider abstraction (Claude, Ollama)
    rag/            retriever, context assembler, Chroma client
    services/       chat orchestration, sessions, embeddings
  migrations/       SQL schema
  tests/            agent, api, ingestion, rag
frontend/
  src/
    components/     Chat, Artifacts, ModelToggle, Session
    hooks/          useChat (state and SSE)
    services/       API client and SSE parser
docker-compose.yml
startup.sh
```

---

## Acknowledgements

[Lenny's Podcast](https://www.lennysnewsletter.com/podcast) for the transcripts,
[Ollama](https://ollama.ai) for local inference, and
[Oogway Labs](https://oogwaylabs.com) for the assignment.
