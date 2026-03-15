---
phase: 2
level: 2
researched_at: 2026-03-15
---

# Phase 2 Research — Infrastructure Layer & External Integrations

## Questions Investigated

1. How does the OpenAI Python SDK (v1.109.1) handle async embeddings, chat completions, and streaming?
2. How does qdrant-client (v1.17.1) AsyncQdrantClient API work for upsert and search?
3. How does redis-py (v5.3.1) handle async operations, pipelines, and sorted sets for rate limiting?
4. How does tiktoken (v0.12.0) work for model-specific token counting?
5. How to wire dependency-injector Singleton providers with nested pydantic-settings attributes?
6. What is the best pattern for an asyncio in-process background worker?

## Findings

### 1. OpenAI Python SDK — Async & Streaming

**Version**: openai 1.109.1

The SDK has **built-in retry logic** (2 retries by default, exponential backoff) — no need for tenacity.

**Async Embeddings:**
```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="...", max_retries=3)

# Single embedding
response = await client.embeddings.create(
    model="text-embedding-3-small",
    input="Hello world"
)
vector = response.data[0].embedding  # list[float]
usage = response.usage  # Usage(prompt_tokens=2, total_tokens=2)

# Batch embedding — pass list of strings
response = await client.embeddings.create(
    model="text-embedding-3-small",
    input=["text1", "text2", "text3"]
)
vectors = [item.embedding for item in response.data]
```

**Async Chat Completions (non-streaming):**
```python
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    temperature=0.7,
    max_tokens=4096,
)
content = response.choices[0].message.content
usage = response.usage  # CompletionUsage(prompt_tokens, completion_tokens, total_tokens)
```

**Async Chat Completions (streaming):**
```python
stream = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True,
)
async for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        yield delta.content
```

**Error Hierarchy:**
| Status Code | Exception Type |
|-------------|---------------|
| 429 | `openai.RateLimitError` |
| 401 | `openai.AuthenticationError` |
| >=500 | `openai.InternalServerError` |
| network | `openai.APIConnectionError` |
| timeout | `openai.APITimeoutError` |

**Key Insight:** The SDK handles retries automatically. Setting `max_retries=3` on the client is sufficient — no need for external retry libraries like tenacity.

**Sources:**
- https://github.com/openai/openai-python
- https://platform.openai.com/docs/api-reference

**Recommendation:** Use `AsyncOpenAI` with `max_retries=3`. Use `chat.completions.create()` for both streaming and non-streaming. Map OpenAI exceptions to domain exceptions.

---

### 2. Qdrant AsyncQdrantClient

**Version**: qdrant-client 1.17.1

```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
    FilterSelector,
)

client = AsyncQdrantClient(host="localhost", port=6333, prefer_grpc=True)

# Create collection (idempotent check)
if not await client.collection_exists("documents"):
    await client.create_collection(
        collection_name="documents",
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

# Upsert points
await client.upsert(
    collection_name="documents",
    points=[
        PointStruct(
            id=str(chunk_id),  # string UUIDs work
            vector=[0.1, 0.2, ...],
            payload={"document_id": str(doc_id), "text": "chunk text"},
        )
    ],
)

# Search
results = await client.query_points(
    collection_name="documents",
    query=[0.1, 0.2, ...],  # query vector
    limit=10,
    query_filter=Filter(
        must=[FieldCondition(key="document_id", match=MatchValue(value=str(doc_id)))]
    ),
)
# results.points -> list of ScoredPoint(id, score, payload, vector)

# Delete by filter
await client.delete(
    collection_name="documents",
    points_selector=FilterSelector(
        filter=Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value=str(doc_id)))]
        )
    ),
)
```

**Key Insight:** `query_points()` is the recommended search method (replaces legacy `search()`). Point IDs can be strings (UUIDs). The `prefer_grpc=True` flag enables gRPC transport for better performance.

**Sources:**
- https://qdrant.tech/documentation/
- https://github.com/qdrant/qdrant-client

