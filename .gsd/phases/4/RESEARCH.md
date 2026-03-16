---
phase: 4
level: 2
researched_at: 2026-03-16
---

# Phase 4 Research: API Layer & Streaming

## Questions Investigated
1. How should SSE streaming be implemented with `sse-starlette` v2 in FastAPI?
2. Should middleware use `BaseHTTPMiddleware` or an alternative approach?
3. What are Pydantic v2 best practices for API request/response schemas?
4. How should domain exceptions map to HTTP status codes in FastAPI?

## Findings

### 1. SSE Streaming with sse-starlette v2

`sse-starlette` v2 provides `EventSourceResponse` which takes an async generator and streams events to the client.

**Key API surface:**
- `EventSourceResponse(content=async_generator, media_type="text/event-stream")` — main entry point
- Automatically sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`
- Sends keep-alive ping comments every 15 seconds (configurable)
- `ServerSentEvent(data=..., event=..., id=..., retry=...)` — for structured events
- `JSONServerSentEvent` — auto-serializes JSON data
- Yield dicts with `data` key for simple events, or yield `ServerSentEvent` objects

**Client disconnection handling:**
```python
async def event_generator():
    try:
        async for chunk in use_case.stream(dto):
            yield {"data": chunk.model_dump_json()}
    except asyncio.CancelledError:
        logger.info("Client disconnected")
        return
```

**Performance tip from official docs:** Declaring return type as `AsyncIterable[Item]` where `Item` is a Pydantic model enables Rust-side serialization for higher performance.

**Pitfalls:**
- Do NOT use with `GZipMiddleware` — causes buffering issues
- SSE works with any HTTP method including POST (our chat endpoint)
- Browser `EventSource` API only supports GET; POST requires `fetch()` with `ReadableStream`

**Sources:**
- [FastAPI SSE docs](https://fastapi.tiangolo.com/advanced/custom-response/#eventsourceresponse)
- [sse-starlette PyPI](https://pypi.org/project/sse-starlette/)
- [sse-starlette GitHub](https://github.com/sysid/sse-starlette)

**Recommendation:** Use `EventSourceResponse` with async generator yielding `model_dump_json()` strings. Handle `asyncio.CancelledError` in generator. Do NOT use `GZipMiddleware`.

---

### 2. Middleware Approach

`BaseHTTPMiddleware` has known issues:
- **Performance overhead** from internal task management routines
- **Body read issues** — reading request body in middleware prevents route handlers from reading it
- **No WebSocket support** (not relevant for us)
- Starlette community has discussed deprecating it

**Alternatives:**
1. **`@app.middleware("http")`** — simpler syntax, same underlying mechanism as `BaseHTTPMiddleware`
2. **Pure ASGI middleware** — best performance, more boilerplate
3. **FastAPI dependencies** — best for per-route concerns (auth, etc.)

**For our use case:**
- **Request logging**: `@app.middleware("http")` is sufficient — simple, doesn't read body
- **Rate limiting**: `@app.middleware("http")` works — only reads headers, no body access needed
- **Error handling**: Use `app.exception_handler(ExceptionClass)` decorators — this is the standard FastAPI pattern

**Sources:**
- [Starlette middleware docs](https://www.starlette.io/middleware/)
- [FastAPI middleware docs](https://fastapi.tiangolo.com/tutorial/middleware/)

**Recommendation:** Use `@app.middleware("http")` for logging and rate limiting (avoids `BaseHTTPMiddleware` class overhead). Use `app.exception_handler()` for error mapping. This is simpler and avoids known issues.

---

### 3. Pydantic v2 API Schema Patterns

**Best practices:**
- Use `ConfigDict` instead of `Config` inner class
- `json_schema_extra={"examples": [...]}` for OpenAPI 3.1 examples (list of examples)
- `Field(description="...")` on every field for auto-generated API docs
- Separate request models from response models (never reuse the same model)
- Use `response_model` parameter in router decorators for automatic validation and filtering
- `model_config = ConfigDict(json_schema_extra={"examples": [{"title": "My Doc", ...}]})`

**Example:**
```python
class IngestDocumentRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Getting Started Guide",
                    "content": "This is the full document content...",
                    "content_type": "text/plain",
                }
            ]
        }
    )
    title: str = Field(..., min_length=1, max_length=500, description="Document title")
    content: str = Field(..., min_length=1, description="Full document text content")
