# Architecture

How The Lenny Growth Assistant is put together, and why each piece is the shape
it is.

---

## 1. System overview

Five services, one Compose file, no external dependency beyond the public
transcript repository.

```
┌─────────────────────────────────────────────────────────────────┐
│ Browser                                                         │
│   React 18 + Vite + TypeScript          :3000                   │
│   chat · session sidebar · model toggle · artifact viewer       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP + Server-Sent Events
┌──────────────────────────▼──────────────────────────────────────┐
│ FastAPI                                  :8080                  │
│                                                                 │
│  api/v1        contracts, validation, error translation         │
│  services      chat orchestration, sessions, embeddings         │
│  agent         intent router → skills                           │
│  rag           retriever, context assembler                     │
│  llm           provider abstraction                             │
│  ingestion     fetch, chunk, embed, index                       │
└────────┬───────────────┬───────────────┬────────────────────────┘
         │               │               │
┌────────▼──────┐ ┌──────▼──────┐ ┌──────▼─────────────────┐
│ PostgreSQL 16 │ │  ChromaDB   │ │ Ollama        :11434   │
│        :5432  │ │      :8000  │ │ llama3.2:3b            │
│ sessions      │ │ 768-dim     │ │ nomic-embed-text       │
│ messages      │ │ cosine HNSW │ └────────────────────────┘
│ transcripts   │ │             │              or
│ chunks        │ └─────────────┘ ┌────────────────────────┐
└───────────────┘                 │ Anthropic Claude (API) │
                                  └────────────────────────┘
```

**Why two datastores.** PostgreSQL is the system of record: sessions, messages,
transcripts, chunk text and offsets. ChromaDB holds only vectors and the
metadata needed to render a citation. Chunk text is duplicated into Chroma so a
retrieval needs one round trip rather than a vector search followed by a
Postgres fan-out on every turn. Postgres remains the source of truth, and the
index can be rebuilt from it.

---

## 2. Database schema

Applied from `backend/migrations/001_initial.sql` on first Postgres start.

```sql
sessions
  id                UUID PK
  user_id           VARCHAR(255)  DEFAULT 'anonymous'
  title             VARCHAR(255)              -- derived from first message
  model_provider    VARCHAR(50)
  model_name        VARCHAR(100)
  is_active         BOOLEAN       DEFAULT true
  created_at        TIMESTAMPTZ
  updated_at        TIMESTAMPTZ               -- trigger-maintained
  metadata          JSONB         DEFAULT '{}'

messages
  id                UUID PK
  session_id        UUID FK → sessions(id) ON DELETE CASCADE
  role              VARCHAR(20)   NOT NULL    -- 'user' | 'assistant'
  content           TEXT          NOT NULL
  sources           JSONB         DEFAULT '[]'  -- citations as rendered
  token_count       INTEGER
  model_provider    VARCHAR(50)               -- which model actually answered
  created_at        TIMESTAMPTZ
  metadata          JSONB         DEFAULT '{}' -- intent, routing reason, artifact

transcripts
  id                UUID PK
  github_path       VARCHAR(500)  UNIQUE NOT NULL
  title             VARCHAR(500)  NOT NULL
  publication_date  DATE
  guests            TEXT[]
  word_count        INTEGER
  content           TEXT          NOT NULL    -- full source, for reindexing
  content_hash      VARCHAR(64)   NOT NULL    -- SHA-256, drives refresh
  created_at        TIMESTAMPTZ
  updated_at        TIMESTAMPTZ
  metadata          JSONB                     -- source_url

chunks
  id                UUID PK
  transcript_id     UUID FK → transcripts(id) ON DELETE CASCADE
  chroma_id         VARCHAR(255)  UNIQUE NOT NULL   -- join key to the vector store
  chunk_index       INTEGER       NOT NULL
  content           TEXT          NOT NULL
  token_count       INTEGER       NOT NULL
  start_char        INTEGER                   -- exact offset into transcripts.content
  end_char          INTEGER
  created_at        TIMESTAMPTZ
  metadata          JSONB
  UNIQUE (transcript_id, chunk_index)
```

Indexed: `sessions(user_id)`, `sessions(created_at DESC)`,
`messages(session_id)`, `messages(created_at DESC)`, `chunks(transcript_id)`,
`chunks(chroma_id)`, `transcripts(publication_date DESC)`.

**Notes on two decisions.**

`metadata` is a reserved attribute on SQLAlchemy declarative models, so the
column is mapped as `extra_metadata = Column("metadata", JSONB)`. The database
column keeps its natural name; only the Python attribute differs.

