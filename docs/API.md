# API Documentation

## Base URL
`http://localhost:8080`

## Health Endpoints

### GET /health
Returns system health status.

**Response:**
```json
{
  "status": "healthy",
  "environment": "development",
  "default_model": "ollama"
}
```

### GET /health/llm
Check LLM provider availability.

**Response:**
```json
{
  "ollama": "available",
  "anthropic": "not_configured"
}
```

## Chat Endpoints

### POST /api/v1/chat
Non-streaming chat endpoint.

**Request:**
```json
{
  "message": "What is product-market fit?",
  "session_id": "optional-session-id",
  "model_provider": "ollama"  
}
```

**Response:**
```json
{
  "message": "Product-market fit is when...",
  "sources": [
    {
      "chunk_id": "uuid",
      "transcript_title": "Episode Title",
      "similarity_score": 0.89
    }
  ],
  "usage": {
    "input_tokens": 45,
    "output_tokens": 120
  }
}
```

### POST /api/v1/chat/stream
Server-Sent Events streaming endpoint.

**Request:** Same as /api/v1/chat

**Response:** SSE stream with events:
- `retrieval_start` - Starting vector search
- `sources` - Retrieved source chunks
- `content_delta` - Streaming response tokens
- `[DONE]` - Stream complete

## Ship 30 Endpoint

### POST /api/v1/ship30/generate
Generate Ship 30 for 30 style essay.

**Request:**
```json
{
  "topic": "Finding product-market fit",
  "word_count": 300,
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "essay": "Hook: Ever wondered why...\n\nBody: ...\n\nCTA: ...",
  "word_count": 298,
  "sources": [...]
}
```

## Error Responses

All endpoints return errors in this format:
```json
{
  "detail": "Error message"
}
```

Status codes:
- 400: Bad Request
- 500: Internal Server Error
- 503: Service Unavailable (LLM offline)
