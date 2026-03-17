# 06 — Scalability Strategy

> This monolith is designed to scale horizontally. Here's what that looks like at each growth stage, and when the decision to decompose becomes inevitable.

---

## Current Architecture Scaling Ceiling

Before optimization, honest capacity estimates:

| Component | Bottleneck | Rough Ceiling |
|-----------|----------|---------------|
| FastAPI (single pod) | CPU / event loop | ~500-1000 RPM |
| PostgreSQL (single node) | Write IOPS / connections | ~5K writes/sec |
| Redis (single node) | Memory / bandwidth | ~100K ops/sec |
| Qdrant (single node) | RAM (vectors + indexes) | ~10M vectors |
| ARQ worker (single pod) | CPU / OpenAI rate limits | ~50 docs/min |
| OpenAI (text-embedding-3-small) | Rate limits | 500K tokens/min (default tier) |

"Production" for a well-funded B2B SaaS might mean 1M requests/day = ~700 RPM. That's one properly configured pod. This monolith can handle serious load before it needs horizontal scaling.

---

## Stage 1: Single Pod (0 → 5K RPM)

### Configuration

```yaml
# docker-compose.yml or Kubernetes Deployment
api:
  replicas: 1
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
worker:
  replicas: 2
  command: arq app.infrastructure.queue.arq_worker.ArqWorkerSettings
```

### Key settings

```bash
# Gunicorn/Uvicorn: workers = 2 * CPU_cores + 1
# For 2-core machine: 5 workers
uvicorn app.main:app --workers 5 --worker-class uvicorn.workers.UvicornWorker
```

⚠️ **Footgun — workers vs. async:** A single Uvicorn worker with asyncio handles thousands of concurrent I/O-bound requests. Multiple workers multiply that. But each worker has its own event loop and its own DI container — there's no shared in-process state, which is fine because all state lives in Redis/PostgreSQL.

---

## Stage 2: Horizontal API Scaling (5K → 50K RPM)

### Stateless Design

The API is designed to be stateless:
- No in-memory session state
- No in-process caches (only Redis external cache)
- No sticky sessions required

This means adding API pods is trivially safe:

```
Load Balancer
├─ api-pod-1 (AWS/GCP/k8s)
├─ api-pod-2
├─ api-pod-3
└─ api-pod-N
All share:
└─ PostgreSQL (single primary)
└─ Redis cluster
└─ Qdrant cluster
```

### Scaling Workers Independently

Workers and API pods scale independently:

```bash
# Scale API for request volume
kubectl scale deployment api --replicas=10

# Scale workers for ingestion backlog
kubectl scale deployment worker --replicas=5
```

This is the key advantage of the ARQ architecture: **the queue absorbs backpressure**. If ingest volume spikes:
- API pods accept requests, enqueue to ARQ
- ARQ queue grows
- Add more workers to drain the queue
- No API changes, no code changes

---

## Stage 3: Database Scaling

### PostgreSQL Bottlenecks

At high write volumes:

**Problem 1:** Single primary PostgreSQL write bottleneck for document inserts

**Solution:** Read replicas for all read queries

```python
class PostgresPool:
    def __init__(self, settings):
        self._write_pool = ...  # primary
        self._read_pool = ...   # replica(s)

    async def fetch(self, query, *args):
        return await self._read_pool.fetch(query, *args)  # reads → replica

    async def execute(self, query, *args):
        return await self._write_pool.execute(query, *args)  # writes → primary
```

**Problem 2:** Content storage — very large TEXT fields for full documents

**Solution:** Move raw content to object storage (S3/GCS), store only a URL in PostgreSQL. This reduces row size, improves index performance, and enables efficient content streaming.

### Redis Scaling

Redis single-node becomes a bottleneck around 100K ops/sec (embedding cache hits). Solutions:

1. **Redis Cluster:** Shard keys across multiple nodes automatically
2. **Read replicas:** Route `GET` operations to replicas, `SET` to primary

For the rate limiter Lua script, it **must** run on the primary — the Lua script is a read-write operation. Route rate limit keys to specific cluster slots to avoid cross-node coordination.

### Qdrant Scaling

```yaml
# Qdrant distributed mode
qdrant-node-1:
  environment:
    QDRANT__CLUSTER__ENABLED: "true"
    QDRANT__CLUSTER__P2P__PORT: 6335

qdrant-node-2:
  environment:
    QDRANT__CLUSTER__ENABLED: "true"
    QDRANT__CLUSTER__P2P__PORT: 6335
```