`messages.sources` stores citations as they were rendered, not as a foreign key
to `chunks`. History should show what the user was actually shown, even after
the index is rebuilt and chunk ids change.

### ChromaDB collection

| Property | Value |
|---|---|
| Name | `lenny_transcripts` |
| Distance | **cosine**, set at creation via `hnsw:space` |
| Dimensions | 768 (`nomic-embed-text`) |
| Document | chunk text |
| Metadata | `transcript_id`, `transcript_title`, `transcript_date`, `guests`, `source_url`, `github_path`, `chunk_index` |

Cosine is not the default. ChromaDB falls back to squared L2, whose distances
are unbounded, and the `1 - distance` conversion to a similarity score is only
meaningful for cosine. This was a live bug: scores were being computed against
an L2 collection. The space is now set explicitly at creation and asserted in
tests. Chroma metadata accepts only `str`/`int`/`float`/`bool`, so dates are
stored as ISO strings and guests as a comma-joined string.

---

## 3. Component boundaries

| Layer | Package | Responsibility | Depends on |
|---|---|---|---|
| API | `app/api/v1` | Contracts, validation, error translation | services, agent |
| Orchestration | `app/services/chat_service` | One turn end to end | agent, rag, llm, sessions |
| Persistence | `app/services/session_service` | Sessions and messages | models, database |
| Agent | `app/agent` | Intent routing, skills | rag types only |
| Retrieval | `app/rag` | Vector search, context assembly | chroma |
| Models | `app/llm` | Provider abstraction | none |
| Ingestion | `app/ingestion` | Fetch, chunk, embed, index | rag, models, database |

The rules that keep this honest:

- **Skills never perform I/O.** A skill receives assembled context and returns a
  prompt plan; `ChatService` does the retrieving, calling and persisting. So
  every skill streams and persists identically, and skills are unit-testable
  with no database, no Chroma and no model.
- **One orchestration path.** Streaming and non-streaming share `_prepare` and
  `_persist`. They cannot drift, which is what previously let the non-streaming
  endpoint ship with no error handling at all.
- **Providers are interchangeable.** Nothing above `app/llm` branches on which
  model is in use.
- **One module owns the vector store.** Swapping ChromaDB for pgvector touches
  `rag/chroma.py` and `rag/retriever.py`.

---

## 4. Ingestion

Source: the public `LennysNewsletter/lennys-newsletterpodcastdata` repository,
fetched over HTTPS. Nothing is cloned or copied by hand.

```
index.json (50 episodes)
    │
    ├─ for each entry: filename, title, date, guest, post_url
    │
    ▼
fetch markdown ──▶ SHA-256 ──▶ unchanged? ──yes──▶ skip
    │                              │
    │                              no
    ▼                              ▼
paragraph-aligned chunking     update in place,
800 to 1200 tokens, 200 overlap   delete stale chunks
    │                          from both stores
    ▼
embed in batches of 16 (nomic-embed-text, bounded concurrency)
    │
    ├──▶ ChromaDB: upsert vectors + citation metadata
    └──▶ PostgreSQL: chunk rows with exact character offsets
```

### Chunking

Chunks are packed from **whole paragraphs** up to the token budget, so a chunk
rarely cuts mid-thought and reads as a quotable passage. A paragraph larger than
the budget is bisected on the best available boundary: paragraph break, then
sentence end, then whitespace. Character offsets are exact slices of the source,
so a citation can be traced to its position in the original transcript.

Two invariants are enforced and tested:

- **Forward progress.** The cursor always advances. The original implementation
  computed `start = end - overlap`, which moved backwards once a document's tail
  was shorter than the overlap, so `chunk_text()` never returned on any real
  transcript. This emptied the knowledge base entirely and hung the test suite.
- **Hard token ceiling.** No chunk exceeds `max_tokens`, verified against the
  true tokenisation of the assembled slice rather than the sum of its parts,
  because tokenisation is not additive across boundaries.

Typical result: ~24 chunks per episode, ~0.03 s per transcript.

### Refresh

`content_hash` drives it. Unchanged transcripts are skipped. A changed one is
updated **in place** and its old chunks are deleted from Postgres and Chroma
before reindexing. The earlier version inserted a new row with the same
`github_path`, which violated the unique constraint and orphaned vectors.

Each transcript runs in its own transaction, so one failure rolls back cleanly
instead of poisoning the run.

