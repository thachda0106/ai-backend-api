# 07 — Best Practices and Anti-Patterns

> Most architectural problems are discovered in code review, not in production. This document is your code review checklist.

---

## Anti-Pattern 1: Fat Controller (Fat Router) 🔴

The most common mistake in FastAPI codebases.

### What It Looks Like

```python
# ❌ WRONG — router doing business logic, SQL, and LLM calls
@router.post("/chat")
async def chat(request: ChatRequest, db: asyncpg.Connection = Depends(get_db)):
    # Business logic in the router — wrong layer
    if len(request.message) > 4000:
        raise HTTPException(422, "Message too long")

    # SQL in the router — wrong layer
    doc_rows = await db.fetch("SELECT content FROM documents WHERE ...")

    # LLM call in the router — wrong layer
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = await openai_client.chat.completions.create(...)

    return {"message": response.choices[0].message.content}
```

### Why This Is Bad

1. Untestable without running a real server + database + OpenAI
2. Logic is duplicated if another endpoint needs the same flow
3. You can't swap the LLM provider without touching the router
4. Business rules (message length limit) are scattered across routers

### The Correct Pattern

```python
# ✅ CORRECT — router delegates everything to use case
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    tenant: Tenant = Depends(resolve_tenant),
    use_case: RAGChatUseCase = Depends(get_rag_chat_use_case),
) -> ChatResponse:
    return await use_case.execute(request, tenant.tenant_id)

# Test this router with:
# - Mocked use_case (returns a ChatResponse)
# - No database, no Redis, no OpenAI needed
```

---

## Anti-Pattern 2: Business Logic in Infrastructure 🔴

Repositories and adapters should be mechanical. If they contain `if/else` logic beyond mapping concerns, that's a smell.

### What It Looks Like

```python
# ❌ WRONG — PostgresDocumentRepository has business knowledge
class PostgresDocumentRepository(DocumentRepository):
    async def save(self, document: Document) -> Document:
        # ❌ Business rule ("free plan max 100 docs") in infrastructure
        if document.tenant.plan == "free":
            count = await self._pool.fetchval(
                "SELECT COUNT(*) FROM documents WHERE tenant_id=$1", tenant_id
            )
            if count >= 100:
                raise PlanLimitExceeded("Free plan limit: 100 documents")
        # ...
```

### The Correct Pattern

```python
# ✅ CORRECT — quota check is a domain concern (Tenant entity)
class RAGChatUseCase:
    async def execute(self, request, tenant_id):
        tenant = await self.tenant_repo.get_by_id(tenant_id)

        # Quota check belongs in the use case (or domain entity)
        if not tenant.can_accept_request():
            raise TenantQuotaExceeded(tenant.plan)

        # Infrastructure call — only after business validation
        document = await self.document_repository.save(document)
```

---

## Anti-Pattern 3: Leaky Domain 🔴

The domain layer importing anything from infrastructure or framework layers.

### Detection: Run This Grep

```bash
# This should return ZERO results
grep -r "import redis\|import asyncpg\|import openai\|from fastapi\|from qdrant_client" \
  app/domain/
```

If you find any, the domain is leaking. Fix immediately.

### Common Leaks and Fixes

```python
# ❌ WRONG — domain entity importing aioredis
from redis.asyncio import Redis

class Tenant(Entity):
    async def refresh_cache(self, redis: Redis):  # infrastructure dependency!
        ...

# ✅ CORRECT — domain entity is pure data + logic
class Tenant(Entity):
    def can_accept_request(self) -> bool:  # pure logic, no I/O
        return self.is_active and self.tokens_used_this_month < self.token_quota
```

---

## Anti-Pattern 4: Mutable Value Objects 🔴

Value objects must be immutable. If you need to "change" a value object, create a new one.

```python
# ❌ WRONG — TenantId is mutable
class TenantId:
    def __init__(self, value: uuid.UUID):
        self.value = value  # mutable!

tenant_id = TenantId(uuid.uuid4())
tenant_id.value = uuid.uuid4()  # silently corrupts identity

# ✅ CORRECT — frozen=True enforces immutability
class TenantId(ValueObject):
    value: uuid.UUID = Field(default_factory=uuid.uuid4)

    model_config = ConfigDict(frozen=True)

tenant_id = TenantId()
tenant_id.value = uuid.uuid4()  # raises ValidationError
```

