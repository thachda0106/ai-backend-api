---
phase: 3
plan: 4
wave: 2
depends_on: ["3.1"]
files_modified:
  - app/application/use_cases/search_documents.py
autonomous: true

must_haves:
  truths:
    - "SearchDocumentsUseCase embeds query and searches Qdrant"
    - "Returns ranked SearchResponse with results and token counts"
    - "Supports optional collection_id filtering"
---

# Plan 3.4: Vector Search Use Case

## Objective
Implement the semantic search use case — embed the user query, search Qdrant, and return ranked results with metadata. This is used standalone and as a sub-step in the RAG chat pipeline.

## Context
- @app/infrastructure/llm/base.py — EmbeddingProvider ABC
- @app/infrastructure/vector_db/qdrant_adapter.py — QdrantVectorRepository
- @app/infrastructure/token/tiktoken_service.py — TiktokenService
- @app/application/dto/search.py — SearchRequest, SearchResponse, SearchResultDTO

## Tasks

<task type="auto">
  <name>Implement SearchDocumentsUseCase</name>
  <files>app/application/use_cases/search_documents.py</files>
  <action>
    Create `SearchDocumentsUseCase`:
    
    Constructor (injected):
    - `embedding_provider` (EmbeddingProvider)
    - `vector_repository` (VectorRepository)
    - `token_service` (TokenService)
    
    Method `async execute(request: SearchRequest) -> SearchResponse`:
    1. Count tokens in query for tracking
    2. Generate embedding for query text: `embedding_provider.embed(query)`
    3. Build filters dict from request (e.g., `{"collection_id": str(collection_id)}`)
    4. Search vectors: `vector_repository.search(embedding, top_k, filters)`
    5. Map domain `SearchResult` to `SearchResultDTO`
    6. Return `SearchResponse(results, total, query_tokens)`
    
    Log: query length, token count, result count, latency via structlog.
  </action>
  <verify>python -m poetry run python -c "from app.application.use_cases.search_documents import SearchDocumentsUseCase; print('OK')"</verify>
  <done>SearchDocumentsUseCase importable with execute() method</done>
</task>

## Success Criteria
- [ ] Query is embedded and used for vector search
- [ ] Results are mapped from domain to DTO format
- [ ] Token count for the query is tracked
- [ ] Collection filtering works when provided
