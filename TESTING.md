# Testing Guide: The Lenny Growth Assistant

**For:** Monika Kumari (khichar-monika15)  
**Demo Date:** August 28, 2026

---

## Prerequisites

Before testing, ensure you have:
- [x] Docker Desktop installed and running
- [x] At least 8GB RAM available
- [x] 20GB free disk space (for Ollama models)

---

## Setup (First Time)

### 1. Start the Stack

```bash
cd /path/to/lenny
./startup.sh
```

**Expected Output:**
```
🚀 Starting The Lenny Growth Assistant...
📝 Creating .env from template...
🐳 Starting Docker services...
⏳ Waiting for services to be ready...
   Waiting for Ollama...
✅ Ollama is ready!
📦 Pulling Ollama models (this may take a few minutes)...
✅ Models pulled!
✅ Backend is ready!
✨ The Lenny Growth Assistant is running!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 Frontend:     http://localhost:3000
🔧 Backend API:  http://localhost:8080
📊 API Docs:     http://localhost:8080/docs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Time:** 5-10 minutes (model downloads)

### 2. Verify Services

```bash
# Check all containers running
docker ps

# Expected: 5 containers
# lenny-postgres, lenny-chromadb, lenny-ollama, lenny-backend, lenny-frontend
```

---

## Manual Test Plan

### Test 1: Health Checks

**Objective:** Verify all services are healthy

**Steps:**
1. Open http://localhost:8080/health
2. Open http://localhost:8080/health/llm

**Expected:**
```json
// /health
{
  "status": "healthy",
  "environment": "development",
  "default_model": "ollama"
}

// /health/llm
{
  "ollama": "available",
  "anthropic": "not_configured"
}
```

**Pass Criteria:** Both endpoints return 200 OK

---

### Test 2: Frontend Loads

**Objective:** React app renders without errors

**Steps:**
1. Open http://localhost:3000
2. Check browser console (F12 → Console)

**Expected:**
- Page shows "🎯 Lenny Growth Assistant"
- Input field visible
- No errors in console

**Pass Criteria:** UI renders, no console errors

---

### Test 3: Ask a Question (Chat Flow)

**Objective:** End-to-end RAG chat works

**Test Case 3.1: Basic Question**

**Steps:**
1. Type: "What did Lenny say about product-market fit?"
2. Click **Send**
3. Wait for response

**Expected:**
- "🔍 Searching transcripts..." appears
- Streaming response begins within 3-5 seconds
- Answer includes citations (e.g., "[Rahul Vohra on PMF]")
- Source badges visible below message

**Pass Criteria:**
- Response arrives
- Contains relevant answer
- Shows source citations

**Test Case 3.2: No Context Available**

**Steps:**
1. Type: "What's the weather today?"
2. Click **Send**

**Expected:**
```
I don't have enough information about weather in Lenny's transcripts.
Try asking about product management, growth, or startup topics.
```

**Pass Criteria:** Model admits it doesn't have context

---

### Test 4: Generate Ship 30 Essay

**Objective:** Essay generation works with correct word count

**Steps (via API - frontend Ship 30 button not implemented in MVP):**

```bash
curl -X POST http://localhost:8080/api/v1/ship30/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Finding product-market fit",
    "word_count": 300,
    "hook_style": "question"
  }'
```

**Expected Response:**
```json
{
  "essay": "How do you know when you've found product-market fit?\n\n...",
  "word_count": 298,
  "target_word_count": 300,
  "sources": [...],
  "model_provider": "ollama"
}
```

**Pass Criteria:**
- Word count within ±10% of target (270-330 for target 300)
- Essay follows Hook-Body-CTA structure
- Sources array not empty

---

### Test 5: Model Toggle (If Anthropic Key Set)

**Objective:** Switch between Claude and Ollama

**Setup:**
1. Add Anthropic API key to `.env`:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   ```
2. Restart backend: `docker-compose restart backend`

**Steps:**
1. Send message with Ollama (default)
2. Switch to Claude in UI (future feature - test via API)

**API Test:**
```bash
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is PMF?",
    "model_provider": "claude"
  }'
```

**Expected:** Response uses Claude model

**Pass Criteria:** Both models work without errors

---

### Test 6: Source Citations Clickable

**Objective:** Source badges are interactive

**Steps:**
1. Ask a question that returns sources
2. Hover over source badge
3. Click source badge (future: opens transcript)

**Expected:**
- Hover shows tooltip with similarity score
- Click does nothing (not implemented in MVP)

**Pass Criteria:** Badges render correctly

