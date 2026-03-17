# API Reference

All endpoints require `X-API-Key` header. Base URL: `http://localhost:8000`

## Authentication

```
X-API-Key: <your-api-key>
```

Responses on auth failure:
- `401 Unauthorized` — missing or invalid API key
- `429 Too Many Requests` — rate limit exceeded

---

## Health

### `GET /health`

No authentication required.

**Response**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "app_name": "AI Backend API"
}
```

---

## Documents

### `POST /api/v1/documents`

Ingest a document into the RAG system. Processing (chunking, embedding, indexing) happens asynchronously in the background.

**Request**
```json
{
  "title": "Introduction to RAG",
  "content": "Retrieval-Augmented Generation (RAG) is...",
  "collection_id": "00000000-0000-0000-0000-000000000001",
  "content_type": "text/plain",
  "metadata": {"source": "manual", "author": "alice"}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | string | ✅ | Human-readable document title |
| `content` | string | ✅ | Full text content |
| `collection_id` | UUID string | ❌ | Logical grouping; auto-generated if not provided |
| `content_type` | string | ❌ | Default: `text/plain` |
| `metadata` | object | ❌ | Arbitrary key-value metadata |

**Response** `202 Accepted`
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "job_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "processing"
}
```

**curl**
```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"title": "My Doc", "content": "Content here..."}'
```

---

## Search

### `POST /api/v1/search`

Performs semantic similarity search using embedded query vectors.

**Request**
```json
{
  "query": "How does attention mechanism work?",
  "top_k": 5,
  "collection_id": "00000000-0000-0000-0000-000000000001",
  "filters": {"author": "alice"}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | ✅ | Natural language search query |
| `top_k` | integer | ❌ | Number of results (default: 5, max: 20) |
| `collection_id` | UUID string | ❌ | Restrict to this collection |
| `filters` | object | ❌ | Metadata key-value filters |

**Response** `200 OK`
```json
{
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "content": "The attention mechanism allows the model to...",
      "score": 0.92,
      "document_title": "Transformer Architecture",
      "chunk_index": 3,
      "metadata": {"author": "alice"}
    }
  ],
  "total": 1,
  "query_tokens": 8
}
```

**curl**
```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "attention mechanism", "top_k": 3}'
```

---

## Chat

### `POST /api/v1/chat`

RAG-powered chat. Retrieves relevant context, builds a prompt, and generates a response from the LLM.

**Request**
```json
{
  "message": "Explain transformers in simple terms",
  "collection_id": "00000000-0000-0000-0000-000000000001",
  "top_k": 5,
  "stream": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✅ | User message |
| `collection_id` | UUID string | ❌ | Restrict context to this collection |
| `top_k` | integer | ❌ | Number of context chunks to retrieve |
| `stream` | boolean | ❌ | Enable SSE streaming (default: false) |

**Response (non-streaming)** `200 OK`
```json
{
  "answer": "Transformers are neural networks that...",
  "sources": [
    {
      "document_id": "...",
      "document_title": "Transformer Architecture",
      "chunk_index": 0,
      "content": "..."
    }
  ],
  "tokens_used": 512
}
```

**Response (streaming)** `200 OK` — `Content-Type: text/event-stream`
```
data: {"token": "Transform"}
data: {"token": "ers are"}
data: {"token": " neural"}
data: [DONE]
```

**curl (streaming)**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is RAG?", "stream": true}'
```

---

## Error Responses

All errors follow this schema:

```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Invalid request body |
| 401 | Missing or invalid API key |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
