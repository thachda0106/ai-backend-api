# 04 — Database & Redis & Qdrant

> The data layer has three distinct storage systems, each chosen for what it does best. Understanding when to use each is critical.

---

## PostgreSQL — Relational Persistence

### Schema Design

```sql
-- Full schema in scripts/migrate.sql

-- TENANTS: the multi-tenancy root
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL UNIQUE,
    name            VARCHAR(255) NOT NULL,
    api_key_hash    VARCHAR(64) NOT NULL UNIQUE,  -- SHA-256, never plaintext
    plan            VARCHAR(50) NOT NULL DEFAULT 'free',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    tokens_used_this_month  BIGINT NOT NULL DEFAULT 0,
    total_tokens_used       BIGINT NOT NULL DEFAULT 0,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DOCUMENTS: core content store
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL UNIQUE,
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    collection_id   UUID NOT NULL,
    title           VARCHAR(1024) NOT NULL,
    content         TEXT NOT NULL,
    content_type    VARCHAR(100) NOT NULL DEFAULT 'text/plain',
    content_hash    VARCHAR(64),         -- SHA-256 for deduplication
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    token_count     INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- INGESTION_JOBS: background processing state machine
CREATE TABLE ingestion_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL UNIQUE,
    tenant_id       UUID NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    document_id     UUID NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    status          VARCHAR(50) NOT NULL DEFAULT 'queued',
    total_chunks    INTEGER NOT NULL DEFAULT 0,
    processed_chunks INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    arq_job_id      VARCHAR(255),        -- ARQ's own job reference
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Indexing Strategy

Every index in this schema serves a specific query pattern:

```sql
-- Tenant lookups by API key (every request) — must be O(1)
CREATE INDEX idx_tenants_api_key_hash ON tenants(api_key_hash);

-- Document list for a tenant's collection (dashboard/admin)
CREATE INDEX idx_documents_collection_id ON documents(tenant_id, collection_id);

-- Monitor stuck jobs (ops dashboard)
CREATE INDEX idx_documents_status ON documents(tenant_id, status);

-- Deduplication check on ingestion
CREATE INDEX idx_documents_content_hash ON documents(tenant_id, content_hash)
    WHERE content_hash IS NOT NULL;  -- partial index: only rows with a hash

-- Job monitoring for a tenant
CREATE INDEX idx_ingestion_jobs_status ON ingestion_jobs(tenant_id, status);
```

💡 **Senior Insight:** The partial index on `content_hash` is significant. Without `WHERE content_hash IS NOT NULL`, PostgreSQL includes all rows in the index even if most have NULL hashes. The partial index is smaller, faster to build, and cheaper for the query planner.

### The `updated_at` Trigger Pattern

All tables use triggers to auto-update `updated_at`:

```sql
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

Why not let the application set `updated_at`? Because:
1. You'd have to remember to set it in every `UPDATE` call
2. If you forget in one place — silently stale
3. The trigger is **guaranteed**, even for direct SQL from migrations, scripts, or other services

### Repository Pattern Implementation

The repository pattern hides SQL from the domain. Here's what a real query looks like:

```python
# postgres_document_repo.py
async def find_duplicate(self, tenant_id: TenantId, content: str) -> Document | None:
    """Find an existing document with identical content via SHA-256 hash."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    row = await self._pool.fetchrow(
        "SELECT * FROM documents WHERE tenant_id = $1 AND content_hash = $2 LIMIT 1",
        tenant_id.value,
        content_hash,
    )
    return self._row_to_document(row) if row else None
```

The domain only calls `repository.find_duplicate(tenant_id, content)`. It never sees the SQL, the hash, or asyncpg. Swapping to SQLAlchemy or a different hash algorithm requires changing only the infrastructure layer.

### Transactions — When and Why

This codebase uses **implicit per-statement transactions** (asyncpg defaults). We don't use explicit `BEGIN/COMMIT` blocks for most operations because:

1. Each repository method is a single operation
2. Application-level coordination via the domain objects (status transitions) handles logical consistency

**When you DO need explicit transactions:**

If you need to update two tables atomically (e.g., mark document FAILED and insert into an error audit table simultaneously), use:

```python
async with self._pool.pool.acquire() as conn:
    async with conn.transaction():
        await conn.execute("UPDATE documents SET status='failed' WHERE document_id=$1", doc_id)
        await conn.execute("INSERT INTO document_errors (...) VALUES (...)", ...)
```

⚠️ **Footgun:** The `PostgresPool` helper methods (`execute`, `fetch`, `fetchrow`) acquire a connection from the pool for each call. They do NOT share a connection. If you need a transaction spanning two calls, you must use `pool.pool.acquire()` directly.

---

## Redis — Cache + Rate Limit + Queue

### Role 1: Embedding Cache

```python
# Key structure
key   = f"embed:{sha256(text).hexdigest()}:{model_name}"
value = json.dumps([0.023, -0.441, 0.112, ...])  # 1536 floats
TTL   = 86400  # 24 hours

# Read path (cache-aside)
async def embed(self, text: str) -> EmbeddingVector:
    cached = await self._cache.get_embedding(text, model)
    if cached:
        return cached  # 0 OpenAI calls, ~1ms Redis GET
    vector = await self._call_openai([text], model)
    await self._cache.set_embedding(text, model, vector)
    return vector
```

**Economics:** At OpenAI `text-embedding-3-small` pricing (~$0.02 per 1M tokens), a 512-token chunk costs ~$0.00001. But if you embed the same chunk 1000 times (popular document, repeated searches), that's $0.01. The Redis call costs ~$0.000001. Cache hit ratio of 80%+ is very achievable for a knowledge base with repeated queries.

### Role 2: Rate Limiting (Atomic Lua)

