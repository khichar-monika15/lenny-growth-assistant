# Product Requirements Document: The Lenny Growth Assistant

**Author:** Monika Kumari (khichar-monika15)  
**Date:** August 28, 2026  
**Status:** Implementation Complete

---

## Executive Summary

The Lenny Growth Assistant is a RAG-powered conversational AI that answers questions about product management and growth by searching through Lenny's Podcast transcripts. It also generates Ship 30 for 30 style atomic essays grounded in Lenny's insights.

**Target Users:** Product managers, founders, growth practitioners seeking actionable insights from Lenny's extensive podcast library.

---

## Discovery Brief

### The User
**Who:** Product and growth teams at startups and scale-ups  
**Role:** PMs, founders, growth leads, product marketers  
**Goal:** Quickly find relevant insights from Lenny's 50+ podcast episodes without manual searching  
**Pain Point:** Transcripts are text files in a GitHub repo - no search, no citations, hard to discover relevant content

### The Problem
- **Manual Search:** Users must grep through markdown files or Cmd+F in browsers
- **No Context:** Can't ask questions across multiple episodes
- **Time Sink:** Takes 10-20 minutes to find answers that should take 30 seconds
- **No Synthesis:** Can't generate summaries or essays from multiple sources

### Success Metrics
1. **Answer Quality:** >80% of answers cite relevant transcript chunks
2. **Response Time:** <5s end-to-end for local Ollama responses
3. **User Satisfaction:** "This saved me 15+ minutes" feedback
4. **Essay Quality:** Ship 30 essays hit target word count 90%+ of time

---

## Assumptions

### Technical Assumptions
1. **50 Transcripts Sufficient:** Lenny's publicly available transcripts (podcast-data repo) provide enough breadth
2. **Local-First Demo Acceptable:** Running on Ollama locally is sufficient for internship demo
3. **ChromaDB Scales:** Can handle 800-1000 chunks without performance issues
4. **One User:** No multi-tenancy, authentication, or rate limiting needed for demo

### Product Assumptions
1. **RAG Over Fine-Tuning:** Retrieval-based approach better than fine-tuned model (freshness, transparency)
2. **Source Citations Critical:** Users need to verify claims against original transcripts
3. **Ship 30 Format Known:** Target users understand Hook-Body-CTA essay structure
4. **Configurable Word Count:** 250-1250 range covers short tweets to medium blog posts

### Scope Assumptions
1. **English Only:** No multi-language support needed
2. **Text Only:** No audio playback, video clips, or images
3. **Read-Only:** No user annotations, bookmarks, or saved searches
4. **Desktop First:** Mobile responsive but not mobile-native

---

## Scope

### In Scope ✅

**MVP Features:**
- Conversational chat with session management
- RAG retrieval with source citations
- SSE streaming for real-time responses
- Ship 30 for 30 essay generation (configurable word count)
- Model toggle (Anthropic Claude cloud vs. Ollama local)
- Markdown artifact viewer
- One-command Docker Compose deployment

**Technical Requirements:**
- FastAPI backend with Anthropic Claude SDK
- PostgreSQL for structured data (sessions, messages, transcripts)
- ChromaDB for vector embeddings
- React frontend with Zustand state management
- Ollama for local LLM and embeddings

**Non-Functional Requirements:**
- <5s response time (local Ollama)
- Source citations on every response
- Secure artifact rendering (DOMPurify + iframe sandbox)
- Health checks for all services

### Out of Scope ❌

**Deferred to v2:**
- User authentication and multi-tenancy
- Conversation history export/import
- Advanced filters (by guest, date range, topic)
- Hybrid search (vector + keyword)
- Fine-tuned models
- Mobile native app
- Real-time collaboration
- Analytics dashboard

**Explicitly Excluded:**
- Audio/video playback
- Community-contributed transcripts
- Comments or social features
- Payment or subscriptions
- Multi-language support

---

## Risks and Mitigations

