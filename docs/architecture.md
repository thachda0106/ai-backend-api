# Architecture

## Overview

Clean Architecture with 4 clear layers. Dependency arrows point inward — outer layers depend on inner layers, never the reverse.

```
┌─────────────────────────────────────────┐
│  Interface Layer  (api/)                │  ← FastAPI routers, schemas
├─────────────────────────────────────────┤
│  Application Layer (application/)       │  ← Use cases, DTOs, app services
├─────────────────────────────────────────┤
│  Domain Layer  (domain/)                │  ← Entities, value objects, interfaces
├─────────────────────────────────────────┤
│  Infrastructure Layer (infrastructure/) │  ← Concrete adapters (Qdrant, Redis, LLM)
└─────────────────────────────────────────┘
```

---

## Layer Detail

### Domain Layer (`app/domain/`)

Pure Python — no framework imports, no I/O.

| Component | Description |
|-----------|-------------|
| `entities/` | `Document`, `Chunk`, `IngestionJob`, `ChatMessage`, `SearchResult` |
| `value_objects/` | `DocumentId`, `CollectionId`, `Embedding`, `Pagination` |
| `repositories/` | Abstract interfaces: `DocumentRepository`, `VectorRepository`, `ChatHistoryRepository` |
| `services/` | `ChunkingStrategy` (abstract + `SimpleChunkingStrategy`), `TokenService` |
| `exceptions/` | Domain-specific exception hierarchy |

### Application Layer (`app/application/`)

Orchestrates domain objects and repository interfaces.

| Component | Description |
|-----------|-------------|
| `use_cases/ingest_document.py` | Save document → create job → mark processing → enqueue |
| `use_cases/process_document.py` | Chunk → embed → upsert to vector store |
| `use_cases/search_documents.py` | Embed query → vector search → map to DTOs |
| `use_cases/rag_chat.py` | Search → build context → prompt LLM → stream response |
| `services/` | `ContextService`, `PromptService` | Build prompts and context windows |
| `dto/` | Request/response data transfer objects |

### Infrastructure Layer (`app/infrastructure/`)

Concrete implementations of domain interfaces.

| Component | Technology |
|-----------|-----------|
| `vector_db/qdrant.py` | Qdrant via `qdrant-client` |
| `cache/redis.py` | Redis via `redis-py` asyncio |
| `llm/openai_provider.py` | OpenAI chat + embeddings |
| `queue/worker.py` | Redis-backed background worker |
| `repositories/` | Concrete implementations of domain repository interfaces |
| `token/tiktoken_service.py` | Token counting via `tiktoken` |

### Interface Layer (`app/api/`)

FastAPI routing — thin layer, maps HTTP ↔ DTOs.

| Component | Description |
|-----------|-------------|
| `routers/documents.py` | `POST /documents` — ingest |
| `routers/search.py` | `POST /search` — semantic search |
| `routers/chat.py` | `POST /chat` — RAG chat with streaming |
| `middleware/` | Rate limiting, request logging, error handling |
| `dependencies/` | FastAPI DI wrappers over DI container |

---

## Data Flows

### Ingestion Pipeline

```
Client POST /documents
  → IngestDocumentUseCase
      → DocumentRepository.save()           (persist metadata)
      → Document.mark_processing()
      → BackgroundWorker.enqueue(process)
          → ProcessDocumentUseCase
              → ChunkingService.chunk()
              → EmbeddingProvider.embed_many()
              → VectorRepository.upsert()
              → Document.mark_completed()
```

### RAG Chat Pipeline

```
Client POST /chat
  → RAGChatUseCase
      → SearchDocumentsUseCase
          → EmbeddingProvider.embed(query)
          → VectorRepository.search()
      → ContextService.build_context(results)
      → PromptService.build_prompt(context, message)
      → ChatProvider.stream(prompt)
          → SSE tokens → response
```

---

## Dependency Injection

The DI container (`app/container.py`) wires all layers together using `dependency-injector`. Interfaces (domain) are satisfied by implementations (infrastructure) at container construction time. Use cases receive repo interfaces — never concrete adapters.

```python
# container.py (simplified)
vector_repository = providers.Singleton(QdrantVectorRepository, ...)
search_use_case   = providers.Singleton(SearchDocumentsUseCase,
                        embedding_provider=embedding_provider,
                        vector_repository=vector_repository,
                        ...)
```

This makes unit testing trivial — inject mocks instead of real adapters.

---

## Infrastructure (AWS)

```
Internet → ALB (HTTPS) → ECS Fargate API tasks
                               ├── ElastiCache Redis (private subnet)
                               └── Qdrant on ECS Fargate (EFS persistent storage)

ECR → ECS (image pull)
CloudWatch + SNS → ops email (CPU/memory/5xx alarms)
```

See [`terraform/`](../terraform/) for Terraform modules.

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Clean Architecture | Enables infrastructure swaps without touching business logic |
| Pydantic entities | Validation at construction; frozen value objects; no dataclass inconsistencies |
| Qdrant on EFS | EFS provides POSIX-compatible persistence for Fargate; `memmap` storage mode for large collections |
| S3 native locking | `use_lockfile = true` in Terraform >= 1.7; no DynamoDB table needed |
| SSE streaming | Lower latency UX for chat; single HTTP connection, no WebSocket complexity |