```bash
docker compose exec backend python -m app.scripts.ingest_transcripts --limit 15
docker compose exec backend python -m app.scripts.ingest_transcripts --all
```

---

## 5. Retrieval

```
query text
    │
    ▼  nomic-embed-text
768-dim vector
    │
    ▼  ChromaDB, cosine, top-k = 10 (15 for essays, 12 for artifacts)
candidate chunks + distances
    │
    ▼  similarity = 1 - distance, clamped to 0..1
drop anything below MIN_SIMILARITY_SCORE (0.25)
    │
    ▼  ContextAssembler
sort by score, deduplicate, pack to CONTEXT_MAX_TOKENS (4000)
prefix each with [Source n: title | with guest | date]
    │
    ▼
context block + structured source list
```

The token budget is a hard limit measured with `tiktoken`, not a
characters-divided-by-four estimate. An over-budget chunk is skipped rather than
truncated mid-sentence, so smaller later chunks can still fit. The single
exception: if the best chunk alone exceeds the budget it is still included,
because one source beats none.

**Failure behaviour is distinguished, deliberately.** An empty index and an
unreachable ChromaDB are different events. The retriever used to swallow every
exception and return `[]`, which made an outage indistinguishable from "nothing
matched" and produced a confident, ungrounded answer. Now:

| Condition | Behaviour |
|---|---|
| Index empty | Empty context; the skill tells the user it cannot answer |
| No chunk clears the floor | Same, logged with the query |
| ChromaDB unreachable | `VectorStoreUnavailable` → HTTP 503 with a hint; the stream reports it |
| Embedding model missing | `EmbeddingError` → HTTP 503 naming the pull command |

---

## 6. Agent layer and routing

### Why this shape

The brief names the Claude Agent SDK. This implementation uses the Anthropic SDK
directly behind a provider abstraction, and puts the agent behaviour, skill
boundaries, routing, grounding, in the application layer.

The reason is the demo requirement. Ollama is mandatory for the demo, and the
Claude Agent SDK is Anthropic-only; adopting it would mean the local demo path
had no agent layer at all, or two divergent implementations. One agent layer
that works identically against both providers was the better trade, and it keeps
routing testable without a network call. The cost is that Anthropic's built-in
tool loop and server-side tool execution are not used; nothing here needs them,
since the skills are prompt-shaping rather than tool-calling.

### Routing

```
message
  │
  ├─ forced_skill given?  ──yes──▶ that skill        (used by /ship30/generate)
  │
  ├─ matches an essay pattern?     ──▶ Ship30Skill    + extracted topic
  │     "write an essay", "ship 30", "atomic essay", "draft a post"
  │
  ├─ matches a document pattern?   ──▶ ArtifactSkill  + detected format
  │     "create a one-pager", "make an HTML page", "checklist", "template"
  │
  └─ otherwise                     ──▶ GroundedAnswerSkill
```

Routing is **rule-based, not model-based**. An LLM classifier would add a full
round trip to every turn, which is painful on local hardware, and would make
routing non-deterministic and awkward to test. The patterns are high-precision:
they match explicit requests to *write something*, and everything else falls
through to grounded answers, which is the safe default. Every route records why
it fired, and the reason is persisted on the message.

