---
phase: 4
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/api/schemas/common.py
  - app/api/schemas/document.py
  - app/api/schemas/search.py
  - app/api/schemas/chat.py
  - app/api/schemas/__init__.py
autonomous: true

must_haves:
  truths:
    - "API schemas are separate from application DTOs — they define the HTTP contract"
    - "ErrorResponse schema is shared across all error handlers"
    - "All schemas use Pydantic v2 with Field descriptions for OpenAPI docs"
---

# Plan 4.1: API Schemas & Error Response Model

## Objective
Create Pydantic v2 request/response schemas that define the HTTP API contract. These are intentionally separate from the application DTOs — API schemas handle serialization, validation constraints, and OpenAPI documentation, while DTOs handle internal data transfer. Also create the shared error response model.

## Context
- @app/application/dto/document.py — IngestDocumentRequest, IngestDocumentResponse
- @app/application/dto/search.py — SearchRequest, SearchResponse, SearchResultDTO
- @app/application/dto/chat.py — ChatRequest, ChatResponseDTO, StreamChunk, SourceDTO
- @app/domain/exceptions/base.py — DomainException hierarchy (code + message)

## Tasks

<task type="auto">
  <name>Create shared error response and common schemas</name>
  <files>
    app/api/schemas/common.py
  </files>
  <action>
    Create shared API schemas:

    **ErrorResponse:**
    - `detail: str` — Human-readable error message
    - `code: str` — Machine-readable error code (e.g., "ENTITY_NOT_FOUND")
    - `field: str | None = None` — Optional field name for validation errors

    **PaginatedMeta (optional for future use):**
    - `total: int`
    - `page: int = 1`
    - `per_page: int = 20`

    Use `Field(...)` with `description=` for all fields to auto-generate OpenAPI docs.
    Use `model_config = ConfigDict(json_schema_extra={"example": {...}})` for example values.
  </action>
  <verify>python -m poetry run python -c "from app.api.schemas.common import ErrorResponse; e = ErrorResponse(detail='test', code='TEST'); print(e.model_dump())"</verify>
  <done>ErrorResponse schema importable and serializable</done>
</task>

<task type="auto">
  <name>Create document, search, and chat API schemas</name>
  <files>
    app/api/schemas/document.py
    app/api/schemas/search.py
    app/api/schemas/chat.py
    app/api/schemas/__init__.py
  </files>
  <action>
    Create API-specific request/response schemas that mirror (but are separate from) application DTOs:

    **document.py:**
    - `IngestDocumentRequest(title, content, collection_id?, content_type?, metadata?)` — add `examples` in ConfigDict
    - `IngestDocumentResponse(document_id, job_id, status)` — read-only output
    - Map to/from `app.application.dto.document` in the router, NOT in the schema

    **search.py:**
    - `SearchRequest(query, collection_id?, top_k?, filters?)` — validate top_k 1-100
    - `SearchResultResponse(chunk_id, document_id, content, score, metadata, document_title, chunk_index)`
    - `SearchResponse(results, total, query_tokens)`

    **chat.py:**
    - `ChatRequest(message, conversation_id?, user_id?, top_k?, stream?)` — `stream: bool = False` controls SSE vs JSON
    - `SourceResponse(index, chunk_id, document_id, document_title, content, score)`
    - `ChatResponse(message, sources, prompt_tokens, completion_tokens, total_tokens)`
    - `StreamEvent(content, done, sources?, prompt_tokens?, completion_tokens?, total_tokens?)` — for SSE chunks

    **__init__.py:** Re-export all schemas for clean imports.

    All schemas must have `description=` on every `Field()` for auto-generated OpenAPI docs.
    Add `model_config = ConfigDict(json_schema_extra={"example": {...}})` with realistic examples.
  </action>
  <verify>python -m poetry run python -c "from app.api.schemas.document import IngestDocumentRequest; from app.api.schemas.search import SearchRequest; from app.api.schemas.chat import ChatRequest; print('All API schemas OK')"</verify>
  <done>All API schemas importable with correct fields and OpenAPI examples</done>
</task>

## Success Criteria
- [ ] ErrorResponse schema exists with detail, code, optional field
- [ ] Document, Search, Chat API schemas exist with full Field descriptions
- [ ] All schemas have json_schema_extra examples for OpenAPI
- [ ] Schemas are separate from application DTOs
