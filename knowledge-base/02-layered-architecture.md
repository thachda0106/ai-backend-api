# 02 — Layered Architecture

> The goal of this architecture is simple: **protect the domain from the framework**.
> Put another way: your business logic should be runnable with no Internet connection and no database.

---

## The Dependency Rule

The single most important rule:

```
api → application → domain ← infrastructure
```

**Dependencies only point inward.** The domain knows nothing about FastAPI, Redis, Qdrant, or asyncpg. Ever.

This is enforced structurally — not just by convention:
- `domain/` contains zero `import` statements that touch `api/`, `application/`, or `infrastructure/`
- `infrastructure/` imports from `domain/` (to implement its interfaces), but `domain/` never imports back

Violating this rule is called a **leaky domain** — see `07-best-practices-and-anti-patterns.md`.

---

## Layer 1 — API (`app/api/`)

**Responsibility:** HTTP contract. Parse requests, validate schemas, call use cases, serialize responses.

**Does NOT contain:** business logic, database calls, LLM calls, domain rules.

### Structure

```
app/api/
├── routers/
│   ├── documents.py   ← POST /documents, GET /documents/{id}
│   ├── chat.py        ← POST /chat (sync + SSE streaming)
│   └── search.py      ← POST /search
├── schemas/
│   ├── document.py    ← IngestDocumentRequest, IngestDocumentResponse
│   └── chat.py        ← ChatRequest, ChatResponse, StreamEvent
├── middleware/
│   ├── rate_limit.py  ← Redis sliding window rate limiter
│   ├── request_logging.py ← Structured request logs
│   └── error_handler.py   ← Map domain exceptions → HTTP status codes
└── dependencies.py    ← FastAPI Depends() — resolves use cases from DI container
```

### What Goes Here (and Why)

```python
# ✅ CORRECT — API layer concern: HTTP validation, schema mapping, use case call
@router.post("/documents", response_model=IngestDocumentResponse)
async def ingest_document(
    request: IngestDocumentRequest,     # Pydantic validates HTTP body
    tenant: Tenant = Depends(resolve_tenant),   # auth middleware, resolved tenant
    use_case: IngestDocumentUseCase = Depends(get_ingest_use_case),
) -> IngestDocumentResponse:
    result = await use_case.execute(request, tenant.tenant_id)  # delegate ALL logic
    return result
```

```python
# 🔴 WRONG — business logic in a router
@router.post("/documents")
async def ingest_document(request: IngestDocumentRequest):
    # ❌ This belongs in the domain, NOT here
    if len(request.content.split()) < 10:
        raise HTTPException(400, "Document too short")
    chunks = request.content.split(". ")  # ❌ chunking is a domain concern
    ...
```

### Schema vs DTO — A Critical Distinction

| Concept | Location | Purpose |
|---------|---------|---------|
| `IngestDocumentRequest` (schema) | `api/schemas/` | HTTP contract — what the client sends |
| `IngestDocumentRequest` (DTO) | `application/dto/` | Application contract — what use cases accept |

They can be identical early on, but they **diverge over time**. The HTTP schema might add `Content-Type` header handling; the application DTO stays stable. Keeping them separate prevents the HTTP contract from leaking into business logic.

### Middleware Order

Starlette executes middleware in **reverse add order**. Our `main.py` adds:
1. Rate limiting (inner)
2. Request logging (outer)

So the actual execution order is: Logging → Rate Limiting → Router. Logging wraps everything including rate-limit decisions.

---

## Layer 2 — Application (`app/application/`)

**Responsibility:** Orchestrate domain objects and infrastructure calls to fulfill a single use case. Think of this as the **transaction script** layer — one use case = one user intention.

**Does NOT contain:** business rules, HTTP-specific code, SQL queries, LLM prompts.

### Structure

```
app/application/
├── use_cases/
│   ├── ingest_document.py    ← Save doc + enqueue ARQ job
│   ├── process_document.py   ← Chunk + embed + store in Qdrant (called by worker)
│   ├── rag_chat.py           ← Retrieve context → build prompt → stream LLM
│   └── search_documents.py   ← Embed query → vector search → return results
├── services/
│   ├── context_service.py    ← Token budget + score threshold for RAG context
│   └── prompt_service.py     ← Prompt template construction (injection-safe)
└── dto/
    └── document.py           ← Application-level data transfer objects
```

### Use Case Design Rules