---

### Test 7: Streaming UI

**Objective:** Streaming response updates in real-time

**Steps:**
1. Ask: "Explain growth loops in detail"
2. Watch message as it streams

**Expected:**
- Text appears word-by-word
- Typing indicator (▊) visible at cursor
- No flash of unstyled content

**Pass Criteria:** Smooth streaming, no UI glitches

---

### Test 8: Error Handling

**Test Case 8.1: Ollama Offline**

**Steps:**
1. Stop Ollama: `docker-compose stop ollama`
2. Send a message

**Expected:**
```
⚠️ Ollama is unavailable
Try again or switch to Claude
```

**Cleanup:** `docker-compose start ollama`

**Test Case 8.2: Empty Input**

**Steps:**
1. Click **Send** with empty input

**Expected:** Send button disabled, nothing happens

**Pass Criteria:** Errors shown clearly, system recovers

---

## Performance Testing

### Latency Benchmarks

**Test:** Measure end-to-end response time

**Steps:**
1. Open browser DevTools → Network tab
2. Send message
3. Note time from request to first token

**Expected Latency:**
- Retrieval: <1s
- First token: <2s (Ollama), <3s (Claude)
- Full response: <10s

**Pass Criteria:** Meets latency targets

---

## Docker Logs Review

### Check for Errors

```bash
# Backend logs
docker-compose logs backend | grep ERROR

# ChromaDB logs
docker-compose logs chromadb | grep ERROR

# Ollama logs
docker-compose logs ollama | tail -20
```

**Pass Criteria:** No critical errors

---

## Cleanup & Reset

### Stop Services

```bash
docker-compose down
```

### Delete All Data (Fresh Start)

```bash
docker-compose down -v  # WARNING: Deletes database + vectors
```

### Restart from Scratch

```bash
rm .env  # Remove config
./startup.sh  # Re-run setup
```

---

## Known Issues (Expected)

1. **Transcript Ingestion:** If no transcripts in `data/transcripts/`, RAG returns empty context
   - **Fix:** Clone https://github.com/LennysNewsletter/lennys-newsletter and copy `.md` files

2. **First Ollama Request Slow:** Cold start takes 5-10 seconds
   - **Fix:** Expected, subsequent requests faster

3. **Frontend Ship 30 Button:** Not implemented in MVP
   - **Workaround:** Use API directly (see Test 4)

4. **No Session Sidebar:** Only one session per browser
   - **Workaround:** Refresh page to start new session

---

## Demo Video Recording Checklist

Before recording, test these flows:

- [x] Ask question about PMF → Get cited answer
- [x] Generate Ship 30 essay via API → Correct word count
- [x] Show streaming response
- [x] Show source citations
- [x] Explain one trade-off (ChromaDB vs pgvector)

**Recommended Flow:**
1. **Intro (30s):** "Hi, I'm Monika. This is the Lenny Growth Assistant..."
2. **Demo (90s):**
   - Ask: "What did Lenny say about product-market fit?"
   - Show streaming response
   - Click source badge
   - Generate Ship 30 essay (via curl or Postman)
3. **Trade-Off (30s):** "I chose ChromaDB over pgvector because..."
4. **Outro (10s):** "One-command startup, fully local, ready for production."

**Total:** 2:40 (under 3 min limit)

---

## Submission Checklist

Before submitting:

- [x] All tests pass
- [x] Demo video uploaded to YouTube (unlisted)
- [x] GitHub repo public: https://github.com/khichar-monika15/lenny-growth-assistant
- [x] README.md has setup instructions
- [x] No `.env` file committed (check with `git status`)
- [x] All commits as khichar-monika15

**Submission Form:** https://forms.gle/LgotDHNVxW1mbzNE7

---

## Troubleshooting

### Frontend not loading
```bash
docker-compose logs frontend | tail -20
```
**Common fix:** `docker-compose restart frontend`

### Backend 500 errors
```bash
docker-compose logs backend | grep ERROR
```
**Common fix:** Check DATABASE_URL in .env

### Ollama "model not found"
```bash
docker-compose exec ollama ollama list
```
**Fix:** Re-pull models: `docker-compose exec ollama ollama pull llama3.1:8b`

### ChromaDB connection refused
```bash
docker-compose ps chromadb
```
**Fix:** `docker-compose restart chromadb`

---

## Success Metrics

**Demo is ready when:**
- All Test 1-7 pass
- No ERROR logs in backend
- Latency <10s for standard questions
- Source citations visible on every response

**Good luck, Monika! 🚀**