Rate limiting must be **atomic**. The original implementation had a TOCTOU (time-of-check-time-of-update) race:

```python
# ❌ RACE CONDITION — two concurrent requests both see count=59, both allowed
pipe.zremrangebyscore(key, '-inf', window_start)
pipe.zcard(key)           # sees 59 — both requests read this
pipe.zadd(key, {now: now})  # both add → count becomes 61
results = await pipe.execute()
if results[1] < 60:       # 59 < 60 → both allowed 🐛
    return True
```

The fix: a **Lua script** — Redis executes it atomically (single-threaded):

```lua
-- Executed as one atomic Redis operation
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
    redis.call('EXPIRE', key, math.ceil(window))
    return 1  -- allowed
end
return 0      -- denied
```

💡 **Senior Insight:** No other request can interleave between the `ZCARD` and `ZADD` because Redis is single-threaded in its command execution. Lua scripts are the correct tool for any Redis operation that requires read-then-write atomicity.

### Role 3: Tenant API Key Cache

```python
# Cache-aside for tenant lookup
# Every HTTP request needs the tenant — this MUST be fast

cache_key = f"tenant:key:{api_key_hash}"  # hash of SHA-256 hash
cached_json = await redis.get(cache_key)

if cached_json:
    return Tenant(**json.loads(cached_json))   # ~1ms, no DB

row = await postgres.fetchrow(                  # ~5-20ms
    "SELECT * FROM tenants WHERE api_key_hash = $1", api_key_hash
)
tenant = Tenant.from_row(row)
await redis.setex(cache_key, 300, tenant.model_dump_json())  # TTL: 5 minutes
return tenant
```

**Invalidation:** When a tenant is updated (plan change, deactivation), the repository calls:
```python
await self._cache.delete(f"tenant:key:{tenant.api_key_hash}")
```

⚠️ **Footgun:** If a tenant is deactivated but the cache hasn't expired, they can still make requests for up to 5 minutes. This is an acceptable trade-off (vs. making every request hit PostgreSQL). For security-critical deactivations (compromise, fraud), manually flush the key and restart all API instances.

---

## Qdrant — Vector Database

### Why a Dedicated Vector Database?

PostgreSQL with `pgvector` can store embeddings, but:

| Factor | pgvector | Qdrant |
|--------|---------|--------|
| Index type | IVFFlat / HNSW | HNSW only (optimized) |
| Payload indexing | No | Yes (keyword, integer, float) |
| Quantization | No | Int8, Binary |
| Filtering | Sequential scan + index | True filtered HNSW |
| Max dimensions | 2000 | 65536 |
| gRPC support | No | Yes |

The critical advantage here is **filtered HNSW**. In a multi-tenant system, every search must filter by `tenant_id`. With pgvector, that filter happens **after** ANN search (approximate nearest neighbors), requiring a larger `top_k` and post-filter. Qdrant filters **during** the HNSW traversal — the index ignores wrong-tenant vectors entirely.

### Collection Setup

```python
await qdrant_client.create_collection(
    collection_name="documents",
    vectors_config=VectorParams(
        size=1536,          # text-embedding-3-small dimensions
        distance=Distance.COSINE,
    ),
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type=ScalarType.INT8,  # 4x memory reduction
            quantile=0.99,         # 99th percentile for calibration
            always_ram=True,       # quantized vectors stay in RAM
        )
    ),
)
```

**Scalar Quantization (INT8):** converts each 32-bit float in the embedding vector to an 8-bit integer. A 1536-dim vector goes from 6KB to 1.5KB. For 1M chunks, that's 6GB → 1.5GB in RAM. The recall loss is typically < 1% with proper calibration.

### Payload Indexes — Critical for Multi-Tenant

```python
indexed_fields = [
    ("tenant_id",     PayloadSchemaType.KEYWORD),  # UUID string
    ("collection_id", PayloadSchemaType.KEYWORD),  # UUID string
    ("document_id",   PayloadSchemaType.KEYWORD),  # UUID string
]

for field, schema in indexed_fields:
    await client.create_payload_index(
        collection_name="documents",
        field_name=field,
        field_schema=schema,
    )
```

Without these indexes, every filtered search triggers a **full payload scan** before HNSW traversal. With 1M vectors across 1000 tenants, that's scanning 1M payloads to find 1K tenant-specific vectors before even running vector similarity. The index makes filtering O(log N).

### Vector Payload Structure

Each vector point stores this payload alongside the embedding:

```json
{
  "tenant_id":      "550e8400-e29b-41d4-a716-446655440000",
  "collection_id":  "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "document_id":    "9e107d9d-372b-b434-9e1d-c1c5f6b58e42",
  "content":        "FastAPI supports CORS via CORSMiddleware which should be added...",
  "document_title": "FastAPI Best Practices",
  "chunk_index":    3,
  "token_count":    487
}
```

💡 **Senior Insight:** Storing `content` in the payload avoids a round-trip to PostgreSQL on every search. The trade-off: payload storage increases. For 1M chunks × ~2KB avg content = ~2GB payload storage. At current scale this is fine. At 10M chunks, consider storing only `chunk_id` in payload and fetching content from PostgreSQL in batch.

### Search Isolation Guarantee

```python
async def search(self, query_embedding, top_k, tenant_id=None):
    filter_conditions = []

    # Tenant filter ALWAYS injected first if provided
    if tenant_id is not None:
        filter_conditions.append(
            FieldCondition(key="tenant_id", match=MatchValue(value=str(tenant_id.value)))
        )

    query_filter = Filter(must=filter_conditions) if filter_conditions else None
    # ...
```

Even if a bug in the application layer forgets to pass `tenant_id`, the filter is still applied as long as the dependency is provided. This is defense in depth — the vector store enforces isolation, not trusting the calling code to always get it right.
