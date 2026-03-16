---
phase: 4
plan: 3
wave: 2
depends_on: [1, 2]
files_modified:
  - app/api/routers/documents.py
  - app/api/routers/search.py
  - app/api/routers/__init__.py
autonomous: true

must_haves:
  truths:
    - "Routers use API schemas for request/response, map to/from application DTOs"
    - "All endpoints require API key authentication via RequireAPIKey"
    - "Routers are thin — delegate all logic to use cases"
---

# Plan 4.3: Document & Search Routers

## Objective
Implement the `POST /documents` (ingestion) and `POST /search` (semantic search) routers. These are standard request→response endpoints that delegate to the application use cases.

## Context
- @app/api/schemas/document.py — API schemas (from Plan 4.1)
- @app/api/schemas/search.py — API schemas (from Plan 4.1)
- @app/api/dependencies/container.py — get_ingest_use_case, get_search_use_case (from Plan 4.2)
- @app/core/security/api_key.py — RequireAPIKey dependency
- @app/application/use_cases/ingest_document.py — IngestDocumentUseCase.execute(IngestDocumentRequest)
- @app/application/use_cases/search_documents.py — SearchDocumentsUseCase.execute(SearchRequest)
- @app/application/dto/document.py — IngestDocumentRequest DTO, IngestDocumentResponse DTO
- @app/application/dto/search.py — SearchRequest DTO, SearchResponse DTO

## Tasks

<task type="auto">
  <name>Create document ingestion router</name>
  <files>
    app/api/routers/documents.py
  </files>
  <action>
    Create the document ingestion router:

    ```python
    router = APIRouter(prefix="/documents", tags=["documents"])

    @router.post(
        "",
        response_model=DocumentIngestResponse,
        status_code=status.HTTP_202_ACCEPTED,
        summary="Ingest a document",
        description="Upload a document for ingestion into the RAG pipeline. Processing happens asynchronously.",
        responses={
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def ingest_document(
        body: DocumentIngestRequest,
        api_key: RequireAPIKey,
        use_case: IngestUseCaseDep,
    ) -> DocumentIngestResponse:
    ```

    Implementation:
    1. Map API schema → application DTO: `IngestDocumentRequest(title=body.title, content=body.content, ...)`
    2. Call `use_case.execute(dto)`
    3. Map application DTO → API schema: `DocumentIngestResponse(document_id=result.document_id, ...)`
    4. Return with 202 Accepted (processing is async)

    The router MUST be thin — no business logic, just mapping.
    Do NOT catch exceptions here — let the error handler middleware deal with them.
  </action>
  <verify>python -m poetry run python -c "from app.api.routers.documents import router; print(f'Routes: {[r.path for r in router.routes]}')"</verify>
  <done>POST /documents endpoint exists, maps schemas to use case, returns 202</done>
</task>

<task type="auto">
  <name>Create search router</name>
  <files>
    app/api/routers/search.py
    app/api/routers/__init__.py
  </files>
  <action>
    Create the semantic search router:

    ```python
    router = APIRouter(prefix="/search", tags=["search"])

    @router.post(
        "",
        response_model=SearchApiResponse,
        summary="Semantic document search",
        description="Search documents using semantic similarity. Returns ranked results with relevance scores.",
        responses={
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def search_documents(
        body: SearchApiRequest,
        api_key: RequireAPIKey,
        use_case: SearchUseCaseDep,
    ) -> SearchApiResponse:
    ```

    Implementation:
    1. Map API schema → application DTO: `SearchRequest(query=body.query, top_k=body.top_k, ...)`
    2. Call `use_case.execute(dto)`
    3. Map results → API response schemas
    4. Return 200

    **__init__.py:** Create a function `register_routers(app: FastAPI)` that includes all routers:
    ```python
    def register_routers(app: FastAPI) -> None:
        app.include_router(documents_router)
        app.include_router(search_router)
        app.include_router(chat_router)  # from Plan 4.4
    ```
    Initially just documents and search. Chat will be added in Plan 4.4.
  </action>
  <verify>python -m poetry run python -c "from app.api.routers.search import router; print(f'Routes: {[r.path for r in router.routes]}')"</verify>
  <done>POST /search endpoint exists, maps schemas to use case, returns 200</done>
</task>

## Success Criteria
- [ ] POST /documents returns 202 Accepted with document_id and job_id
- [ ] POST /search returns ranked results with scores and metadata
- [ ] Both endpoints require X-API-Key authentication
- [ ] Routers are thin — only schema↔DTO mapping, no business logic
