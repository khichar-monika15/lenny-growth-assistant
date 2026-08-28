# Agent Transcripts

This project was built with Claude Code. The raw session logs are exported here,
along with an index of the mistakes that cost real time and how each was caught.

| File | Contents |
|---|---|
| [`session-01.md`](session-01.md) | Main build and remediation session |
| [`session-02.md`](session-02.md) | Initial planning and architecture exploration |

**Sanitisation.** Exported by [`backend/app/scripts/export_agent_transcripts.py`](../backend/app/scripts/export_agent_transcripts.py),
which redacts API keys, tokens, email addresses, phone numbers and absolute home
paths, and drops turns about submission logistics. Internal model reasoning is
omitted and long tool output is truncated. Re-run it with:

```bash
cd backend
python -m app.scripts.export_agent_transcripts \
  --source ~/.claude/projects/<project-dir>/ --out ../agent_transcripts
```

---

## What went wrong, and how it was corrected

The honest summary: the first pass produced code that *looked* finished and
passed a casual smoke test, while the product's central requirement did not work
at all. A second pass audited it properly. The most useful lesson is in **why**
the first pass missed it.

### 1. The chunker looped forever, and it silently emptied the knowledge base

**Symptom.** Ingestion died with exit code 137. It was written off as "an OOM on
large transcripts, non-blocking, chat works without it."

**That conclusion was wrong**, and it hid the worst bug in the project.
`chunk_text()` advanced its cursor with `start = end - overlap`. Once a
document's remaining tail was shorter than the overlap, that expression moved
the cursor *backwards*, then stalled:

```
total=1300   -> stalls at 1100      total=6000    -> stalls at 5800
total=2500   -> stalls at 2300      total=20000   -> stalls at 19800
```

Every real transcript is longer than `max_tokens`, so the function never
returned and grew a list until the kernel killed it. Consequences:

- The knowledge base stayed **completely empty** (0 transcripts, 0 chunks).
- Every answer came from the base model's own memory, with **zero citations**,
  while looking perfectly plausible.
- `pytest` hung forever, so the test suite was never actually green.

**How it was caught.** Not by reading the code, which had been reviewed before.
By running a query against the live API and counting the sources:

```
POST /api/v1/chat -> sources returned: 0
```

**Correction.** Rewrote the chunker to pack whole paragraphs, bisect oversized
ones on sentence boundaries, and guarantee forward progress. Regression tests
pin the exact stall inputs above.

**Lesson.** A failure that is dismissed without a root cause tends to be hiding
something bigger. "Non-blocking" was a guess, not a finding.

### 2. ChromaDB defaulted to L2, so every similarity score was meaningless

The collection was created without `hnsw:space`, so ChromaDB used squared L2
while `retriever.py` computed `1 - distance` — a formula only valid for cosine.
L2 distances are unbounded, so scores could go arbitrarily negative.

Confirmed by asking the running server rather than assuming:

```json
{"hnsw": {"space": "l2", ...}}
```

**Correction.** Create collections with `metadata={"hnsw:space": "cosine"}`, and
clamp scores to `0..1`. The stale L2 collection had to be dropped and rebuilt.

### 3. Ingestion could not have worked even without the loop

Two independent bugs sat behind the chunker, each fatal on its own:

- A `datetime.date` was written into ChromaDB metadata. Chroma accepts only
  `str`/`int`/`float`/`bool`, so every `add()` would have raised.
- The pipeline wrote the key `publication_date`; the retriever read
  `transcript_date`. Dates would always have come back blank.

**Lesson.** Two components agreeing in the same author's head is not an
interface. Both now round-trip through a test.

### 4. Re-ingestion would have crashed on the second run

On a changed content hash the pipeline inserted a *new* `Transcript` row with the
same `github_path`, violating the unique constraint, and left the old vectors
orphaned in Chroma. "Refresh" was documented but had never been executed twice.

**Correction.** Update in place, delete stale chunks from both stores, and a test
that runs ingestion twice.

### 5. `startup.sh` promised a one-command setup it could not deliver

The script counted local `.md` files in an empty directory and told the user to
clone a repository and copy files in. The pipeline fetches over HTTP and ignores
local files entirely, so the branch was dead code. A fresh `./startup.sh` left
the assistant with nothing to cite.

**Correction.** The script now calls the real pipeline, waits with bounded
timeouts, and never prompts, so it runs unattended.

### 6. Earlier failures from the first build session

Each of these was a genuine dead end that had to be diagnosed and reversed:

| Failure | Cause | Fix |
|---|---|---|
| `Could not connect to tenant default_tenant` | Client 0.4.22 spoke the v1 API; the server only serves v2 | Upgraded to `chromadb==1.5.9` after 0.5.20 also failed |
| `Attribute name 'metadata' is reserved` | SQLAlchemy 2.0 reserves `metadata` on declarative models | Mapped as `extra_metadata = Column("metadata", JSONB)` |
| `404` fetching transcripts | Guessed repository name and directory layout | Read the real `index.json`: the repo is `lennys-newsletterpodcastdata`, files sit at the root |
| `unhashable type: 'slice'` | Assumed `index.json` was a list | It is an object; the entries are under `podcasts` |
| `column is of type date but expression is of type character varying` | Model declared `String(50)` against a `DATE` column | Changed to `Date` and parsed the string |
| `pip` resolution failure | `httpx==0.26.0` conflicts with `chromadb 1.5.9` | Relaxed to a compatible range |
| Frontend `<style>` silently dropped | The HTML parser hoists a leading `<style>` into `<head>`, which DOMPurify discards | Added `FORCE_BODY: true`, pinned by a test |
| API tests: "attached to a different loop" | A module-level engine pools connections bound to one event loop; pytest-asyncio uses a fresh loop per test | Dispose the pool around every test |

---

## What this says about the process

Three habits did the actual work:

1. **Verify by executing, not by reading.** The chunker had been reviewed and
   looked correct. A twenty-line simulation of its loop found the defect in
   seconds. Code review checks plausibility; only running it checks behaviour.
2. **Check the observable outcome, not the status code.** The stack was "healthy"
   and chat returned fluent text throughout. Counting the citations was the test
   that mattered.
3. **Distrust a dismissed failure.** Every serious bug here was downstream of one
   symptom that had already been explained away.
