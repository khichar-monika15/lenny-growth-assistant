# Product Requirements: The Lenny Growth Assistant

**Status:** delivered · **Author:** Monika Kumari · **Date:** 28 August 2026

---

## 1. Discovery brief

### The user

A **product manager or growth lead on a 10 to 40 person product team**. They
have hard, specific questions — how to price a second product line, what to do
when activation stalls, how to run a first enterprise sales call — and they know
that someone on Lenny's Podcast has answered each one well. They cannot find it.

A secondary user is the **content owner** on the same team, who turns internal
knowledge into posts, briefs and enablement docs, and who currently starts from
a blank page every time.

Both are non-technical about AI. They should never see a prompt, a model name or
a chunk size to get value.

### The problem

Lenny's Podcast is one of the densest sources of product and growth practice
available, and it is close to unusable as a reference. Fifty episodes run to
roughly 800,000 words. The knowledge exists in a form that only rewards people
who already know where to look.

Today a PM either:

- **Searches the web**, lands on a transcript page, and skims 16,000 words for
  the four paragraphs that matter, or
- **Asks a general chatbot**, which produces confident, plausible product advice
  that may be nothing any guest ever said, with no way to check.

The second failure mode is the dangerous one. Generic advice is indistinguishable
from grounded advice at the point of reading, and teams act on it.

**The job:** *"Give me what practitioners actually said about my specific
problem, tell me who said it, and let me turn it into something I can share."*

Three pains removed:

1. **Search cost.** Minutes of skimming become one question.
2. **Trust.** Every claim names its episode, so a reader can verify or go deeper.
3. **Blank page.** A grounded answer becomes an essay or a document in one step.

### Success metrics

**Primary — grounding rate.** *At least 90% of answers to in-corpus questions
cite at least one transcript, and every cited passage is genuinely relevant.*

This is the metric because it is the one that failed. During development the
assistant returned fluent, plausible answers with **zero sources** for every
question, and nothing in the UI or the logs said so. The product was, briefly,
exactly the failure mode it exists to prevent. Grounding rate is measurable at
any moment:

```bash
curl -s -X POST localhost:8080/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"..."}' | jq '.sources | length'
```

**Secondary:**

| Metric | Target | How |
|---|---|---|
| Honest refusal | 100% of out-of-corpus questions decline rather than improvise | Ask about something no episode covers |
| Time to first grounded answer, from clone | Under 20 minutes unattended | `./startup.sh` on a clean machine |
| Response latency, local | Under 30 s end to end for a chat answer | Observed on a 3B model, CPU |
| Ship 30 length compliance | Within ±12% of target | Reported per generation as `within_tolerance` |
| Artifact safety | 100% of scripting and network payloads inert | Automated sanitisation tests |

**Operational:** every failure mode names itself. A user or engineer should
never have to guess whether the model, the index, the database or the network
broke. Four health endpoints and request-id-tagged JSON logs serve this.

### Assumptions

The brief was deliberately incomplete. Recorded here so a reviewer can see what
was decided rather than discovered.

| # | Assumption | If wrong |
|---|---|---|
| 1 | Internal, trusted, single-tenant team tool | Auth and per-user isolation become required |
| 2 | The 50 free transcripts are a fair proxy for the full corpus | Ingestion already scales; only runtime changes |
| 3 | Evaluators run on a laptop, not a GPU box | An 3B model is the ceiling; larger models are a config change |
| 4 | Grounded and cited beats comprehensive | The similarity floor would be lowered to trade precision for recall |
| 5 | ~1,250 words is the Ship 30 default the brief wants, though classic atomic essays are ~250 | Range is configurable 250 to 1,250 |
| 6 | Transcripts change rarely | Hash-based refresh suffices; no webhook or scheduler needed |
| 7 | Reading, not editing, is the artifact job | An editable canvas would be a much larger build |
| 8 | Ollama for the demo, Claude available for quality | Both are wired; the toggle makes the trade visible |

### Scope

**Built:**

