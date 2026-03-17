# 03 — Request Flow

> Trace every important flow end-to-end so you understand what actually happens on the wire, in the queue, and in the database.

---

## Flow 1: Document Ingestion (Async)

### What the Client Does

```http
POST /documents
X-API-Key: sk-tenant-abc123
Content-Type: application/json

{
  "title": "FastAPI Best Practices",
  "content": "FastAPI is a modern Python web framework...",
  "collection_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### What the System Does

```
Client
  │
  │ POST /documents
  ▼
RateLimitMiddleware  ─── checks Redis sliding window ──► 429 if exceeded
  │
  ▼
resolve_tenant() [Depends]
  │── hash API key: sha256("sk-tenant-abc123")
  │── Redis GET "tenant:key:{hash}"  ── HIT → deserialize Tenant
  │                                  └─ MISS → PostgreSQL SELECT → Redis SET (5min TTL)
  │── tenant.can_accept_request()    ── quota check → 402 if exceeded
  ▼
IngestDocumentUseCase.execute(request, tenant_id)
  │
  ├─ 1. PostgresDocumentRepository.find_duplicate(tenant_id, content)
  │       SELECT tenant_id, content_hash WHERE content_hash = sha256(content)
  │       If found → return 200 with status="duplicate" (no re-processing)
  │
  ├─ 2. Document entity created (status=PENDING)
  │
  ├─ 3. PostgresDocumentRepository.save(document)
  │       INSERT INTO documents (...) ON CONFLICT DO NOTHING
  │
  ├─ 4. document.mark_processing() → status=PROCESSING
  │
  ├─ 5. PostgresDocumentRepository.update(document)
  │       UPDATE documents SET status='processing' WHERE document_id=$1
  │
  └─ 6. arq_pool.enqueue_job("process_document_task", tenant_id, document_id, job_id)
          Redis: ZADD arq:queue {score=now, value=serialized_job}
  │
  ▼
HTTP 202 Accepted
{ "document_id": "...", "job_id": "...", "status": "processing" }

───────────────── Async boundary ─────────────────

ARQ Worker Process picks up job from Redis queue

process_document_task(ctx, tenant_id, document_id, job_id)
  │
  ├─ 1. Fetch document from PostgreSQL (verify it still exists)
  │
  ├─ 2. TokenAwareChunkingStrategy.chunk(content, 512, 50)
  │       Tiktoken encode → sliding window (512 tokens, 50 overlap) → decode
  │       Result: list[ChunkData] with exact token_count per chunk
  │
  ├─ 3. OpenAIEmbeddingService.embed_batch(chunk_texts)
  │       For each chunk text:
  │         Redis GET "embed:{sha256(text)}:{model}"  ── HIT → skip OpenAI call
  │                                                   └─ MISS → batch with uncached
  │       Single OpenAI API call for all uncached chunks
  │       Write results to Redis cache (24h TTL)
  │
  ├─ 4. QdrantVectorRepository.upsert_many([(chunk_id, embedding, metadata)])
  │       POST qdrant:6334/collections/documents/points (gRPC)
  │       metadata payload: { tenant_id, collection_id, document_id, content, chunk_index }
  │
  ├─ 5. PostgresDocumentRepository.update(document.mark_completed(chunks, tokens))
  │       UPDATE documents SET status='completed', chunk_count=N, token_count=M
  │
  └─ 6. (On failure) document.mark_failed(error_message)
          UPDATE documents SET status='failed', error_message=...
          If final retry: ZADD dlq:document_processing {score=now, job_entry}
```

### Failure Scenarios

| Failure Point | What Happens |
|---------------|-------------|
| Redis unavailable at enqueue | `IngestDocumentUseCase` raises, HTTP 503 returned |
| Worker crashes mid-processing | ARQ retries (3 times, 30s backoff). Document stays PROCESSING. |
| OpenAI rate limit | `LLMRateLimitException` raised, ARQ retries with exponential backoff |
| Qdrant write fails | Document stays PROCESSING, worker retries |
| All retries exhausted | Moved to DLQ (`dlq:document_processing`). Document → FAILED status. |
| Duplicate document submitted | `find_duplicate()` detects via content hash — returns 200 immediately, no reprocessing |

---

## Flow 2: Semantic Search (Synchronous)

```http
POST /search
X-API-Key: sk-tenant-abc123
Content-Type: application/json

{ "query": "How do I handle errors in FastAPI?", "top_k": 5 }
```

### Sequence

```
Client
  │
  ├─ RateLimitMiddleware (Redis)
  ├─ resolve_tenant() → Tenant from cache or PostgreSQL
  │
  ▼
SearchDocumentsUseCase.execute(query, tenant_id, top_k=5)
  │
  ├─ 1. OpenAIEmbeddingService.embed("How do I handle errors in FastAPI?")
  │       Redis GET "embed:{sha256(query)}:text-embedding-3-small"
  │         HIT → return cached vector (common for repeated queries)
  │         MISS → OpenAI embeddings API → cache write
  │       Returns: EmbeddingVector(values=(0.023, -0.441, ...), dimensions=1536)
  │
  ├─ 2. QdrantVectorRepository.search(embedding, top_k=5, tenant_id=tenant_id)
  │       Filter: must=[FieldCondition(tenant_id=str(tenant_id))]  ← mandatory isolation
  │       Uses payload index on tenant_id → O(log N), not full scan
  │       Returns: list[ScoredPoint] ordered by cosine similarity
  │
  ├─ 3. Map ScoredPoint → SearchResult (hydrate from payload)
  │       SearchResult(
  │         chunk_id, document_id, collection_id,
  │         content, score, document_title, chunk_index
  │       )
  │
  ├─ 4. Filter by score threshold (0.72 default)
  │       Results below threshold discarded — prevents noisy context
  │
  └─ Return list[SearchResult]
  │
  ▼
