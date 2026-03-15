---
phase: 3
plan: 5
wave: 3
depends_on: ["3.1", "3.4"]
files_modified:
  - app/application/use_cases/rag_chat.py
autonomous: true

must_haves:
  truths:
    - "RAGChatUseCase performs search, builds context, and streams LLM response"
    - "Supports both streaming and non-streaming responses"
    - "Includes source citations in response"
    - "Tracks token usage across the pipeline"
---

# Plan 3.5: RAG Chat Use Case

## Objective
Implement the complete RAG pipeline as a use case — search for relevant context, build a prompt with citations, and stream the LLM response. This is the crown jewel of the system.

## Context
- @app/application/use_cases/search_documents.py — SearchDocumentsUseCase
- @app/application/services/prompt_service.py — PromptService
- @app/application/services/context_service.py — ContextService
- @app/infrastructure/llm/base.py — ChatProvider (stream + complete)
- @app/domain/repositories/chat_repository.py — ChatHistoryRepository
- @app/application/dto/chat.py — ChatRequest, ChatResponse, StreamChunk

## Tasks

<task type="auto">
  <name>Implement RAGChatUseCase</name>
  <files>app/application/use_cases/rag_chat.py</files>
  <action>
    Create `RAGChatUseCase`:
    
    Constructor (injected):
    - `search_use_case` (SearchDocumentsUseCase)
    - `chat_provider` (ChatProvider)
    - `prompt_service` (PromptService)
    - `context_service` (ContextService)
    - `chat_history_repository` (ChatHistoryRepository)
    - `token_service` (TokenService)
    
    Method `async execute(request: ChatRequest) -> ChatResponse`:
    (Non-streaming full response)
    1. Search for relevant context: `search_use_case.execute(SearchRequest(query=request.message, top_k=request.top_k))`
    2. Build context from results: `context_service.build_context(results, model)`
    3. Build prompt: `prompt_service.build_rag_prompt(request.message, context, used_results)`
    4. Optionally prepend chat history for conversation continuity
    5. Call `chat_provider.complete(messages)` for full response
    6. Save user message and assistant message to chat history
    7. Build sources list from used search results
    8. Return ChatResponse with message, sources, token_usage
    
    Method `async stream(request: ChatRequest) -> AsyncGenerator[StreamChunk, None]`:
    (Streaming response)
    1-4. Same search/context/prompt as execute()
    5. Call `chat_provider.stream(messages)` and yield `StreamChunk(content=delta)`
    6. On final chunk: yield `StreamChunk(content="", done=True, sources=..., token_usage=...)`
    7. Save messages to history after streaming completes
    
    Log: query, context token count, result count, latency via structlog.
  </action>
  <verify>python -m poetry run python -c "from app.application.use_cases.rag_chat import RAGChatUseCase; print('OK')"</verify>
  <done>RAGChatUseCase with execute() and stream() methods</done>
</task>

## Success Criteria
- [ ] RAG pipeline: search → context → prompt → LLM → response
- [ ] Streaming yields content deltas with final sources/usage
- [ ] Chat history is saved for conversation continuity
- [ ] Source citations reference the search results used
