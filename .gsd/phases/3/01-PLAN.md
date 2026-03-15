---
phase: 3
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/application/dto/document.py
  - app/application/dto/search.py
  - app/application/dto/chat.py
  - app/application/services/prompt_service.py
  - app/application/services/context_service.py
autonomous: true

must_haves:
  truths:
    - "DTOs exist for document ingestion, search, and chat request/response"
    - "PromptService builds system prompts with RAG context"
    - "ContextService manages context window token budgets"
---

# Plan 3.1: DTOs + Prompt & Context Services

## Objective
Create the Data Transfer Objects that bridge API input/output to use cases, and implement the prompt template and context window services that the RAG chat pipeline needs.

## Context
- @app/domain/entities/document.py — Document entity
- @app/domain/entities/chat.py — ChatMessage, ChatResponse, TokenUsage
- @app/domain/entities/search_result.py — SearchResult
- @app/domain/entities/ingestion_job.py — IngestionJob, IngestionStatus
- @app/core/config/settings.py — OpenAISettings (max_tokens)

## Tasks

<task type="auto">
  <name>Create application DTOs</name>
  <files>
    app/application/dto/document.py
    app/application/dto/search.py
    app/application/dto/chat.py
  </files>
  <action>
    Create Pydantic models for use case input/output:
    
    **document.py:**
    - `IngestDocumentRequest(title, content, collection_id?, metadata?)`
    - `IngestDocumentResponse(document_id, job_id, status)`
    - `DocumentResponse(document_id, title, status, chunk_count, ...)`
    
    **search.py:**
    - `SearchRequest(query, collection_id?, top_k=10, filters?)`
    - `SearchResponse(results: list[SearchResultDTO], total, query_tokens)`
    - `SearchResultDTO(chunk_id, document_id, content, score, metadata, document_title)`
    
    **chat.py:**
    - `ChatRequest(message, conversation_id?, user_id?, top_k=5)`
    - `ChatResponse(message, sources, token_usage)`
    - `StreamChunk(content, done, sources?, token_usage?)`
    
    All DTOs should be plain Pydantic BaseModel (not frozen). They map between API schemas and domain objects.
  </action>
  <verify>python -m poetry run python -c "from app.application.dto.document import IngestDocumentRequest, IngestDocumentResponse; from app.application.dto.search import SearchRequest, SearchResponse; from app.application.dto.chat import ChatRequest; print('DTOs OK')"</verify>
  <done>All DTOs importable with correct fields</done>
</task>

<task type="auto">
  <name>Implement PromptService and ContextService</name>
  <files>
    app/application/services/prompt_service.py
    app/application/services/context_service.py
  </files>
  <action>
    **PromptService:**
    - `build_system_prompt() -> str`: Returns the RAG system prompt template
    - `build_rag_prompt(query, context_chunks) -> list[ChatMessage]`: Builds full message list with system prompt, context injection, and user query
    - The system prompt should instruct the LLM to:
      - Answer based on provided context
      - Cite sources using [1], [2], etc.
      - Say "I don't know" if context doesn't contain the answer
    
    **ContextService:**
    - `__init__(token_service, max_context_tokens)`: Takes token service and token budget
    - `build_context(search_results, model) -> tuple[str, list[SearchResult]]`: 
      - Iterate results in score order
      - Add content until token budget exhausted
      - Return formatted context string and used results
    - `format_context_block(results) -> str`: Format results as numbered context blocks
    
    Keep prompts simple and effective. Don't over-engineer templates.
  </action>
  <verify>python -m poetry run python -c "from app.application.services.prompt_service import PromptService; from app.application.services.context_service import ContextService; print('Services OK')"</verify>
  <done>PromptService builds RAG prompts, ContextService manages token budgets</done>
</task>

## Success Criteria
- [ ] DTOs exist for ingestion, search, and chat
- [ ] PromptService creates RAG-specific prompts with context injection
- [ ] ContextService fits search results within token budget
