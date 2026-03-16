---
phase: 4
plan: 2
wave: 1
depends_on: [1]
files_modified:
  - app/api/dependencies/container.py
  - app/api/dependencies/__init__.py
  - app/api/middleware/request_logging.py
  - app/api/middleware/rate_limit.py
  - app/api/middleware/error_handler.py
  - app/api/middleware/__init__.py
autonomous: true

must_haves:
  truths:
    - "Dependencies extract use cases from the DI container via app.state.container"
    - "Request logging middleware binds structlog context per request"
    - "Rate limit middleware uses the existing RedisRateLimiter"
    - "Error handler maps domain exceptions to HTTP status codes"
---

# Plan 4.2: FastAPI Dependencies & Middleware

## Objective
Create the FastAPI dependency injection functions that bridge the DI container to route handlers, and implement middleware for request logging, rate limiting, and domain exception → HTTP error mapping.

## Context
- @app/container.py — Container with all providers (ingest_document, search_documents, rag_chat, rate_limiter)
- @app/core/security/api_key.py — RequireAPIKey dependency (already exists)
- @app/core/logging/context.py — RequestContext, bind_request_context, clear_request_context
- @app/infrastructure/cache/rate_limiter.py — RedisRateLimiter with is_allowed(), get_remaining()
- @app/domain/exceptions/base.py — DomainException, EntityNotFoundException, ValidationException
- @app/domain/exceptions/llm.py — LLMRateLimitException, LLMConnectionException
- @app/api/schemas/common.py — ErrorResponse (from Plan 4.1)

## Tasks

<task type="auto">
  <name>Create container dependency functions</name>
  <files>
    app/api/dependencies/container.py
    app/api/dependencies/__init__.py
  </files>
  <action>
    Create FastAPI dependency functions that extract use cases from the container:

    ```python
    from fastapi import Request

    def get_container(request: Request) -> Container:
        return request.app.state.container

    def get_ingest_use_case(request: Request) -> IngestDocumentUseCase:
        return request.app.state.container.ingest_document()

    def get_search_use_case(request: Request) -> SearchDocumentsUseCase:
        return request.app.state.container.search_documents()

    def get_rag_chat_use_case(request: Request) -> RAGChatUseCase:
        return request.app.state.container.rag_chat()

    def get_rate_limiter(request: Request) -> RedisRateLimiter:
        return request.app.state.container.rate_limiter()
    ```

    Use `Annotated[..., Depends(...)]` type aliases for clean router signatures.

    **__init__.py:** Re-export all dependency functions and type aliases.
  </action>
  <verify>python -m poetry run python -c "from app.api.dependencies.container import get_ingest_use_case, get_search_use_case, get_rag_chat_use_case; print('Dependencies OK')"</verify>
  <done>All dependency functions importable and return correct types</done>
</task>

<task type="auto">
  <name>Create middleware stack</name>
  <files>
    app/api/middleware/request_logging.py
    app/api/middleware/rate_limit.py
    app/api/middleware/error_handler.py
    app/api/middleware/__init__.py
  </files>
  <action>
    **RESEARCH FINDING:** Do NOT use `BaseHTTPMiddleware` — it has known performance overhead
    and body-read issues (see RESEARCH.md §2). Use standalone middleware functions registered
    via `add_middleware_function()` helper or applied directly in `create_app()`.

    **request_logging.py — create_request_logging_middleware(app):**
    - Register via `@app.middleware("http")` or return a middleware function
    - On each request:
      1. Generate `request_id` (uuid4)
      2. Create `RequestContext(request_id, method, path, client_ip)`
      3. Call `bind_request_context(context)`
      4. Log request start with method, path, request_id
      5. Call `response = await call_next(request)`
      6. Log request end with status_code, duration_ms
      7. Add `X-Request-ID` header to response
      8. Call `clear_request_context()`
    - Skip logging for `/health` endpoint

    **rate_limit.py — create_rate_limit_middleware(rate_limiter):**
    - Return a middleware function (closure over rate_limiter instance)
    - The returned function is registered via `app.middleware("http")` in create_app()
    - On each request:
      1. Extract API key from `X-API-Key` header (or use client IP as fallback)
      2. Call `rate_limiter.is_allowed(key)`
      3. If not allowed: return 429 JSON with `ErrorResponse(detail="Rate limit exceeded", code="RATE_LIMIT_EXCEEDED")`
      4. Add rate limit headers: `X-RateLimit-Remaining`, `X-RateLimit-Limit`
    - Skip rate limiting for `/health` endpoint

    **error_handler.py — register_exception_handlers(app):**
    - Function that registers exception handlers on the FastAPI app via `@app.exception_handler()`
    - Map domain exceptions to HTTP status codes:
      - `EntityNotFoundException` → 404
      - `ValidationException` → 422
      - `BusinessRuleViolation` → 409
      - `LLMRateLimitException` → 429
      - `LLMConnectionException` → 502
      - `TokenLimitExceededException` → 413
      - `DomainException` (catch-all) → 400
      - `RequestValidationError` (Pydantic) → 422
      - `Exception` (catch-all) → 500
    - All responses use `ErrorResponse` schema
    - Log all exceptions with structlog

    **__init__.py:** Re-export middleware factory functions and register function.
  </action>
  <verify>python -m poetry run python -c "from app.api.middleware.request_logging import create_request_logging_middleware; from app.api.middleware.rate_limit import create_rate_limit_middleware; from app.api.middleware.error_handler import register_exception_handlers; print('Middleware OK')"</verify>
  <done>All middleware importable and properly structured</done>
</task>

## Success Criteria
- [ ] Container dependency functions extract use cases from app.state.container
- [ ] Request logging middleware binds structlog context and adds X-Request-ID
- [ ] Rate limit middleware uses RedisRateLimiter and returns 429
- [ ] Exception handlers map all domain exceptions to correct HTTP status codes
- [ ] No use of BaseHTTPMiddleware (per research findings)