---

## Anti-Pattern 5: Direct Infrastructure Access in Tests 🔴

Unit tests must be able to run without any external services.

```python
# ❌ WRONG — test requires Redis, PostgreSQL, and OpenAI to run
async def test_ingest_document():
    pool = await asyncpg.create_pool(dsn="postgresql://localhost/test")
    redis = Redis()
    use_case = IngestDocumentUseCase(
        document_repository=PostgresDocumentRepository(pool),
        arq_pool=await create_pool(RedisSettings()),
    )
    result = await use_case.execute(request, tenant_id)
    # Fails if any dependency is unavailable

# ✅ CORRECT — pure unit test using mocks
async def test_ingest_document(document_repo, arq_pool):
    use_case = IngestDocumentUseCase(
        document_repository=document_repo,  # MagicMock
        arq_pool=arq_pool,                  # MagicMock
    )
    result = await use_case.execute(request, tenant_id)
    assert result.status == "processing"
    arq_pool.enqueue_job.assert_called_once()
```

---

## DDD Best Practices for This Codebase

### 1. Enforce Status Transitions in Entities

Every entity with a status field should have dedicated transition methods:

```python
class Document(Entity):
    status: DocumentStatus = DocumentStatus.PENDING

    def mark_processing(self) -> None:
        """Only callable from PENDING. Raises if called from wrong state."""
        if self.status != DocumentStatus.PENDING:
            raise InvalidStatusTransition(
                f"Cannot transition to PROCESSING from {self.status.value}"
            )
        self.status = DocumentStatus.PROCESSING
```

Never: `document.status = "processing"` — this bypasses the transition guard.

### 2. Use Typed Identifiers, Not Raw Strings

```python
# ❌ Raw string — no type safety, silently passes wrong ID
def get_document(document_id: str) -> Document: ...

get_document(tenant_id)   # compiles, fails at runtime

# ✅ Typed — compiler/linter catches wrong ID type
def get_document(document_id: DocumentId) -> Document: ...

get_document(tenant_id)   # type error — caught before runtime
```

### 3. Repository Returns Domain Entities

```python
# ❌ Repository leaks database records into the domain
class PostgresDocumentRepository:
    async def get_by_id(self, doc_id) -> asyncpg.Record:  # raw row!
        return await self._pool.fetchrow(...)

# ✅ Repository maps to domain entities before returning
class PostgresDocumentRepository:
    async def get_by_id(self, doc_id) -> Document | None:
        row = await self._pool.fetchrow(...)
        return self._row_to_document(row) if row else None  # mapped

    @staticmethod
    def _row_to_document(row: asyncpg.Record) -> Document:
        return Document(
            tenant_id=TenantId(value=row["tenant_id"]),
            document_id=DocumentId(value=row["document_id"]),
            # ...
        )
```

### 4. Exception Hierarchy

```
DomainException                # Base — all domain errors
├── DocumentNotFound
├── TenantQuotaExceeded
├── InvalidStatusTransition
└── ...

LLMException                  # External service errors
├── LLMRateLimitException
├── EmbeddingException
└── LLMConnectionException
```

The API middleware maps these to HTTP status codes:
```python
# api/middleware/error_handler.py
@app.exception_handler(TenantQuotaExceeded)
async def handle_quota_exceeded(req, exc):
    return JSONResponse(status_code=402, content={"error": str(exc)})

@app.exception_handler(LLMRateLimitException)
async def handle_rate_limit(req, exc):
    return JSONResponse(status_code=503, content={"error": "Service temporarily unavailable"})
```

---

## Testing Strategy

### Test Pyramid

```
                    /─────────────────────────────────────────────\
                   /              E2E Tests (5%)                    \
                  / Docker Compose, real OpenAI (smoke tests only)  \
                 /─────────────────────────────────────────────────\
                /         Integration Tests (20%)                   \
               / FastAPI TestClient + real PostgreSQL + real Redis   \
              / (requires docker-compose up for test infra)          \
             /─────────────────────────────────────────────────────\
            /              Unit Tests (75%)                          \
           / No network, no database, mocked infrastructure          \
          / Runs in < 1 second. Must pass in CI without any infra    \
         /────────────────────────────────────────────────────────────\
```

### What to Unit Test

