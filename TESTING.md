# Testing

Automated coverage, then a manual UI plan an evaluator can work through in about
fifteen minutes.

---

## Automated tests

```bash
docker compose exec backend python -m pytest        # 101 tests
cd frontend && npm test                             # 18 tests
cd frontend && npm run typecheck
```

Backend tests run inside the container so they hit the real PostgreSQL. Tests
that need the database skip with a clear message if it is not up, rather than
failing confusingly.

| Area | File | What it pins |
|---|---|---|
| Chunking | `tests/ingestion/test_chunker.py` | Termination on the exact inputs that used to loop forever; token ceiling; paragraph alignment; exact character offsets; overlap; coverage of the whole document |
| Routing | `tests/agent/test_router.py` | Essay, document and question intents in both directions; forced skill; topic extraction; format detection; unknown skill rejected |
| Ship 30 | `tests/agent/test_ship30.py` | Every encoded rule reaches the prompt; word-count tolerance band; token budget scales with target; section count; artifact and title extraction |
| Retrieval | `tests/rag/test_retrieval.py` | Cosine distance to similarity; scores clamped to 0..1; similarity floor drops weak matches; empty index; guests parsed back from the joined string; missing metadata tolerated |
| Context assembly | `tests/rag/test_retrieval.py` | Best-first ordering; deduplication; hard token budget; one oversized chunk still returned; citation numbering |
| Sessions and persistence | `tests/api/test_sessions_api.py` | CRUD; cascade delete; turns persisted with citations, tokens and provider; title derived from first message |
| Session isolation | `tests/api/test_sessions_api.py` | One session's history never leaks into another's prompt; prior turns replayed within a session |
| API contracts | `tests/api/test_sessions_api.py` | Response shapes; 422 on invalid input; typed errors with no stack trace; health endpoints |
| Streaming | `tests/api/test_sessions_api.py` | Event ordering; `[DONE]` always sent, including after a failure |
| HTML sanitisation | `frontend/src/components/Artifacts/sanitize.test.ts` | Scripts, event handlers, `javascript:` URLs, nested iframes, forms and remote stylesheets all neutralised; layout and inline CSS preserved; removals reported |
| SSE parsing | `frontend/src/services/api.test.ts` | Frames split across chunk boundaries reassembled; multiple frames per chunk; multi-byte characters intact; error events surfaced; malformed payloads skipped without aborting |

Two of these exist because the bug shipped once. The chunker termination tests
encode the exact token counts that used to stall the cursor. The SSE
reassembly tests encode a split frame, which the old client dropped silently.

---

## Manual UI test plan

**Setup.** From a clean state, so this also tests the documented install path:

```bash
docker compose down -v
./startup.sh
```

Expect it to finish unattended, print the URLs, and report a non-zero chunk
count. Then open http://localhost:3000.

---

### 1 · Services and index are healthy

```bash
docker compose ps
curl -s localhost:8080/health/retrieval
curl -s localhost:8080/health/llm
```

- [ ] All five containers `Up`, and postgres, chromadb and backend `(healthy)`
- [ ] `/health/retrieval` shows `"chromadb": "available"` and `indexed_chunks` above zero
- [ ] `/health/llm` shows `"status": "available"` with both models pulled
- [ ] The sidebar footer shows the same chunk count

---

### 2 · A grounded answer with citations

Ask: **"What does Jen Abel say about closing enterprise deals?"**

- [ ] Three pulsing dots appear before the first token
- [ ] Text streams in rather than appearing all at once
- [ ] A **sources** row appears below the answer
- [ ] Expanding it shows episode title, guest, date and a match percentage
- [ ] The title links to the episode and opens in a new tab
- [ ] The answer attributes claims by name, e.g. "Jen Abel argues…"
- [ ] Match percentages are between 0 and 100

*This is the single most important test. An answer with no sources row means the
index is empty; see Troubleshooting in the README.*

---

### 3 · Follow-up keeps context

In the same conversation, ask: **"Why does that matter?"**

- [ ] The reply addresses the previous topic without you restating it
- [ ] It does not start a fresh, unrelated answer

---

### 4 · Honest refusal

Ask something no episode covers: **"What is the best recipe for sourdough bread?"**

- [ ] The assistant says it cannot answer from Lenny's transcripts
- [ ] It does **not** answer from general knowledge
- [ ] It does **not** show fabricated sources

---

### 5 · Sessions are independent

- [ ] Click **+ New chat**; the thread clears
- [ ] Ask something unrelated, e.g. "How do you price a second product line?"
- [ ] The answer shows no awareness of the earlier conversation
- [ ] Both conversations appear in the sidebar, titled from their first messages
- [ ] Clicking the earlier one restores its full history with sources intact
- [ ] Reload the browser; sessions and history survive
- [ ] Deleting a session removes it and clears the view if it was open

---

### 6 · Ship 30 essay

Ask: **"Write a Ship 30 essay about talent density"**

- [ ] The artifact viewer opens on the right with the essay
- [ ] It has a clear hook in the opening line
- [ ] Headed sections, bullets and selective bold
- [ ] A specific closing takeaway
- [ ] Claims are attributed to guests
- [ ] Roughly 1,250 words, not truncated mid-sentence

For explicit control:

```bash
curl -s -X POST localhost:8080/api/v1/ship30/generate \
  -H 'Content-Type: application/json' \
  -d '{"topic":"talent density","word_count":600,"hook_style":"contrarian"}' \
  | jq '{word_count, target_word_count, within_tolerance, sources: (.sources|length)}'
```

- [ ] `within_tolerance` is `true`
- [ ] `sources` is greater than zero

---

### 7 · Artifact viewer

Ask: **"Create a markdown checklist for running a first enterprise sales call"**

- [ ] Renders as a formatted document, not a code block
- [ ] **Source** tab shows the raw Markdown
- [ ] **Copy** copies it
- [ ] **Download** saves a `.md` file with a sensible name
- [ ] **Close** hides the panel and the conversation widens
- [ ] The chip on the message reopens it

---

### 8 · Artifact security

Ask: **"Make an HTML page showing three pricing tiers"**

- [ ] Renders with styling and layout intact
- [ ] The **Source** tab contains no `<script>` tag and no `on*` attribute

Then verify the boundary directly. Open the browser console:

```js
document.querySelector('.artifact-frame').getAttribute('sandbox')
// → "" (empty: every capability withheld)
```

- [ ] The `sandbox` attribute is present and empty
- [ ] The frame's document contains a `Content-Security-Policy` meta with `default-src 'none'`

To see the notice, ask for a page containing a script or an `onerror` handler:

- [ ] A **"Blocked for safety"** notice names what was stripped
- [ ] Nothing executes: no alert, no console error from injected code

---

### 9 · Model toggle and fallback

With no `ANTHROPIC_API_KEY` set:

- [ ] The header shows **Local · Ollama** with a green dot
- [ ] **Cloud · Claude** shows a grey dot
- [ ] Selecting Claude displays a hint that requests fall back to the local model
- [ ] Sending a message still works, answered by Ollama

With a key configured (`echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env`, then
`docker compose up -d backend`):

- [ ] Claude shows a green dot
- [ ] Answers arrive noticeably faster and are more detailed
- [ ] Citations still appear, since embeddings remain local

---

### 10 · Failure handling

Each of these should degrade visibly, never silently.

**Model unavailable.**

```bash
docker compose stop ollama
```

- [ ] Sending a message shows an error on the message with a hint
- [ ] The composer re-enables; the UI is not stuck
- [ ] `/health/llm` reports Ollama unavailable

```bash
docker compose start ollama   # recover
```

**Vector store unavailable.**

```bash
docker compose stop chromadb
```

- [ ] `/health/retrieval` returns 503 naming ChromaDB
- [ ] The chat surfaces a retrieval error rather than answering ungrounded

```bash
docker compose start chromadb
```

**Database unavailable.**

```bash
docker compose stop postgres
```

- [ ] `/health/db` returns 503
- [ ] The error names the database, not a generic 500

```bash
docker compose start postgres
```

**Stopping mid-stream.** Ask for a long essay and press **Stop**:

- [ ] Generation halts
- [ ] Partial text remains on screen
- [ ] The composer re-enables immediately

---

### 11 · Responsive and accessible

Resize the browser, or use device emulation:

- [ ] **> 1100px** three columns with the artifact open
- [ ] **820 to 1100px** the artifact becomes a full-height overlay
- [ ] **< 820px** single column; ☰ opens the sidebar as a drawer
- [ ] No horizontal page scrolling at any width

Keyboard only, no mouse:

- [ ] Tab reaches the sidebar, composer, send button, sources toggle and every artifact control
- [ ] Focus outlines are clearly visible
- [ ] Enter sends; Shift+Enter inserts a newline
- [ ] Arrow keys or Tab operate the model toggle as a radio group

---

### 12 · Ingestion is idempotent

```bash
docker compose exec backend python -m app.scripts.ingest_transcripts --limit 3
```

- [ ] Reports transcripts **skipped**, not processed
- [ ] No unique-constraint error
- [ ] The chunk count in `/health/retrieval` is unchanged

---

### 13 · Observability

```bash
docker compose logs backend --tail=20
```

- [ ] Each line is a single JSON object
- [ ] Request lines carry `request_id`, `status_code` and `duration_ms`
- [ ] A response's `X-Request-ID` header matches a log line:

```bash
curl -si -X POST localhost:8080/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"test"}' | grep -i x-request-id
```

---

### 14 · No secrets committed

```bash
git ls-files | grep -E '^\.env$'          # expect no output
git log -p | grep -iE 'sk-ant-|ghp_'      # expect no output
```

- [ ] `.env` is untracked
- [ ] `.env.example` exists and contains no real values
- [ ] `agent_transcripts/` contains no keys, emails or absolute home paths

---

## Known limitations

Stated plainly so they are not mistaken for bugs.

- **First response after startup is slow.** The model loads into memory on first
  use. Ten to thirty seconds is normal on CPU.
- **Local answers are shorter and less nuanced than Claude's.** Expected for an
  3B model. Grounding carries most of the quality.
- **Routing keys off explicit phrasing.** "Write an essay about X" routes to
  Ship 30; "help me think through X in a shareable way" does not. Use the
  `skill` parameter to force it.
- **Only 15 episodes are indexed by default.** Questions about other episodes
  will be honestly refused. Run with `INGEST_LIMIT=0` for the full catalogue.
- **Artifacts are read-only.** No in-place editing.
- **No dark theme, and no skip-to-content link.** Unfinished, not considered done.