```

**Sources:**
- [Pydantic v2 Configuration](https://docs.pydantic.dev/latest/concepts/config/)
- [FastAPI Request Models](https://fastapi.tiangolo.com/tutorial/body/)

**Recommendation:** Use `ConfigDict(json_schema_extra={"examples": [...]})` for OpenAPI examples. `Field(description=...)` on all fields.

---

### 4. Domain Exception → HTTP Status Code Mapping

FastAPI supports registering exception handlers via `@app.exception_handler(ExceptionClass)` or `app.add_exception_handler(ExceptionClass, handler_fn)`.

**Mapping for our domain exceptions:**

| Domain Exception | HTTP Status | Rationale |
|---|---|---|
| `EntityNotFoundException` | 404 Not Found | Resource doesn't exist |
| `ValidationException` | 422 Unprocessable Entity | Domain validation failed |
| `BusinessRuleViolation` | 409 Conflict | Business constraint violated |
| `LLMRateLimitException` | 429 Too Many Requests | Upstream rate limit hit |
| `LLMConnectionException` | 502 Bad Gateway | Upstream service unavailable |
| `TokenLimitExceededException` | 413 Content Too Large | Request too large for model |
| `DomainException` (catch-all) | 400 Bad Request | Generic domain error |
| `RequestValidationError` | 422 Unprocessable Entity | Pydantic validation failed |
| `Exception` (catch-all) | 500 Internal Server Error | Unexpected error |

**Pattern:**
```python
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found(request, exc):
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
        )
```

**Sources:**
- [FastAPI Exception Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)

**Recommendation:** Use `register_exception_handlers(app)` function pattern. Map each domain exception to specific HTTP status. Always return `ErrorResponse` schema. Log all exceptions.

---

## Decisions Made

| Decision | Choice | Rationale |
|---|---|---|
| SSE library | `sse-starlette` v2 (already in deps) | Production-ready, FastAPI-native |
| SSE event format | Yield `model_dump_json()` strings | Simple, avoids double serialization |
| Middleware pattern | `@app.middleware("http")` functions | Avoids `BaseHTTPMiddleware` performance issues |
| Error handling | `register_exception_handlers()` function | Clean separation, testable |
| Schema pattern | Separate API schemas from application DTOs | Clean Architecture boundary |
| OpenAPI examples | `ConfigDict(json_schema_extra={"examples": [...]})` | Pydantic v2 standard |
| Streaming toggle | `stream: bool` field in chat request body | Client controls response format |

## Patterns to Follow
- Thin routers: schema mapping only, no business logic
- Dependency injection via `request.app.state.container` accessor functions
- `Annotated[Type, Depends(fn)]` type aliases for clean router signatures
- `RequireAPIKey` dependency on all non-health endpoints
- Structured logging with `request_id` context per request
- Rate limit headers on responses (`X-RateLimit-Remaining`, `X-RateLimit-Limit`)

## Anti-Patterns to Avoid
- `BaseHTTPMiddleware` class — performance overhead, body-read issues
- `GZipMiddleware` with SSE — causes buffering and breaks streaming
- Business logic in routers — belongs in use cases
- Catching exceptions in routers — let exception handlers deal with them
- Reusing application DTOs as API schemas — breaks Clean Architecture boundary
- Module-level `@inject` decorators — use explicit container access via `request.app.state`

## Dependencies Identified

| Package | Version | Purpose |
|---|---|---|
| `sse-starlette` | ^2.2 | SSE streaming (already in deps) |
| `fastapi` | ^0.115 | API framework (already in deps) |
| `pydantic` | ^2.10 | Request/response validation (already in deps) |
| `structlog` | ^25.1 | Structured logging (already in deps) |

No new dependencies needed.

## Risks
- **SSE with POST**: Browser `EventSource` API only supports GET. Clients using POST must use `fetch()` with `ReadableStream`. Document this in API docs.
- **Rate limiter requires Redis**: If Redis is down, rate limiter may fail. Consider graceful degradation (allow request if Redis unavailable).
- **Middleware execution order**: Starlette adds middleware in reverse order. Must add in correct sequence.

## Ready for Planning
- [x] Questions answered
- [x] Approach selected
- [x] Dependencies identified (none new needed)
