---
phase: 1
level: 2
researched_at: 2026-03-15
---

# Phase 1 Research — Project Foundation & Domain Layer

## Questions Investigated

1. How to integrate `dependency-injector` with FastAPI's async patterns?
2. What is the optimal project structure for Clean Architecture + DDD in Python 3.12+?
3. How to configure `pydantic-settings` v2 with nested settings and `.env` support?
4. How to set up Poetry + ruff + mypy strict in `pyproject.toml`?
5. What are the best patterns for Python domain value objects?

## Findings

### 1. dependency-injector + FastAPI Async

**Version**: `dependency-injector` v4.48.3 (latest, Dec 2025)

The library fully supports async patterns with FastAPI:

- **Async Resource Providers**: Use `providers.Resource(init_async_resource)` for async initialization (DB connections, HTTP clients)
- **Wiring**: The `@inject` decorator works seamlessly with `async def` FastAPI endpoints
- **Container Pattern**: Define a `Container(containers.DeclarativeContainer)` with all providers, then call `container.wire(modules=[...])` to inject into FastAPI router modules
- **Lifespan Integration**: Initialize/shutdown resources in FastAPI's lifespan context manager via `await container.init_resources()` / `await container.shutdown_resources()`

**Recommended Pattern:**
```python
class Container(containers.DeclarativeContainer):
    config = providers.Configuration()
    
    # Singletons for long-lived services
    redis_client = providers.Singleton(RedisClient, url=config.redis.url)
    
    # Factories for per-request services
    embedding_service = providers.Factory(EmbeddingService, client=openai_client)
    
    # Use cases wired with dependencies
    ingest_use_case = providers.Factory(
        IngestDocumentUseCase,
        doc_repo=document_repository,
        embedding_service=embedding_service
    )
```

**Sources:**
- https://python-dependency-injector.ets-labs.org/examples/fastapi.html
- https://pypi.org/project/dependency-injector/

**Recommendation:** Use `dependency-injector` with `DeclarativeContainer`, `Singleton` providers for infrastructure clients, and `Factory` providers for use cases. Wire to FastAPI router modules.

---

### 2. Clean Architecture Project Structure

Research confirms the following best practices for Python 3.12+ projects:

**src-layout** is recommended in 2025 to prevent silent imports during testing:

```
app/                          # Application root package
├── api/                      # Presentation layer (FastAPI)
│   ├── routers/              # Route handlers (thin)
│   ├── dependencies/         # FastAPI Depends functions
│   ├── middleware/            # Request/response middleware
│   └── schemas/              # Request/Response Pydantic models
├── application/              # Application layer
│   ├── services/             # Application services
│   ├── use_cases/            # Use case implementations
│   └── dto/                  # Data Transfer Objects
├── domain/                   # Domain layer (pure, no framework deps)
│   ├── entities/             # Domain entities
│   ├── value_objects/        # Immutable value objects
│   ├── repositories/         # Abstract repository interfaces
│   ├── services/             # Domain services
│   └── exceptions/           # Domain-specific exceptions
├── infrastructure/           # Infrastructure implementations
│   ├── llm/                  # LLM provider implementations
│   ├── vector_db/            # Vector DB implementations
│   ├── cache/                # Cache implementations
│   └── queue/                # Background worker implementations
├── repositories/             # Concrete repository implementations
│   └── implementations/
├── core/                     # Cross-cutting concerns
│   ├── config/               # Settings and configuration
│   ├── logging/              # Structured logging
│   └── security/             # Authentication, authorization
└── container.py              # DI container definition
```

**Key principles:**
- Domain layer has ZERO framework dependencies (no FastAPI, no SQLAlchemy imports)
- Use cases orchestrate domain objects + infrastructure through interfaces
- FastAPI routers are thin — delegate to use cases immediately
- Repository interfaces live in domain, implementations in infrastructure

**Recommendation:** Use the `app/` layout (not src/) since this is a single-service project. Keep the domain layer framework-agnostic.

---

### 3. pydantic-settings v2 Configuration

**Best practices for nested settings:**

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class RedisSettings(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0

class OpenAISettings(BaseModel):
    api_key: SecretStr
    model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    max_retries: int = 3

class QdrantSettings(BaseModel):
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "documents"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        case_sensitive=False,
    )
    
    app_name: str = "AI Backend API"
    debug: bool = False
    
    redis: RedisSettings = RedisSettings()
    openai: OpenAISettings  # Required — no default
    qdrant: QdrantSettings = QdrantSettings()