**Recommendation:** Use `AsyncQdrantClient` with `prefer_grpc=True`. Use `query_points()` for search. Store `document_id` in payload for filter-based deletion.

---

### 3. Redis Async Operations

**Version**: redis 5.3.1 (with hiredis 3.3.0 for C-accelerated parsing)

```python
import redis.asyncio as aioredis

# Connection
client = aioredis.from_url("redis://localhost:6379/0", decode_responses=False)

# Basic ops
await client.set("key", b"value", ex=3600)  # with TTL
value = await client.get("key")  # bytes | None
await client.delete("key")

# Pipeline (atomic batch)
async with client.pipeline(transaction=True) as pipe:
    pipe.zremrangebyscore("rate:key", 0, cutoff_timestamp)
    pipe.zcard("rate:key")
    pipe.zadd("rate:key", {str(now): now})
    pipe.expire("rate:key", 60)
    results = await pipe.execute()

# Sorted sets for sliding window rate limiting
now = time.time()
window_start = now - 60  # 1 minute window
async with client.pipeline(transaction=True) as pipe:
    pipe.zremrangebyscore(key, "-inf", window_start)
    pipe.zcard(key)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, 60)
    _, count, _, _ = await pipe.execute()
    allowed = count < max_requests
```

**Key Insight:** Use `decode_responses=False` for binary data (embeddings). Use `decode_responses=True` for JSON/string data. Pipelines are essential for atomic rate limiting.

**Sources:**
- https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html

**Recommendation:** Create RedisCache with lazy connection. Use sorted sets + pipeline for sliding window rate limiting. Use separate key prefixes for different cache types.

---

### 4. tiktoken Token Counting

**Version**: tiktoken 0.12.0

```python
import tiktoken

# Get encoding for a model
enc = tiktoken.encoding_for_model("gpt-4o")  # returns Encoding

# Count tokens
tokens = enc.encode("Hello world")  # list[int]
count = len(tokens)  # 2

# Decode back
text = enc.decode(tokens)  # "Hello world"

# Truncate to limit
tokens = enc.encode(long_text)
truncated_tokens = tokens[:max_tokens]
truncated_text = enc.decode(truncated_tokens)

# Cache encodings (they're expensive to create)
# tiktoken internally caches, but explicit caching is still recommended
```

**Model → Encoding mapping (handled by tiktoken):**
- gpt-4o, gpt-4o-mini → o200k_base
- gpt-4, gpt-3.5-turbo → cl100k_base
- text-embedding-3-small/large → cl100k_base

**Fallback for unknown models:** Use `tiktoken.get_encoding("cl100k_base")`

**Sources:**
- https://github.com/openai/tiktoken

**Recommendation:** Use `encoding_for_model()` with try/except fallback to `cl100k_base`. Cache Encoding instances in a dict.

---

### 5. dependency-injector Nested Settings Wiring

**Version**: dependency-injector 4.48.3

The `.provided` attribute allows accessing nested properties of provider results:

```python
class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(get_settings)
    
    # Access nested attributes via .provided
    redis_cache = providers.Singleton(
        RedisCache,
        url=settings.provided.redis.url,  # calls settings().redis.url
    )
    
    embedding_provider = providers.Singleton(
        OpenAIEmbeddingService,
        settings=settings.provided.openai,  # passes full OpenAISettings object
    )
```

**Key Insight:** `.provided` creates a lazy attribute accessor that resolves at call time. This works for nested Pydantic models and properties.

**Important caveat:** The `.provided.redis.url` syntax invokes the `url` property on `RedisSettings`. For complex nested access, use `providers.Callable` with a lambda as fallback.

**Sources:**
- https://python-dependency-injector.ets-labs.org/providers/singleton.html

**Recommendation:** Use `.provided` for direct nested attribute access. Use `providers.Callable(lambda s: s.redis.url, settings)` if `.provided` chain breaks.

---

### 6. Asyncio Background Worker Pattern

**Pattern:** Use `asyncio.Queue` + `asyncio.TaskGroup` (Python 3.11+)