### High-Risk Items

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Hallucination** | High (users trust wrong info) | Medium | Ground all responses in retrieved chunks; show sources |
| **Ollama Quality** | Medium (worse than Claude) | High | Make Claude toggle easy; show model in UI |
| **Ingestion Time** | Low (demo delay) | High | Pre-ingest in startup.sh; cache embeddings |
| **Artifact XSS** | High (security vulnerability) | Low | DOMPurify sanitization + iframe sandbox (no allow-scripts) |
| **Docker Complexity** | Medium (setup friction) | Medium | One-command startup.sh; clear error messages |

### Technical Debt

**Accepted for MVP:**
- No database migrations (schema changes require manual SQL)
- No comprehensive test suite (manual testing only)
- No observability (basic logs only)
- No rate limiting (single-user demo)

**Plan to Address:**
- Post-demo: Add Alembic migrations
- Post-demo: Add pytest suite with >80% coverage
- V2: Add structured logging + metrics
- V2: Add Redis for rate limiting

---

## User Stories

### Core Workflow

**Story 1: Ask a Question**
```
As a PM,
I want to ask "What did Lenny say about product-market fit?"
So that I can get relevant insights without reading 10 transcripts
```
**Acceptance Criteria:**
- Returns streaming response within 5 seconds
- Cites 3-5 relevant transcript sources
- Shows episode titles and similarity scores
- Answers in conversational tone

**Story 2: Generate Ship 30 Essay**
```
As a content creator,
I want to generate a 300-word Ship 30 essay about "finding PMF"
So that I can post on LinkedIn with Lenny's insights
```
**Acceptance Criteria:**
- Essay follows Hook-Body-CTA structure
- Word count within ±10% of target
- All claims backed by sources
- Markdown formatted

**Story 3: Toggle Models**
```
As a user,
I want to switch between Ollama (local) and Claude (cloud)
So that I can balance speed vs. quality
```
**Acceptance Criteria:**
- Dropdown shows both options with availability status
- Switch takes <2 seconds
- UI shows which model generated each response

---

## Edge Cases

### Handled
1. **No Relevant Context:** "I don't have enough information about X in the transcripts..."
2. **Model Offline:** Fallback to alternate provider with warning
3. **Word Count Miss:** Retry essay generation once if out of range
4. **Empty Query:** Disable send button, show placeholder text

### Not Handled (Acceptable for MVP)
1. **Malicious Prompts:** No prompt injection protection
2. **Very Long Questions:** >2000 chars may truncate
3. **Concurrent Sessions:** Race conditions possible
4. **Database Down:** No graceful degradation

---

## Success Criteria for Demo

**Must Have:**
- [x] Ask question → Get cited answer
- [x] Generate Ship 30 essay → Correct word count
- [x] Switch Ollama/Claude → Works without restart
- [x] One-command startup → No manual steps
- [x] Source citations → Visible on every response

**Nice to Have:**
- [ ] Sub-3s responses on M-series Mac
- [ ] Zero hallucinations in demo questions
- [ ] Essay word count exactly on target

---

## Open Questions (Resolved)

**Q: Use LangChain or Claude SDK directly?**  
**A:** Claude SDK per assignment requirement ✅

**Q: ChromaDB vs. pgvector?**  
**A:** ChromaDB for speed; designed for pgvector migration ✅

**Q: Fixed or configurable Ship 30 word count?**  
**A:** Configurable 250-1250 range ✅

**Q: Session persistence across restarts?**  
**A:** Yes, PostgreSQL stores sessions ✅

---

## Timeline

**Total: 24 hours**
- Infrastructure: 3h ✅
- Ingestion: 3h ✅
- RAG: 3h ✅
- Backend API: 3h ✅
- Frontend: 6h ✅
- Documentation: 2h 🔄 (in progress)
- Demo Video: 1h ⏳
- Testing: 3h ⏳

**Deadline:** August 28, 2026 EOD ✅
