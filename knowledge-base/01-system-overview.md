# 01 — System Overview

> **Read this first.** Everything else in this knowledge base assumes you understand this document.

---

## What Is This System?

The **AI Backend API** is a multi-tenant RAG (Retrieval-Augmented Generation) platform. It allows multiple isolated tenants (organizations/API consumers) to:

1. **Ingest documents** — upload text documents that get chunked, embedded (vectorized), and stored
2. **Search documents semantically** — find relevant content using semantic similarity, not keyword matching
3. **Chat with their documents** — ask natural-language questions and receive answers grounded in their stored context

Under the hood:
- **FastAPI** handles all HTTP traffic
- **PostgreSQL** stores documents, tenants, and job state durably
- **Redis** provides embedding/response caching, rate limiting, and the background job queue (ARQ)
- **Qdrant** stores and searches high-dimensional embedding vectors
- **OpenAI** generates text embeddings and LLM completions

---

## Why a Monolith (Not Microservices)?

This is a deliberate choice. Here's the reasoning:

### Arguments for Monolith Here

| Factor | Why Monolith Wins |
|--------|-------------------|
| **Team size** | Small team. Microservice overhead (service mesh, inter-service auth, distributed tracing) costs more than it saves |
| **Data cohesion** | Documents, chunks, and ingestion jobs are tightly related. Splitting them across services creates distributed joins |
| **Operational simplicity** | One Docker image, one deployment unit, one log stream to chase |
| **Latency** | Intra-process calls are nanoseconds. HTTP calls between microservices add 1–10ms per hop — catastrophic for a chat streaming pipeline |
| **Transaction boundary** | Saving a document + creating an ingestion job must be atomic. In microservices, this becomes a two-phase commit or saga — both are hard |
| **Early stage** | You don't know the true service boundaries until you've run production traffic. Premature decomposition locks you into bad boundaries |

### Where Microservice Thinking Still Applies

Even as a monolith, this system respects **logical service boundaries**:

- The `domain` layer has zero dependency on FastAPI, Redis, or anything external
- Infrastructure adapters implement domain interfaces (`VectorRepository`, `DocumentRepository`) — swap Qdrant for Weaviate without touching a use case
- The ARQ worker runs as a **separate process** (same codebase, different entrypoint) — it's already horizontally scalable

### When to Break It Apart

See `06-scalability-strategy.md` for the full analysis. Short version: break out the **embedding worker** first when it becomes a bottleneck, before anything else.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (HTTP/SSE)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼────────────────────────────────────┐
│                    LOAD BALANCER / API GATEWAY                  │
│              (rate limiting, TLS termination, routing)          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   FASTAPI  (api/ layer)                         │
│   Routers → Schema validation → Auth middleware → Use cases     │
└──────┬──────────────────────────────────────────────────────────┘
       │ calls (in-process, no HTTP)
┌──────▼──────────────────────────────────────────────────────────┐
│              APPLICATION  (application/ layer)                  │
│        Use cases orchestrate domain → call infrastructure       │
└──────┬──────────────────────────────────────────────────────────┘
       │ pure domain operations
┌──────▼──────────────────────────────────────────────────────────┐
│                 DOMAIN  (domain/ layer)                         │
│      Entities · Value Objects · Domain Services · ABCs          │
│   Zero framework dependencies. Pure Python business logic.      │
└──────┬──────────────────────────────────────────────────────────┘
       │ calls through interfaces (ABCs)
┌──────▼──────────────────────────────────────────────────────────┐
│            INFRASTRUCTURE  (infrastructure/ layer)              │
│  PostgreSQL · Redis · Qdrant · OpenAI · ARQ queue               │
└─────────────────────────────────────────────────────────────────┘

Async worker (separate OS process, same codebase):
Redis Queue (ARQ) → [arq_worker.py] → PostgreSQL + Qdrant + OpenAI
```

---

## Sync vs Async Flow

### Synchronous (request/response)

```
POST /chat → RAGChatUseCase → search Qdrant → call OpenAI → SSE stream back
```
Every step happens in the same request lifecycle. The client waits.

### Asynchronous (fire-and-forget)

```
POST /documents → IngestDocumentUseCase → save to PostgreSQL → enqueue in Redis (ARQ)
                                                                    ↓
                                                          [ARQ Worker Process]
                                                          extract → chunk → embed → store in Qdrant
```
The HTTP request returns immediately with `202 Accepted`. Processing happens in a worker process, tracked via `IngestionJob` status.

### Why This Split?

Document ingestion can take 10–120 seconds (large documents, batched embedding calls, OpenAI rate limits). Keeping that in-band with the HTTP request would:
- Tie up a Uvicorn worker for the full duration
- Cause clients to time out
- Make progress reporting impossible

---

## Tenant Model

Every piece of data is owned by a `Tenant`:

```
Tenant (api_key_hash, plan, token_quota)
  └── Documents (tenant_id, collection_id)
       └── Chunks (tenant_id, document_id)  → stored in Qdrant
```

Isolation is enforced at **two levels**:
1. **PostgreSQL** — every query is scoped by `tenant_id` column (row-level isolation)
2. **Qdrant** — every vector search injects `must: [FieldCondition(tenant_id)]` filter (payload index, not full scan)

There is no separate schema or collection per tenant — this is a **shared-everything** design with logical isolation, which keeps operational complexity low.

---

## Technology Choices: The Reasoning

| Technology | Why This One | Trade-off |
|------------|-------------|-----------|
| **FastAPI** | Async-native, automatic OpenAPI docs, Pydantic validation | More opinionated than Flask; less battle-tested than Django |
| **asyncpg** | Fastest PostgreSQL async driver for Python | No ORM — SQL must be written by hand |
| **Qdrant** | gRPC support, payload indexing, quantization, Docker-friendly | Newer than Pinecone/Weaviate, smaller ecosystem |
| **ARQ** | Minimal, async-native, Redis-backed — no Celery overhead | Fewer features than Celery; no scheduled tasks built-in |
| **Redis** | Ubiquitous, fast, handles cache + rate limit + queue | Single point of failure if not clustered |
| **dependency-injector** | Explicit DI without magic decorators | Verbose container definition; requires wiring |
| **structlog** | JSON-native structured logging | More setup than `logging`; requires understanding processors |