The limit is honest: a request phrased unusually ("could you put my thinking
into a shareable format?") routes to a normal answer. The `skill` field on
`/api/v1/chat` is the escape hatch.

### Skills

| Skill | Owns | top-k | Output |
|---|---|---|---|
| `grounded_answer` | Citation-bound Q&A, refusal when unsupported | 10 | Text |
| `ship30_essay` | Ship 30 method, word-count contract | 15 | Text + Markdown artifact |
| `artifact` | Standalone documents | 12 | Text + Markdown/HTML artifact |

Each implements `plan(context) → SkillPlan` and optionally
`finalize(text, context) → SkillResult`.

**Ship 30 as an encoded skill.** The brief asks for the method encoded rather
than an unstructured prompt. The skill holds the rules as addressable data, a
hook taxonomy (`question`, `stat`, `story`, `contrarian`), six voice principles,
five formatting rules, a section count derived from the target length, and a
tolerance band, and composes the prompt from them. Each rule is testable on its
own, and the token budget is computed from the word target (~2.2 tokens/word)
rather than fixed, which is what previously truncated long essays.

---

## 7. Model configuration and toggle

```python
class BaseLLMProvider(ABC):
    async def generate(messages, system_prompt, max_tokens, temperature) -> dict
    def stream(messages, system_prompt, max_tokens, temperature) -> AsyncIterator[dict]
    async def count_tokens(text) -> int
    async def aclose() -> None
```

Both providers emit the same event shapes, so `ChatService` never branches on
which model is running.

| | Claude | Ollama |
|---|---|---|
| Transport | `anthropic` SDK | HTTP to `/api/chat` |
| Auth | `ANTHROPIC_API_KEY` | none |
| Errors | Typed SDK exceptions | Status codes, mapped |

Ollama uses `/api/chat`, not `/api/generate`. The earlier code flattened
messages into a `"User:/Assistant:"` string, which bypasses the model's own chat
template and measurably degrades instruction following on chat-tuned models.

**Selection and fallback**, all in `resolve_provider()`:

1. Explicit `model_provider` on the request, else `DEFAULT_MODEL`.
2. Claude requested with no API key → fall back to Ollama and record the reason.
3. The reason is returned as `fallback_reason` and shown in the UI.

Falling back rather than failing keeps the mandatory local demo working when no
key is configured, and never silently pretends a cloud model answered. Provider
failures are normalised to `LLMUnavailable` and `LLMTimeout`, so a missing model,
a rejected key and a rate limit are distinguishable by the caller.

---

## 8. API

Contracts are Pydantic models in `app/api/v1/schemas.py`; OpenAPI is generated
at `/docs`.

| Method | Path | Success | Notes |
|---|---|---|---|
| `POST` | `/api/v1/chat` | 200 | Creates a session if none given |
| `POST` | `/api/v1/chat/stream` | 200 | `text/event-stream` |
| `POST` | `/api/v1/sessions` | 201 | |
| `GET` | `/api/v1/sessions` | 200 | Newest first |
| `GET` | `/api/v1/sessions/{id}` | 200 | With messages |
| `GET` | `/api/v1/sessions/{id}/messages` | 200 | |
| `DELETE` | `/api/v1/sessions/{id}` | 204 | Cascades |
| `POST` | `/api/v1/ship30/generate` | 200 | |
| `GET` | `/api/v1/ship30/hook-styles` | 200 | |
| `GET` | `/health`, `/health/db`, `/health/retrieval`, `/health/llm` | 200 / 503 | |

**Validation.** Message length 1 to 8000, `word_count` 250 to 1250, `hook_style`
against the known set, UUIDs coerced by path type. Invalid input is 422 before
any work happens.

**Errors.** One translation layer maps domain exceptions to stable codes:

```json
{ "error": "model_timeout",
  "detail": "The model took too long to respond.",
  "hint": "Local models are slow on first load. Retry, or raise OLLAMA_TIMEOUT_SECONDS." }
```

`session_not_found` 404 · `invalid_request` 400 · `vector_store_unavailable`,
`embedding_unavailable`, `model_unavailable` 503 · `model_timeout` 504 ·
`internal_error` 500. 5xx detail is logged, never returned.

**SSE contract.**

```
session        session_id, intent, provider, model, fallback_reason
sources        citations, retrieval_error
content_delta  incremental text  (repeats)
artifact       when a skill produced one
message_stop   usage, metadata
[DONE]         always sent, including after an error
error          code, detail, hint  (on failure, before [DONE])
```

`[DONE]` in a `finally` block matters: the previous implementation emitted an
error event and stopped, and the client waited forever.

---

## 9. Security

**Artifact rendering** is the main surface, and is defended in three independent
layers so bypassing one is insufficient:

1. **DOMPurify** strips `<script>`, `<iframe>`, `<form>`, `<input>`, `<link>`,
   `<object>`, `<embed>`, `<base>`, `<meta>`, every `on*` handler, and
   `javascript:` URLs.
2. **`<iframe sandbox="" srcdoc=...>`**, an empty sandbox grants nothing, so
   scripting, forms, popups, pointer lock and top-level navigation are disabled
   and the frame gets an opaque origin with no access to the parent.
3. **CSP `default-src 'none'`** inside that document blocks every network
   request, so nothing can exfiltrate even if it executed.

Layers 2 and 3 hold independently of layer 1: an unsanitised script cannot run
in a frame where scripting is disabled at all. Permitted: structural markup,
text, tables, lists, inline `<style>`, `data:` images. Blocked: scripting,
network, form input. Removals are reported in the UI rather than silent.

Markdown never goes through this path. `react-markdown` builds a React element
tree instead of setting `innerHTML`, and `rehype-raw` is deliberately absent, so
embedded HTML is inert by construction.

**Elsewhere:** parameterised queries only, through the SQLAlchemy ORM. CORS
restricted to configured origins. Secrets only from the environment, `.env`
gitignored, `.env.example` carries no real values. Prompt injection from
transcript content is bounded rather than solved, retrieved text is delimited
and labelled as source material, and the artifact sandbox means the worst case
is misleading text, not code execution.

**Not implemented, deliberately:** authentication, rate limiting, per-user
isolation. Scoped out for an internal single-tenant tool; see PRD.md.

---

## 10. Observability

JSON logs, one object per line, every line carrying the request id that is also
returned in `X-Request-ID`:

```json
{"timestamp":"2026-08-28T17:46:44.129Z","level":"INFO","logger":"app.request",
 "message":"POST /api/v1/chat","request_id":"9605b093b501","status_code":200,
 "duration_ms":4213.7}
```

One turn can be traced across routing, retrieval, generation and persistence by
that id. Routing decisions, source counts, provider selection, empty-retrieval
warnings and ingestion progress are all logged.

Health is split by dependency so a failure names itself rather than returning
one opaque "unhealthy". `/health/retrieval` reports the indexed chunk count,
which is the fastest way to diagnose the most likely failure, a running stack
with an empty index.

Dependencies are checked and logged at startup but never block it: the API must
come up so its health endpoints can explain what is broken.

---

## 11. Deployment topology

```
docker compose up -d

postgres   16.2-alpine   :5432   volume postgres_data   healthcheck pg_isready
chromadb   1.5.9         :8000   volume chroma_data     healthcheck /api/v2/heartbeat
ollama     0.5.7         :11434  volume ollama_data     healthcheck ollama list
backend    built         :8080                          healthcheck /health
frontend   built         :3000
```

Startup order is enforced by `depends_on` with health conditions: backend waits
for Postgres and ChromaDB healthy, frontend waits for backend healthy.

Image tags are pinned. With `:latest`, an evaluator could receive a different
ChromaDB or Ollama build than the one this was verified against. Every port is
overridable via `.env` for machines where 5432 or 8000 is already taken.

The ChromaDB healthcheck probes `/api/v2/heartbeat`. The v1 endpoint it used to
probe was removed and returns 404, so the container reported unhealthy while
serving correctly. The Ollama image ships no `curl`, so its healthcheck uses the
`ollama` CLI.

**Production changes this does not make:** the backend mounts source and runs
`--reload`, which suits an evaluator reading and changing code. A real
deployment would bake the code into the image, drop the mount, run behind TLS,
add authentication, and move Postgres to a managed instance.

---

## 12. Trade-offs

| Decision | Alternative | Why |
|---|---|---|
| ChromaDB | pgvector | One less concept while iterating; Postgres already holds the text. Retrieval is isolated to two modules, so migrating is contained |
| Vector search only | Hybrid BM25 + vector | Conversational questions are semantic. Hybrid adds tuning surface for gains this corpus size does not demand |
| Rule-based routing | LLM classifier | Deterministic, testable, no extra round trip on local hardware. Cost: unusual phrasings default to Q&A |
| Anthropic SDK + own agent layer | Claude Agent SDK | The mandatory Ollama demo must have the same agent behaviour as the cloud path |
| Paragraph-packed chunks | Fixed token windows | Retrieved passages read as quotable citations rather than fragments |
| Duplicate chunk text into Chroma | Vector search then Postgres fetch | One round trip per turn; Postgres stays the source of truth |
| Similarity floor over always answering | Return best-effort matches | A weak citation is worse than an honest refusal |
| Subset ingestion by default | Full catalogue | An evaluator gets a working demo in minutes; `INGEST_LIMIT=0` for everything |
| SQL file for schema | Alembic | One schema, no migration history to manage yet. Alembic is the next step if it evolves |

---

## 13. Where it would go next

- **pgvector** to collapse two datastores into one and make retrieval
  transactional with the metadata it cites.
- **Query rewriting** for follow-ups. The current heuristic folds in the
  previous turn; a condensation step would handle longer chains.
- **Reranking** a wider candidate set with a cross-encoder, the usual next win
  after basic vector search.
- **Evaluation harness.** A labelled question set scoring retrieval precision
  and citation accuracy, so prompt and chunking changes stop being guesswork.
- **Streaming Ship 30 with mid-flight validation** rather than post-hoc word
  counting.
- **Auth and per-user isolation** if it moves beyond a single team.
