# 05 — Concurrency and Consistency

> Async Python is deceptively easy to write incorrectly. This document covers the real concurrency challenges in this system and what it solves (and doesn't solve).

---

## Async Python Fundamentals in This System

The entire API is built on `asyncio` via Uvicorn + FastAPI. Understanding what this means:

- **Single-threaded event loop** — one OS thread handles all requests concurrently
- **Concurrent, not parallel** — multiple requests progress simultaneously, but only one runs Python code at any moment
- **I/O-bound work = async** — while waiting for PostgreSQL/Redis/OpenAI, the event loop serves other requests
- **CPU-bound work = blocking** — tiktoken encoding and SHA-256 hashing are synchronous but fast enough not to matter

```
Event Loop
│
├─ Request A: waiting for PostgreSQL → yield control
│  Request B: processing → runs
│  Request A: PostgreSQL returns → resumes
│                                              (all on one thread)
```

### The Golden Rule

**Never block the event loop.** Operations that block:

```python
# ❌ Blocks event loop — all other requests stall until this returns
time.sleep(1)
requests.get("https://api.openai.com/...")   # sync HTTP
```

```python
# ✅ Yields control to event loop during wait
await asyncio.sleep(1)
await async_openai_client.embeddings.create(...)  # async HTTP
```

In this codebase, all I/O is async: `asyncpg` (async PostgreSQL), `aioredis` (async Redis), `AsyncQdrantClient`, `AsyncOpenAI`.

---

## Background Processing with ARQ

### Why ARQ?

The document processing pipeline (chunk → embed → store) can take 10–120 seconds. It's too slow for a synchronous HTTP response. ARQ provides:

1. **Durability:** Jobs survive process crashes (stored in Redis, not RAM)
2. **Multi-worker:** Multiple worker processes dequeue from the same Redis queue
3. **Retry with backoff:** Failed jobs retry automatically (3 times, 30s between retries)
4. **DLQ (Dead Letter Queue):** Jobs exhausting all retries land in `dlq:document_processing` sorted set

### Worker Architecture

```
API Pod (N instances)               Worker Pod (M instances)
─────────────────────               ────────────────────────
IngestDocumentUseCase               arq_worker.py
  arq_pool.enqueue_job(...)   →→→→  process_document_task()
                                    chunks + embeds + stores in Qdrant
                              ←←←←  updates document status in PostgreSQL
```

Both API pods and worker pods connect to the same Redis queue. Scaling M independently of N is the key operational advantage. If embedding backlog grows, scale workers. No API changes needed.

### Job Lifecycle

```
State machine for an ARQ job:

queued     → [ARQ dequeues]   → running
running    → [success]         → complete
running    → [exception]       → retrying (attempt 2)
retrying   → [exception]       → retrying (attempt 3)
retrying   → [exception]       → failed (→ DLQ)
```

```python
# arq_worker.py — the task function
async def process_document_task(ctx, tenant_id, document_id, job_id):
    try:
        await process_use_case.execute(doc_id, ingestion_job, tenant_id=t_id)
    except Exception as exc:
        attempt = ctx.get("job_try", 1)
        if attempt >= settings.worker.max_retries:
            await _write_to_dlq(ctx, tenant_id, document_id, job_id, str(exc))
        raise  # ARQ sees the exception → schedules retry
```

### DLQ Monitoring

Failed jobs accumulate in a Redis sorted set:

```python
DLQ_KEY = "dlq:document_processing"
# score = unix timestamp of failure
# value = JSON: {tenant_id, document_id, job_id, error, failed_at}

# Inspect DLQ from Redis CLI:
# ZRANGE dlq:document_processing 0 -1 WITHSCORES
```

⚠️ **Footgun:** The DLQ is Redis, which is volatile. If Redis restarts without persistence, DLQ entries are lost. For production, ensure Redis is configured with `AOF` persistence (`appendonly yes`), or export DLQ entries to PostgreSQL before they expire.

---

## Idempotency

### Document Ingestion Idempotency

The ingestion pipeline is designed to be safe to retry:

```python
# 1. Document save: ON CONFLICT DO NOTHING
await self._pool.execute("""
    INSERT INTO documents (...) VALUES (...)
    ON CONFLICT (document_id) DO NOTHING
""", ...)
# Safe to call multiple times with same document_id

# 2. Qdrant upsert (not insert):
await qdrant.upsert(collection_name="documents", points=[...])
# Same chunk_id = replace, not duplicate

# 3. Embedding cache write: Redis SET (idempotent by nature)
await redis.setex(cache_key, ttl, vector_json)
```

If the worker crashes after step 1 (PostgreSQL write) but before step 3 (Qdrant write), a retry is safe. The only observable effect: the document stays in status `PROCESSING` until the retry succeeds or all retries are exhausted.

### Chat Idempotency — Notable Absence

RAG chat is **not** idempotent. Calling `POST /chat` twice with the same message and `conversation_id` will:
1. Perform two vector searches (doubled cost)
2. Make two OpenAI completions (doubled cost)
3. Append two turns to chat history

This is acceptable for a chat interface — users don't typically send the same message twice, and idempotent chat (requiring server-side deduplication) adds complexity without clear benefit.

---

## Consistency Model

### What This System Guarantees (Strong Consistency)

| Operation | Guarantee |
|-----------|-----------|
| Document save in PostgreSQL | Durable immediately (WAL-flushed) |
| Rate limit check | Atomic (Lua script — no window racing) |
| Tenant lookup | Consistent within 5 minutes (cache TTL) |
| Document status update | Consistent immediately (direct PostgreSQL UPDATE) |

### What This System Does NOT Guarantee

| Scenario | What Happens |
|----------|-------------|
| Worker crashes mid-chunk | Document stuck in PROCESSING. Repair: ARQ retries. |
| Redis cache stale (deactivated tenant) | Tenant can still make requests for up to 5min |
| Qdrant write succeeds, PostgreSQL UPDATE fails | Chunks in Qdrant but doc shows PROCESSING. Repair: ARQ retry will re-embed (Qdrant upsert is idempotent) |
| Two workers pick same ARQ job | ARQ prevents this with Redis SETNX locking per job — should not happen |

### Eventual Consistency: Chunk Storage

After a document is ingested:
1. Content saved in PostgreSQL immediately (synchronous)
2. Chunks stored in Qdrant **eventually** (via ARQ worker, potentially seconds/minutes later)

This means: a document can be `COMPLETED` in PostgreSQL but its chunks not yet searchable in Qdrant if the worker is slow. This is expected behavior — the `status` field communicates processing state to the client.

---

## Optimistic vs Pessimistic Locking

This system uses **no explicit locking** for document operations. Instead:

1. **ARQ prevents duplicate job execution** — each job has a Redis-backed lock (ARQ internal)
2. **Content hash deduplication** prevents duplicate documents at the application level
3. **Document status FSM** prevents double-processing (PROCESSING → can't start again)

For a higher-traffic future scenario where the same document might be submitted simultaneously by two requests:

```python
# Option 1: PostgreSQL advisory lock per document_id
# (SELECT pg_try_advisory_lock(hashtext(document_id)))

# Option 2: Redis SETNX lock before processing
# await redis.set(f"lock:doc:{document_id}", "1", nx=True, ex=60)
```

Currently, the `ON CONFLICT DO NOTHING` in `save()` combined with the status FSM provides sufficient protection.

---

## Connection Pool Management

### PostgreSQL Pool

```python
pool = await asyncpg.create_pool(
    dsn=settings.url,
    min_size=2,    # always-warm connections
    max_size=10,   # cap at 10 concurrent DB connections
    command_timeout=30,  # fail fast on slow queries
)
```

**Sizing rule of thumb:**
- Each API pod: `max_size=10` PostgreSQL connections
- 5 API pods × 10 connections = 50 total client connections
- PostgreSQL default `max_connections=100` → room for monitoring tools + headroom

⚠️ **Footgun:** `max_size=None` (asyncpg default) creates unbounded pools. Under load, 1000 concurrent requests create 1000 connections → PostgreSQL OOM → cascade failure. Always set `max_size`.

### Redis Connection

`aioredis` uses a connection pool internally. The `RedisCache` class wraps a single `AsyncRedis` client shared across all requests via the DI container Singleton.

### Qdrant Connection

The `QdrantAdapter` uses gRPC when `prefer_grpc=True` (default for performance). gRPC connections are persistent HTTP/2 streams — multiplexed, one connection handles many concurrent requests efficiently.