```

**Key patterns:**
- Sub-models inherit from `BaseModel` (NOT `BaseSettings`)
- Use `env_nested_delimiter="__"` for `REDIS__HOST=localhost`
- Use `SecretStr` for API keys (prevents logging exposure)
- Required fields (no default) = startup validation
- Use `@lru_cache` to create singleton settings instance

**Recommendation:** Implement nested settings with `__` delimiter. Use `SecretStr` for all secrets. Validate at startup.

---

### 4. Poetry + Ruff + Mypy Configuration

**Poetry init:**
```bash
poetry init --name ai-backend-api --python "^3.12"
```

**pyproject.toml configuration:**

```toml
[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "S",    # flake8-bandit
    "A",    # flake8-builtins
    "C4",   # flake8-comprehensions
    "DTZ",  # flake8-datetimez
    "T20",  # flake8-print
    "RET",  # flake8-return
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "ARG",  # flake8-unused-arguments
    "PTH",  # flake8-use-pathlib
    "RUF",  # Ruff-specific rules
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # Allow assert in tests

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
plugins = ["pydantic.mypy"]

[tool.mypy.pydantic-mypy]
init_forbid_extra = true
init_typed = true
warn_required_dynamic_aliases = true
```

**Recommendation:** Use the comprehensive ruff rule set above. Enable mypy strict with pydantic plugin. Configure all tools in `pyproject.toml`.

---

### 5. Domain Value Objects

**Pattern:** Frozen Pydantic models with validation

```python
from pydantic import BaseModel, ConfigDict, Field
import uuid

class DocumentId(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: uuid.UUID = Field(default_factory=uuid.uuid4)

class EmbeddingVector(BaseModel):
    model_config = ConfigDict(frozen=True)
    values: tuple[float, ...]
    model: str
    dimensions: int
```

**Key decisions:**
- Use `ConfigDict(frozen=True)` for immutability
- Use `tuple` over `list` for immutable sequences in value objects
- Factory defaults for IDs (`uuid.uuid4`)
- Hashable by default when frozen (can be used as dict keys/set members)

**Recommendation:** Create a `ValueObject` base class with `ConfigDict(frozen=True)` that all value objects inherit from.

---

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Package manager | Poetry | User preference, mature ecosystem |
| Linter/Formatter | Ruff | All-in-one, fast, configurable in pyproject.toml |
| Type checker | Mypy strict | Catches bugs early, pydantic plugin available |
| DI framework | dependency-injector v4.48.3 | Full-featured, async support, FastAPI integration |
| Settings | pydantic-settings v2 + nested models | Type-safe, .env support, validation at startup |
| Value objects | Frozen Pydantic BaseModel | Immutable, validated, hashable |
| Project layout | `app/` package (not src/) | Single service, simpler imports |
| Repository interfaces | ABC in domain layer | Framework-agnostic, testable |

## Patterns to Follow

- **Thin routers**: FastAPI handlers should only validate input and delegate to use cases
- **Use case pattern**: One class per use case with a single `execute()` method
- **Repository pattern**: Abstract interface in domain, concrete in infrastructure
- **Factory providers**: Use `providers.Factory` for per-request services
- **Singleton providers**: Use `providers.Singleton` for shared infrastructure clients
- **Nested settings**: Group related config into sub-models with `BaseModel`
- **Domain exceptions**: Custom exception hierarchy for domain-specific errors

## Anti-Patterns to Avoid

- **Fat routers**: Don't put business logic in FastAPI route handlers
- **Leaky abstractions**: Domain layer must NOT import from infrastructure
- **God container**: Split container into sub-containers if it grows too large
- **Over-engineering**: Keep DDD pragmatic — this is a RAG platform, not a complex business domain
- **Mutable value objects**: Always use `frozen=True` on value objects
- **Direct env access**: Never use `os.environ` directly — always go through Settings

## Dependencies Identified

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | ^0.115 | Web framework |
| uvicorn | ^0.34 | ASGI server |
| pydantic | ^2.10 | Data validation |
| pydantic-settings | ^2.7 | Settings management |
| dependency-injector | ^4.48 | Dependency injection |
| openai | ^1.60 | OpenAI API client |
| qdrant-client | ^1.13 | Qdrant vector DB client |
| redis | ^5.2 | Redis async client |
| sse-starlette | ^2.2 | Server-Sent Events |
| tiktoken | ^0.9 | Token counting |
| httpx | ^0.28 | Async HTTP client |
| structlog | ^25.1 | Structured logging |
| ruff | ^0.9 | Linting + formatting (dev) |
| mypy | ^1.14 | Type checking (dev) |
| pytest | ^8.3 | Testing (dev) |
| pytest-asyncio | ^0.25 | Async test support (dev) |

## Risks

- **dependency-injector + mypy strict**: The library's type stubs may not be perfect — may need `# type: ignore` annotations in some places. **Mitigation**: Pin to stable version, add targeted ignores.
- **Pydantic v2 performance**: Frozen models have slight overhead vs dataclasses. **Mitigation**: Only use for value objects (not hot-path data structures).
- **Domain purity**: Risk of infrastructure concerns leaking into domain models over time. **Mitigation**: Enforce via code review and linting rules.

## Ready for Planning

- [x] Questions answered
- [x] Approach selected
- [x] Dependencies identified
- [x] Patterns documented
- [x] Anti-patterns documented
- [x] Risks assessed