| Layer | Unit Test Focus |
|-------|----------------|
| Domain entities | Status transitions, business rules, value object equality |
| Domain services | Chunking output, token counting, score filtering |
| Application use cases | Orchestration flow, repository calls, error propagation |
| Infrastructure | Data mapping (row → entity), cache hit/miss behavior |

### What to Integration Test

| Scenario | Test Type |
|---------|----------|
| Rate limiter with real Redis | Integration — Lua script behavior |
| PostgreSQL unique constraint behavior | Integration |
| Qdrant vector search with real data | Integration |
| Full ingest → search round-trip | Integration/E2E |

### Fixture Pattern

```python
# conftest.py — reusable test factories
def make_document(
    *,
    tenant_id: TenantId | None = None,
    status: DocumentStatus = DocumentStatus.PENDING,
) -> Document:
    """Always create valid documents with sensible defaults.
    
    This prevents tests from breaking when a new required field is added —
    you only update make_document(), not every test that uses Document.
    """
    return Document(
        tenant_id=tenant_id or TenantId(),
        document_id=DocumentId(),
        collection_id=CollectionId(),
        title="Test Document",
        content="Test content",
    )
```

### Testing Async Code

```python
# All async tests need @pytest.mark.asyncio (configured globally in pyproject.toml)
[tool.pytest.ini_options]
asyncio_mode = "auto"  # all async functions are treated as tests automatically

# Tests run:
async def test_document_status_transition():
    doc = make_document()
    doc.mark_processing()
    assert doc.status == DocumentStatus.PROCESSING
```

---

## Senior Insights

### 💡 The "Port-and-Adapter" Mental Model

This architecture is a variant of the Ports and Adapters (Hexagonal) pattern:

- **Port** = a domain interface (`DocumentRepository`, `EmbeddingProvider`) — what the domain **needs**
- **Adapter** = an infrastructure implementation (`PostgresDocumentRepository`, `OpenAIEmbeddingService`) — **how** it's provided

When you add a new external dependency, always ask: "What is the port?" Define the port in the domain first. Then write the adapter.

### 💡 Don't Let Pydantic Bleed Into Domain Logic

Pydantic is excellent for validation at the edges (API schemas, settings). But domain entities using Pydantic as their base means your domain logic is coupled to a validation library.

In this codebase, Pydantic is used for entities (via `BaseModel`) — this is a pragmatic choice, not a pure DDD decision. The trade-off: faster development, simpler code, at the cost of theoretical purity. If Pydantic's validation behavior changes or you need to run domain logic in a non-Pydantic context, you'd need refactoring.

### 💡 Configuration Injection vs. Hardcoding

```python
# ❌ Hardcoded in the use case
class ProcessDocumentUseCase:
    CHUNK_SIZE = 512  # if this changes, redeploy

# ✅ Injected via container → from settings
class ProcessDocumentUseCase:
    def __init__(self, ..., chunk_size: int, chunk_overlap: int):
        self._chunk_size = chunk_size  # can be tuned per environment

# In container:
process_document = providers.Factory(
    ProcessDocumentUseCase,
    chunk_size=settings.provided.chunking.chunk_size,
)
```

Externalize every tunable parameter. `chunk_size=512` that's hardcoded is `chunk_size=512` you'll forget exists when a new model with different context windows arrives.

### 💡 Fail Fast on Startup

```python
# settings.py
@model_validator(mode="after")
def check_production_api_key(self):
    if not self.debug and self.api_key == "change-me-in-production":
        raise ValueError(
            "API_KEY must be changed from the default in non-debug environments."
        )
    return self
```

This rejects a misconfigured deployment **at startup**, not at the first authenticated request. A deployment pipeline that starts the process should catch this immediately. Silent misconfigurations that only fail on user traffic are much more dangerous.

### 💡 Observability Before Optimization

Before profiling and tuning, make sure you can measure. Every significant operation should emit structured logs:

```python
await logger.ainfo(
    "qdrant_search",
    collection=self.collection_name,
    results_count=len(results),
    elapsed_seconds=round(elapsed, 3),
    has_tenant_filter=tenant_id is not None,
)
```

When you get a performance report saying "search is slow", you should be able to answer:
- Slow for which tenant?
- How many results were returned?
- What was the p99 latency over the last hour?

Without structured logs, you're guessing.