```python
import asyncio
import uuid

class BackgroundWorker:
    def __init__(self, max_concurrent: int = 5):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tasks: dict[str, dict] = {}
        self._running = False
    
    async def enqueue(self, coro, name: str = "") -> str:
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {"status": "pending", "name": name}
        await self._queue.put((task_id, coro))
        return task_id
    
    async def start(self):
        self._running = True
        asyncio.create_task(self._worker_loop())
    
    async def _worker_loop(self):
        while self._running:
            task_id, coro = await self._queue.get()
            asyncio.create_task(self._execute(task_id, coro))
    
    async def _execute(self, task_id, coro):
        async with self._semaphore:
            self._tasks[task_id]["status"] = "running"
            try:
                await coro
                self._tasks[task_id]["status"] = "completed"
            except Exception as e:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
    
    async def stop(self):
        self._running = False
```

**Key Insight:** Use `asyncio.Semaphore` for concurrency limiting, not TaskGroup. Keep the worker simple — it's in-process, not distributed.

**Recommendation:** Lightweight implementation with Queue + Semaphore. Track task status in a dict. Graceful shutdown waits for running tasks.

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Retry strategy | OpenAI SDK built-in (`max_retries=3`) | SDK handles exponential backoff natively, no tenacity needed |
| Qdrant search method | `query_points()` | Recommended over legacy `search()` |
| Qdrant transport | gRPC (`prefer_grpc=True`) | Better performance than REST |
| Redis rate limiting | Sorted sets + pipeline | Atomic sliding window, standard pattern |
| Token counting | tiktoken with model-specific encoding | Exact token counts matching OpenAI's tokenizer |
| Background worker | asyncio.Queue + Semaphore | Simple, in-process, no external dependencies |
| Container wiring | `.provided` attribute chains | Lazy resolution of nested settings |

## Patterns to Follow

- **Lazy client initialization**: Don't create async clients in `__init__`. Create lazily on first use or accept pre-created clients
- **Built-in retry**: Rely on OpenAI SDK's built-in retry instead of adding tenacity
- **Cache key hashing**: Use SHA256 prefix for deterministic, collision-resistant cache keys
- **Pipeline atomicity**: Always use Redis pipelines for multi-step atomic operations
- **Graceful shutdown**: All infrastructure services must support async cleanup via `close()` or `stop()`

## Anti-Patterns to Avoid

- **No tenacity for OpenAI**: The SDK already handles retries — adding tenacity doubles the retry logic
- **No synchronous Redis**: Always use `redis.asyncio`, never `redis.Redis` (blocks event loop)
- **No hardcoded collection names**: Always pass from settings
- **No raw embedding storage**: Serialize as JSON, not pickle (portability)
- **No unbounded queues**: Background worker must have max_concurrent limit

## Dependencies Already Installed

| Package | Version | Purpose |
|---------|---------|---------|
| openai | 1.109.1 | LLM client (embeddings + chat) |
| qdrant-client | 1.17.1 | Vector database client |
| redis | 5.3.1 | Cache + rate limiting |
| hiredis | 3.3.0 | C-accelerated Redis parser |
| tiktoken | 0.12.0 | Token counting |
| dependency-injector | 4.48.3 | DI container |
| structlog | 25.5.0 | Structured logging |

## Risks

- **OpenAI API changes**: The SDK is adding a new `responses.create()` API alongside `chat.completions.create()`. We use `chat.completions` which is stable and documented. **Mitigation**: Pin openai version.
- **qdrant-client async maturity**: Some edge cases in async mode may differ from sync. **Mitigation**: Test with real Qdrant instance.
- **tiktoken + Python 3.14**: tiktoken 0.12.0 has pre-built wheels for 3.14. **Mitigation**: Already verified working.
- **dependency-injector `.provided` chain depth**: Deep nesting may fail silently. **Mitigation**: Use `providers.Callable` fallback if needed.

## Ready for Planning

- [x] Questions answered
- [x] Approach selected
- [x] Dependencies identified
- [x] Exact API patterns documented with code examples
- [x] Patterns documented
- [x] Anti-patterns documented
- [x] Risks assessed