- Grounded conversational Q&A with per-answer citations, guest, date and match score
- Honest refusal when the corpus does not support an answer
- Session management: create, list, switch, delete, with independent context
- Full persistence of conversations, citations, timestamps and provider in PostgreSQL
- Follow-up handling: history replay plus retrieval-query augmentation for short turns
- Agent layer: deterministic intent routing to three skills with declared boundaries
- Ship 30 for 30 skill with the method encoded as structured rules
- Markdown and HTML artifact generation with an in-app viewer
- Three-layer isolation for untrusted generated HTML
- Cloud and local model toggle with visible status and documented fallback
- Hash-based incremental ingestion and refresh from the public transcript repo
- One-command startup, structured logging, split health checks, typed errors
- 119 automated tests plus a manual UI test plan

**Deliberately excluded:**

| Not built | Why |
|---|---|
| Authentication, per-user isolation | Internal tool, single tenant (assumption 1). Adds real surface for no evaluation value |
| Hybrid keyword + vector search | Conversational questions are semantic. Tuning surface without a measured gain at this corpus size |
| Reranking | The honest next step, but unjustifiable without an evaluation set to prove it helps |
| Editable artifacts | Reading is the job. Editing is a separate product |
| Multi-turn artifact revision | Regenerating is fast enough at this scale |
| Analytics dashboard | The success metrics are queryable from Postgres and the health endpoints |
| Cloud deployment | The brief asks for local, reproducible. Compose is the deliverable |
| Alembic migrations | One schema with no history to manage. Real cost once it evolves |

### Risks and trade-offs

| Risk | Severity | Mitigation | Residual |
|---|---|---|---|
| **Hallucination** — the model answers from its own memory and it looks identical to a grounded answer | **High** | Similarity floor discards weak matches; the prompt forbids outside knowledge and instructs refusal; sources are always shown so an uncited answer is visibly uncited | An 3B model can still paraphrase loosely. Citations let a reader check |
| **Silent retrieval failure** — the worst version of the above, where infrastructure is broken and the product still answers confidently | **High** | An unreachable vector store now raises rather than returning "no results"; `/health/retrieval` reports the indexed count; the UI shows a retrieval error on the message | This actually happened during development. It is the reason grounding rate is the primary metric |
| **Local model quality** — a 3B model reasons less well than a frontier model | Medium | Grounding does most of the work: the model summarises retrieved text rather than reasoning from scratch. Claude toggle available | Answers are shorter and less nuanced locally. An accepted trade for a zero-key demo |
| **Latency** — local generation is slow | Medium | Streaming shows tokens immediately; retrieval is off the event loop; bounded embedding concurrency | 10 to 30 s for a full local answer. First request also pays model load |
| **Unsafe artifact rendering** — generated HTML is untrusted | Medium | Three independent layers: DOMPurify, an empty iframe sandbox, and a CSP blocking all network. Tested against concrete payloads | Layers 2 and 3 hold even if 1 is bypassed |
| **Prompt injection from transcripts** | Low | Retrieved text is delimited and labelled as source material; the sandbox means the worst case is misleading text, not execution | Bounded, not solved |
| **Data leakage** | Low | Local-only by default; no key needed. `.env` gitignored, no secrets committed | Selecting Claude sends the question and retrieved excerpts to Anthropic. Public transcripts, so low sensitivity |
| **Cost** | Low | Local demo is free. Cloud is opt-in and per-request | Bounded by `max_tokens` |
| **Routing misses** | Low | High-precision patterns default to Q&A; `skill` parameter forces a skill | Unusual phrasings get a normal answer instead of a document |

---

## 2. User flows

### Ask a grounded question

1. User opens the app and types a question.
2. Router classifies it as a grounded answer.
3. The question is embedded and matched against the index.
4. Chunks above the floor are assembled into cited context.
5. The answer streams token by token; sources appear beneath it.
6. The turn is persisted with its citations.

**Acceptance:** the answer streams within 30 s locally; at least one source is
shown with title, guest, date and match score; the source links to the episode;
reloading the session shows the same history.

### Ask a follow-up

1. User asks "why does that matter?" in the same session.
2. Prior turns are replayed to the model.
3. Because the message is short, the previous turn is folded into the retrieval
   query, which alone would be meaningless to embed.