HTTP 200
{ "results": [{ "content": "...", "score": 0.91, "document_title": "..." }] }
```

### Why Cosine Similarity?

Cosine similarity measures the **angle** between two vectors, not their magnitude. This means:
- "Error handling FastAPI" and "FastAPI error handling" map to nearly identical vectors
- Document length doesn't affect similarity — a one-paragraph chunk and a ten-paragraph chunk can both score 0.95 for the right query

---

## Flow 3: RAG Chat (Streaming SSE)

This is the most complex flow. It combines semantic search with LLM completion and streams the response.

```http
POST /chat
X-API-Key: sk-tenant-abc123
Accept: text/event-stream

{ "message": "How do I configure CORS in FastAPI?", "stream": true, "top_k": 10 }
```

### Full Sequence

```
Client
  │
  ├─ RateLimitMiddleware (Redis)
  ├─ resolve_tenant()
  │
  ▼
RAGChatUseCase.stream(request, tenant_id)
  │
  ├─ 1. SearchDocumentsUseCase.execute(query, tenant_id, top_k=10)
  │       (see Flow 2 above — embed + Qdrant search)
  │       Returns: list[SearchResult] (already filtered by score >= 0.72)
  │
  ├─ 2. ContextService.build_context(results, model="gpt-4o")
  │       Score filter: keep only results where score >= 0.72 (already done in search)
  │       Token budget: iterate results, accumulate token count
  │         If adding next chunk exceeds 20,000 tokens → stop (truncate, don't omit)
  │       Format into numbered citation blocks:
  │         [1] Source: "FastAPI Docs" (chunk 3, relevance 94%)
  │         FastAPI supports CORS via the CORSMiddleware...
  │       Returns: (context_string, used_results)
  │
  ├─ 3. Load chat history from Redis (if conversation_id provided)
  │       Redis GET "chat:history:{conversation_id}"
  │       Deserialize last N messages
  │
  ├─ 4. PromptService.build_rag_prompt(query, context, history)
  │       Safe injection: context.replace("%%CONTEXT%%", actual_context)
  │       Result: list[ChatMessage]
  │         System: "You are a helpful AI... [CONTEXT]...[/CONTEXT]"
  │         User[prev]: "How do I install FastAPI?"   (from history)
  │         Asst[prev]: "pip install fastapi uvicorn"  (from history)
  │         User[now]:  "How do I configure CORS in FastAPI?"
  │
  ├─ 5. OpenAIChatService.stream(messages, model="gpt-4o")
  │       POST https://api.openai.com/v1/chat/completions (stream=True)
  │       Async generator: yields content deltas as they arrive
  │
  ├─ 6. For each delta from OpenAI:
  │       yield SSE event: data: {"content": "You can", "done": false}
  │       yield SSE event: data: {"content": " configure", "done": false}
  │       ...
  │
  ├─ 7. On stream complete:
  │       yield final SSE event:
  │         data: {
  │           "content": "",
  │           "done": true,
  │           "sources": [{"index":1, "document_title":"FastAPI Docs", "score":0.94}],
  │           "prompt_tokens": 2400,
  │           "completion_tokens": 180,
  │           "total_tokens": 2580
  │         }
  │
  └─ 8. Save turn to Redis chat history
          Redis SET "chat:history:{conversation_id}" (TTL: 24h)
  │
  ▼
SSE stream closes
```

### SSE vs WebSocket

This system uses **Server-Sent Events (SSE)**, not WebSockets. Why?

| Factor | SSE | WebSocket |
|--------|-----|-----------|
| Direction | Server → Client only | Bidirectional |
| HTTP compatibility | Standard HTTP/1.1, works through proxies | Requires upgrade handshake |
| Reconnection | Automatic (browser handles) | Manual |
| Fit for chat | ✅ Client sends request, server streams response | Overkill for this pattern |

For a chat interface where the client sends one message and the server streams one response, SSE is simpler, more robust, and works through every load balancer and CDN.

---

## Token Budget — Why It Matters

The context window in `ContextService` is central to cost and quality:

```python
# Without budget control:
# 10 chunks × 1000 tokens each = 10,000 context tokens
# + 500 token question
# + 4,000 token response
# = 14,500 tokens @ gpt-4o pricing = ~$0.044 per chat message

# With score threshold (0.72) + 20K budget:
# - Noisy chunks rejected before reaching LLM
# - Budget stops at 20K regardless of how many chunks match
# - Prevents runaway costs on large document collections
```

💡 **Senior Insight:** The `score_threshold` and `max_context_tokens` are **critical business controls**, not just performance settings. Set them wrong and you'll either:
- Include irrelevant chunks, confusing the LLM ("hallucination amplification")
- Exceed token limits and get API errors mid-stream
- Burn token budget on context that doesn't help the answer

Monitor these metrics per tenant: average context size, average score of used chunks, LLM cost per request.