1. **One public method:** `execute()` (or `execute()` + `stream()` for SSE)
2. **Constructor injection only:** all dependencies passed via `__init__`
3. **No direct infrastructure calls:** use abstract repositories/providers
4. **Returns a DTO, never a domain entity:** entities must not escape the application boundary (they'd carry mutable state into the HTTP response layer)

```python
class RAGChatUseCase:
    def __init__(
        self,
        search_use_case: SearchDocumentsUseCase,
        chat_provider: ChatProvider,          # ABC — OpenAI behind the scenes
        prompt_service: PromptService,
        context_service: ContextService,
        chat_history_repository: ChatHistoryRepository,  # ABC — Redis behind the scenes
        token_service: TokenService,
    ) -> None:
        ...

    async def execute(self, request: ChatRequest, tenant_id: TenantId) -> ChatResponse:
        # 1. Retrieve context (calls SearchDocumentsUseCase — another use case)
        search_results = await self.search_use_case.execute(...)

        # 2. Build context window (domain service — token budget + score filter)
        context, used_results = self.context_service.build_context(search_results)

        # 3. Build prompt (application service — prompt construction)
        messages = self.prompt_service.build_rag_prompt(query, context, history)

        # 4. Call LLM (through provider interface — not OpenAI directly)
        response = await self.chat_provider.complete(messages)

        # 5. Return DTO (not a domain entity)
        return ChatResponse(message=response.content, sources=...)
```

### The "Thin Use Case" Ideal

Use cases should be thin orchestrators. If a use case method exceeds ~50 lines, extract a domain service or application service. The logic you're hiding in the use case probably belongs in the domain.

---

## Layer 3 — Domain (`app/domain/`)

**Responsibility:** Pure business logic. No frameworks, no I/O, no side effects.

This is the heart of the system. It should be independently testable with `pytest` in under 100ms with no network calls.

### Structure

```
app/domain/
├── entities/
│   ├── base.py          ← Entity base class (id, timestamps, equality-by-id)
│   ├── tenant.py        ← Tenant (api_key_hash, plan, quota, can_accept_request)
│   ├── document.py      ← Document (tenant_id, status FSM, mark_processing/completed)
│   ├── chunk.py         ← Chunk (content, token_count, vector relationship)
│   ├── ingestion_job.py ← IngestionJob (status tracking for background processing)
│   └── user.py          ← User (per-user token usage tracking)
├── value_objects/
│   ├── base.py          ← ValueObject (frozen, equality-by-value)
│   ├── identifiers.py   ← DocumentId, ChunkId, CollectionId, TenantId, etc.
│   ├── tenant_id.py     ← TenantId value object
│   └── embedding.py     ← EmbeddingVector (tuple of floats + model + dimensions)
├── repositories/
│   ├── document_repository.py ← Abstract DocumentRepository (no asyncpg import!)
│   ├── tenant_repository.py   ← Abstract TenantRepository
│   └── vector_repository.py   ← Abstract VectorRepository (no Qdrant import!)
├── services/
│   ├── chunking_service.py        ← ChunkingStrategy ABC + SimpleChunkingStrategy
│   ├── token_aware_chunking.py    ← TokenAwareChunkingStrategy (tiktoken)
│   └── token_service.py           ← TokenService (count tokens for budgeting)
└── exceptions/
    ├── domain.py   ← DomainException, TenantQuotaExceeded, DocumentNotFound, etc.
    └── llm.py      ← LLMRateLimitException, EmbeddingException, etc.
```

### Entities vs Value Objects

| Concept | Identity | Equality | Mutability |
|---------|---------|---------|-----------|
| **Entity** | Has a unique ID | Equal if same ID (even if fields differ) | Mutable (status changes) |
| **Value Object** | No ID concept | Equal if all fields are equal | Immutable (`frozen=True`) |

```python
# Entity — identity matters
doc1 = Document(document_id=DocumentId(uuid1), title="v1", ...)
doc2 = Document(document_id=DocumentId(uuid1), title="v2", ...)
assert doc1 == doc2  # True — same ID, different title. Entity equality is ID-only.

# Value Object — all fields matter
id1 = TenantId(value=uuid1)
id2 = TenantId(value=uuid1)
assert id1 == id2  # True
id3 = TenantId(value=uuid2)
assert id1 != id3  # True — different UUID, different value object
```

### The Document Entity as a State Machine

`Document.status` is not just a field — it's a finite state machine with transitions enforced by the entity:

```
PENDING → PROCESSING → COMPLETED
                     → FAILED
```

```python
class Document(Entity):
    status: DocumentStatus = DocumentStatus.PENDING

    def mark_processing(self) -> None:
        if self.status != DocumentStatus.PENDING:
            raise InvalidStatusTransition(
                f"Cannot move to PROCESSING from {self.status}"
            )
        self.status = DocumentStatus.PROCESSING

    def mark_completed(self, chunk_count: int, token_count: int) -> None:
        if self.status != DocumentStatus.PROCESSING:
            raise InvalidStatusTransition(...)
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.token_count = token_count
```

Why? Because `document.status = "processing"` anywhere in the codebase is an unchecked string assignment. The FSM pattern ensures the transition is always valid. The infrastructure layer cannot put a document into an invalid state.

### Repository Abstractions

```python
# domain/repositories/document_repository.py
class DocumentRepository(ABC):
    """Pure interface — mentions nothing about PostgreSQL, SQL, or asyncpg."""

    @abstractmethod
    async def get_by_id(self, document_id: DocumentId) -> Document | None: ...

    @abstractmethod
    async def get_by_id_for_tenant(
        self, document_id: DocumentId, tenant_id: TenantId
    ) -> Document | None: ...

    @abstractmethod
    async def save(self, document: Document) -> Document: ...

    @abstractmethod
    async def update(self, document: Document) -> Document: ...
```

The domain defines **what** it needs. Infrastructure defines **how** to provide it. The application layer only ever sees the ABC.

### Domain Services

Domain services exist for logic that doesn't belong to any single entity:

```python
class TokenAwareChunkingStrategy(ChunkingStrategy):
    """Splits text at exact tiktoken token boundaries.

    This is a domain service because:
    - It's pure business logic (how to split text)
    - It involves no I/O
    - It belongs to the domain, not to any specific entity
    - Multiple parts of the system (ingest, re-chunk) use it
    """
    def chunk(self, content: str, chunk_size: int, chunk_overlap: int) -> list[ChunkData]:
        token_ids = self._encoder.encode(content)
        # ... sliding window logic ...
```

---

## Layer 4 — Infrastructure (`app/infrastructure/`)

**Responsibility:** Implement the domain's abstract interfaces using real external systems.

**Does NOT contain:** business rules, HTTP routing, use case orchestration.

### Structure

```
app/infrastructure/
├── db/
│   └── postgres_pool.py           ← asyncpg pool lifecycle
├── repositories/
│   ├── postgres_document_repo.py  ← Implements DocumentRepository via asyncpg
│   ├── postgres_tenant_repo.py    ← Implements TenantRepository + Redis cache-aside
│   ├── memory_document_repo.py    ← In-memory (tests/dev only)
│   └── redis_chat_repo.py         ← Chat history in Redis
├── vector_db/
│   └── qdrant_adapter.py          ← Implements VectorRepository via Qdrant
├── llm/
│   ├── openai_chat.py             ← Implements ChatProvider via OpenAI
│   └── openai_embedding.py        ← Implements EmbeddingProvider with cache-aside
├── cache/
│   ├── redis_cache.py             ← Raw Redis client with typed helpers
│   └── rate_limiter.py            ← Sliding window rate limiter (Lua script)
├── queue/
│   └── arq_worker.py              ← ARQ task function + worker settings
└── token/
    └── tiktoken_service.py        ← Token counting (domain service implementation)
```

### The Repository Pattern in Practice

```python
# infrastructure/repositories/postgres_document_repo.py
class PostgresDocumentRepository(DocumentRepository):  # implements domain ABC
    def __init__(self, pool: PostgresPool) -> None:
        self._pool = pool

    async def save(self, document: Document) -> Document:
        content_hash = hashlib.sha256(document.content.encode()).hexdigest()
        await self._pool.execute(
            """
            INSERT INTO documents (
                document_id, tenant_id, collection_id, title, content,
                content_hash, status, chunk_count, token_count,
                error_message, metadata, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT (document_id) DO NOTHING
            """,
            document.document_id.value,
            document.tenant_id.value,
            # ...
        )
        return document
```

💡 **Senior Insight:** `ON CONFLICT DO NOTHING` makes save() idempotent. If the ARQ worker crashes after saving but before enqueuing, the retry will call `save()` again harmlessly.

### Redis as a Multi-Purpose Layer

Redis serves three different roles in this system:

```
1. Embedding cache
   key: "embed:{sha256(text)}:{model}"
   value: JSON array of float64
   TTL: 24 hours

2. Rate limiting
   key: "rate:{api_key_prefix}"
   value: sorted set of timestamps (sliding window)
   TTL: 60 seconds

3. ARQ job queue (built into ARQ)
   key: "arq:queue"
   value: sorted set of job payloads
```

Each role uses a different Redis key prefix and TTL, but **the same Redis cluster**. This is fine at current scale. At higher scale, consider splitting into dedicated Redis instances per role.

---

## Dependency Injection Container (`app/container.py`)

The DI container is the **composition root** — the only place where concrete implementations are bound to abstractions.

```python
class Container(containers.DeclarativeContainer):
    # Abstract: DocumentRepository
    # Concrete: PostgresDocumentRepository
    document_repository = providers.Singleton(
        PostgresDocumentRepository,
        pool=postgres_pool,
    )

    # Use case gets the ABC — doesn't know it's PostgreSQL
    ingest_document = providers.Factory(
        IngestDocumentUseCase,
        document_repository=document_repository,  # injected as ABC
        arq_pool=arq_pool,
    )
```

In tests, you replace concrete providers with mocks:
```python
container.document_repository.override(providers.Object(mock_repo))
```

📐 **Rule:** The container is the **only place** where `InMemoryDocumentRepository` and `PostgresDocumentRepository` are named. Everywhere else sees `DocumentRepository`.

---

## Data Flow Between Layers (Summary)

```
HTTP Request
     │
     ▼
[api/routers] — Pydantic validates schema, resolves use case via DI
     │
     ▼ passes DTO
[application/use_cases] — orchestrates, calls domain + infra abstractions
     │                  └── calls [domain/entities] for business rules
     │                  └── calls [domain/services] for domain logic
     │
     ▼ calls ABCs
[infrastructure/] — concrete implementations (SQL, Redis, OpenAI, Qdrant)
     │
     ▼
External Systems (PostgreSQL, Redis, Qdrant, OpenAI)
```

Returning data flows in reverse order — but **entities are never returned above the application layer**. The use case maps entities to DTOs before returning to the API layer.