In distributed Qdrant, collections are sharded across nodes. Scalar quantization becomes even more important — 4x memory reduction means a 3-node cluster handles 4x more vectors.

---

## Stage 4: Caching Strategy Evolution

### Layer 1: Embedding Cache (Already Implemented)

- **What:** OpenAI embedding results cached in Redis by content hash
- **Cache hit speed:** ~1ms vs ~200ms for OpenAI
- **TTL:** 24 hours
- **Hit ratio target:** >80% for a mature knowledge base with repeated queries

### Layer 2: Search Result Cache (Future)

Cache vector search results for identical embedding vectors:

```python
# Cache key: sha256(embedding_values_json) + collection_id + top_k
cache_key = f"search:{sha256(str(embedding.values))}:{collection_id}:{top_k}"
cached_results = await redis.get(cache_key)
if cached_results:
    return json.loads(cached_results)  # ~1ms vs ~20ms Qdrant search

results = await qdrant.search(...)
await redis.setex(cache_key, 300, json.dumps([r.dict() for r in results]))
```

**TTL consideration:** Search cache must be invalidated when new documents are ingested. Short TTL (5 min) is safer than manual invalidation. For real-time knowledge bases, skip this cache.

### Layer 3: LLM Response Cache (Future, Careful)

Caching LLM responses is tempting but dangerous:

```python
# Only cache if: same question + same context + same model + same temperature
cache_key = f"llm:{sha256(str(messages_json))}"
# TTL: should be short (10-30 min) — context changes as new docs are ingested
```

⚠️ **Never cache non-deterministic LLM responses long-term.** If the underlying knowledge base changes, cached answers become stale. Use this only for identical repeated queries in a static knowledge base.

---

## Stage 5: Breaking Apart the Monolith

The decision to extract services should be **demand-driven**, not speculative. Here's the order:

### Phase 1: Extract Embedding Service

**Signal:** >80% of OpenAI costs are embedding, not chat. Worker pods saturate. Embedding latency affects chat response time.

**How:**
- Create a microservice API: `POST /embed {texts: [...]} → {embeddings: [...]}`
- Shared Redis cache sits in front of this service
- Both API pods and worker pods call this service
- Enables independent scaling of embedding capacity

### Phase 2: Extract Document Processing Worker

**Signal:** Ingestion backlog regularly exceeds 1000 jobs. Worker resource (GPU for local models, memory for chunking) differs from API resource needs.

**How:**
- Worker becomes a separate deployable with its own Docker image
- Communicates with API via PostgreSQL (shared DB, not cross-service API)
- This is already largely done — the ARQ worker runs as a separate process

### Phase 3: Extract Tenant/Auth Service

**Signal:** Multiple products share the same tenant/API-key system. Auth logic needs to be consistent across services.

**How:**
- Tenant service becomes a source-of-truth API with JWT issuance
- Current API key validation replaced by JWT validation (zero-DB on each request)
- This is the most disruptive extraction — do it last

### Rule: Never Extract for Technical Reasons Alone

Only extract a service if it has a **different scaling dimension** or **different deployment lifecycle** from the rest of the system. "Clean architecture" in a monolith is not a reason to split into microservices.

---

## Performance Tuning Checklist

```
Database:
  ☐ All WHERE clauses use indexed columns
  ☐ EXPLAIN ANALYZE run on all high-frequency queries
  ☐ Connection pool sized (not unlimited)
  ☐ Read replicas for heavy read workloads

Redis:
  ☐ maxmemory policy set (allkeys-lru for cache)
  ☐ AOF persistence enabled (especially for rate limiter data)
  ☐ Monitor keyspace evictions (means cache too small)

Qdrant:
  ☐ Scalar quantization enabled (INT8)
  ☐ Payload indexes on tenant_id, collection_id
  ☐ HNSW indexing_threshold tuned (20K default)
  ☐ gRPC enabled for Python client (5-10x faster than REST)

Application:
  ☐ Embedding batch size maximized (batch all uncached texts in one call)
  ☐ Score threshold configured (don't embed irrelevant context)
  ☐ Uvicorn worker count = 2 * CPU + 1

OpenAI:
  ☐ Use text-embedding-3-small (5x cheaper than ada-002, same quality)
  ☐ Monitor tokens/minute usage vs. tier limit
  ☐ Circuit breaker on OpenAI calls (prevent cascade failure)
```