**Acceptance:** the reply resolves the reference without restating it; a new
session started at the same moment shares none of that context.

### Ask about something the corpus does not cover

1. User asks about a topic no episode discusses.
2. Nothing clears the similarity floor.
3. The skill switches to its no-context prompt.

**Acceptance:** the assistant says it cannot answer from the transcripts and
suggests what would help. It does not answer from general knowledge and does not
fabricate a citation.

### Generate a Ship 30 essay

1. User types "write a Ship 30 essay about talent density", or calls
   `/api/v1/ship30/generate` with a topic, word count and hook style.
2. Router selects the Ship 30 skill and extracts the topic for retrieval.
3. A wider retrieval (top-k 15) grounds the essay.
4. The essay streams and opens in the artifact viewer.

**Acceptance:** hook, headed sections, bullets, selective bold and a closing
takeaway; within ±12% of the target; claims attributed to guests by name;
`within_tolerance` reported.

### Generate and view an artifact

1. User asks for a checklist, one-pager or HTML page.
2. Router selects the artifact skill and detects the format.
3. The viewer opens beside the chat with preview and source tabs.
4. HTML is sanitised, sandboxed and CSP-locked before rendering.

**Acceptance:** it renders as a document, not a code block; copy and download
work; scripts, handlers and network requests are inert and the removal is
reported.

### Switch model

1. User picks Cloud · Claude in the header.
2. With no key configured, the backend falls back to Ollama and returns why.

**Acceptance:** the selected provider and its live status are visible; a
fallback is stated, never silent; the answer still arrives.

---

## 3. Implementation

Built in two passes. The second is the more informative one.

**Pass one** delivered the full surface: ingestion, retrieval, providers, chat,
Ship 30, Docker Compose, documentation. Every service came up healthy and chat
returned fluent answers.

**Pass two** was an audit, and it found that the product's central requirement
did not work. Zero transcripts were indexed. Every answer had been ungrounded.
The cause was one arithmetic error in the chunker's cursor that made it loop
forever on any document longer than one chunk — which is every document. It had
been dismissed as a memory issue and left alone.

That audit produced 40 findings and reordered the remaining work:

1. **Make retrieval actually work** — chunker, cosine space, metadata contract, refresh
2. **Sessions, persistence, agent routing** — none of which existed
3. **Artifact viewer, model toggle, session UI** — core requirements with no implementation
4. **Resilience, observability, tests**
5. **Deliverables, documentation, hygiene**

The lesson worth recording: *the stack being healthy said nothing about the
product working.* Counting the sources in a response was the test that mattered,
and it took thirty seconds once someone thought to run it.

### Acceptance criteria

| # | Criterion | Verified by |
|---|---|---|
| 1 | Fresh clone reaches a grounded answer using only the README | `docker compose down -v && ./startup.sh` |
| 2 | Answers cite real transcripts with scores in 0..1 | Live query, `.sources` non-empty |
| 3 | Out-of-corpus questions are refused | Manual test 4 |
| 4 | Sessions keep independent context | Automated test |
| 5 | Conversations persist with citations and timestamps | Automated test |
| 6 | Ship 30 lands within tolerance with correct structure | Manual test 6 |
| 7 | Artifacts render in-app; hostile HTML is inert | Automated + manual test 8 |
| 8 | Model toggle visible; fallback explained | Manual test 9 |
| 9 | Every dependency failure is diagnosable | Manual test 10 |
| 10 | No secrets committed | `git ls-files` review |

---

## 4. Open questions

Answered by decision rather than by the client, and worth revisiting with a real
user:

- **How strict should refusal be?** The floor sits at 0.25. Stricter means more
  honest refusals and more "I don't know"; looser means more weak citations.
  This wants tuning against real questions.
- **Is 1,250 words right?** The brief says so; the Ship 30 method says ~250.
  Configurable, defaulting to the brief.
- **Should artifacts be editable?** Assumed no. The first thing a content owner
  will ask for.
- **Whole corpus or curated?** All 50 episodes are treated equally. A team may
  want to weight recency or specific guests.
