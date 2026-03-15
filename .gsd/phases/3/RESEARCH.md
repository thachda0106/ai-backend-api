---
phase: 3
level: 2
researched_at: 2026-03-15
---

# Phase 3 Research — Application Layer & Use Cases

## Questions Investigated

1. What are the best practices for RAG system prompts and context injection?
2. How to implement SSE streaming in FastAPI 0.115?
3. What patterns should use cases follow in Clean Architecture?
4. How should batch embedding be managed for large documents?
5. What citation format should the RAG system use?

## Findings

### 1. RAG System Prompt Best Practices

**System prompt design:**
```python
SYSTEM_PROMPT = """You are a helpful AI assistant. Answer questions based ONLY on the provided context.

Rules:
1. Use ONLY the information from the [CONTEXT] section below
2. If the context does not contain enough information, say "I don't have enough information to answer that"
3. Cite sources using [1], [2], etc. corresponding to the context blocks
4. Be concise and accurate
5. Do not make up information not present in the context

[CONTEXT]
{context}
[END CONTEXT]
"""
```

**Key principles:**
- Use clear markers (e.g., `[CONTEXT]` / `[END CONTEXT]`) to separate retrieved content from instructions
- Explicitly instruct to use ONLY provided context, never external knowledge
- Require citation using numbered references `[1]`, `[2]`
- Include fallback instruction for when context is insufficient
- Keep prompts simple — overly complex prompts degrade performance

**Context injection:**
- Format context as numbered blocks: `[1] Title: ... Content: ...`
- Include metadata (title, chunk_index) for citation mapping
- Order by relevance score (highest first)
- Stop adding context when token budget is reached

**Sources:**
- https://morphik.ai/blog/rag-best-practices
- https://medium.com/ — multiple RAG prompt engineering articles
- https://promptagent.uk — system prompt design

**Recommendation:** Keep prompts minimal. Use `[CONTEXT]` markers. Number each context block. Instruct for `[1]`, `[2]` citations.

---

### 2. FastAPI SSE Streaming

**Version**: FastAPI 0.115.14

FastAPI 0.135+ has built-in `EventSourceResponse` — we're on 0.115, so use `StreamingResponse` with `text/event-stream` media type.

**Pattern:**
```python
from fastapi import APIRouter
from starlette.responses import StreamingResponse
import json

router = APIRouter()

@router.post("/chat/stream")
async def stream_chat(request: ChatRequest):
    async def generate():
        async for chunk in rag_chat_use_case.stream(request):
            data = json.dumps(chunk.model_dump())
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

**SSE protocol:**
- Each event: `data: {json}\n\n` (double newline terminates event)
- Final event: `data: [DONE]\n\n` (signals end of stream)
- Content-Type: `text/event-stream`
- Headers: `Cache-Control: no-cache`, `Connection: keep-alive`

**Key insight:** The async generator in the use case yields domain objects. The API layer formats them as SSE events. Clean separation.

**Sources:**
- https://medium.com — FastAPI SSE patterns
- https://starlette.io/docs/responses

**Recommendation:** Use `StreamingResponse` with `text/event-stream`. Use case returns `AsyncGenerator[StreamChunk]`, API layer wraps as SSE JSON events.

---

### 3. Use Case Patterns in Clean Architecture

**Pattern:** One public method per use case (`execute()` or `stream()`).

```python
class SomeUseCase:
    def __init__(self, repo: Repository, service: Service):
        self._repo = repo
        self._service = service
    
    async def execute(self, request: RequestDTO) -> ResponseDTO:
        # 1. Validate input
        # 2. Call domain services
        # 3. Persist via repos
        # 4. Return DTO (not domain entity)
        ...
```

**Rules:**
- Use cases depend on ABCs (repositories, services), injected via constructor
- Input: DTO (Pydantic model), Output: DTO
- Never expose domain entities directly to the API layer
- Use cases orchestrate; they don't contain business logic (that's in domain services)
- Each use case is a single responsibility

**Factory vs Singleton:** Use cases should be **Factory** providers (new instance per request) because they might hold per-request state. Services (prompt, context) are **Singletons** because they're stateless.

**Recommendation:** One-method use cases with DTO I/O. Factory providers in DI container. Domain entities stay inside the use case boundary.

---

### 4. Batch Embedding Strategy

For the processing pipeline, documents may produce 100+ chunks. The OpenAI embedding API accepts up to ~2000 texts per batch, but there are practical limits:

**Strategy:**
```python
BATCH_SIZE = 50  # chunks per API call

async def embed_chunks(chunks: list[Chunk]) -> list[EmbeddingVector]:
    results = []
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = [c.content for c in chunks[i:i + BATCH_SIZE]]
        embeddings = await embedding_provider.embed_batch(batch)
        results.extend(embeddings)
    return results
```

**Why 50?**
- OpenAI rate limits are per-minute, not per-request
- 50 chunks × ~500 tokens ≈ 25K tokens per call — well within limits
- Keeps individual requests fast (<5s typical)
- If a batch fails, only 50 chunks need retrying

**Recommendation:** Batch in groups of 50. Track progress via `job.record_progress()`. Built-in SDK retry handles transient failures.

---

### 5. Citation Format

**Format for context blocks:**
```
[1] Document: "Getting Started Guide" (chunk 3/10)
Machine learning is a subset of artificial intelligence...

[2] Document: "Advanced Topics" (chunk 1/15)
Neural networks are composed of layers...
```

**Citation in response:** The LLM references sources as `[1]`, `[2]` inline. The response includes a `sources` list mapping numbers to SearchResult metadata.

**Recommendation:** Number context blocks sequentially. Include document title and chunk position. Map citation numbers to SearchResultDTO in the response.

---

### 6. Existing Codebase Assets

Already implemented and available for Phase 3:

| Asset | Location | What it provides |
|-------|----------|------------------|
| Document entity | `app/domain/entities/document.py` | Status FSM (PENDING→PROCESSING→COMPLETED/FAILED) |
| IngestionJob entity | `app/domain/entities/ingestion_job.py` | 7-stage FSM with progress tracking |
| Chunk entity | `app/domain/entities/chunk.py` | `set_embedding()`, `has_embedding()` |
| ChunkingStrategy | `app/domain/services/chunking_service.py` | SimpleChunkingStrategy with overlap |
| ChatMessage/Response | `app/domain/entities/chat.py` | MessageRole, TokenUsage, ChatResponse |
| SearchResult | `app/domain/entities/search_result.py` | score, content, metadata, chunk_id |
| OpenAI embedding | `app/infrastructure/llm/openai_embedding.py` | `embed()`, `embed_batch()` |
| OpenAI chat | `app/infrastructure/llm/openai_chat.py` | `complete()`, `stream()` |
| Qdrant adapter | `app/infrastructure/vector_db/qdrant_adapter.py` | `upsert_many()`, `search()` |
| TiktokenService | `app/infrastructure/token/tiktoken_service.py` | `count_tokens()`, `truncate_to_token_limit()` |
| BackgroundWorker | `app/infrastructure/queue/worker.py` | `enqueue()`, `start()`, `stop()` |

**Key insight:** Phase 3 is pure orchestration — all building blocks exist. No new dependencies needed.

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SSE transport | `StreamingResponse` with `text/event-stream` | FastAPI 0.115 doesn't have `EventSourceResponse` |
| Citation format | Numbered `[1]`, `[2]` inline | Simple, universally understood, easy to parse |
| Context markers | `[CONTEXT]` / `[END CONTEXT]` | Clear separation, prevents prompt injection |
| Batch size | 50 chunks per embedding API call | Balance between speed and rate limit safety |
| Use case providers | Factory (new per request) | Avoids shared state between requests |
| Service providers | Singleton | Stateless, safe to share |
| System prompt style | Minimal with explicit rules | Complex prompts degrade LLM performance |

## Patterns to Follow

- **DTO boundary**: Use cases accept DTOs, return DTOs — never expose domain entities to API
- **Single responsibility**: One use case = one workflow (ingest, process, search, chat)
- **Orchestration only**: Use cases wire domain services + repos — no business logic in use cases
- **Token budget**: Stop adding context when budget exhausted, don't truncate mid-chunk
- **SSE terminator**: Always send `data: [DONE]\n\n` as the final event

## Anti-Patterns to Avoid

- **No entity leakage**: Never return domain entities from use cases — always map to DTOs
- **No prompt complexity**: Don't over-engineer prompts with complex instructions
- **No synchronous embedding**: Always use `embed_batch()` not individual `embed()` in pipeline
- **No unbounded context**: Always enforce token budget in context building
- **No blocking in use cases**: All I/O must be async

## Dependencies Identified

No new dependencies needed. All required packages are already installed:
- FastAPI 0.115.14 (StreamingResponse for SSE)
- All OpenAI/Qdrant/Redis/tiktoken infrastructure from Phase 2

## Risks

- **Token counting accuracy**: tiktoken may slightly differ from OpenAI's server-side count. **Mitigation**: Use conservative estimates (90% of budget).
- **Streaming error handling**: If the LLM stream fails mid-response, the client receives a partial response. **Mitigation**: Send error event as final SSE message.
- **Context window overflow**: Long chat histories + context could exceed model limits. **Mitigation**: ContextService enforces strict token budget.

## Ready for Planning

- [x] Questions answered
- [x] Approach selected
- [x] Dependencies identified
- [x] SSE streaming pattern validated
- [x] RAG prompt template designed
- [x] Citation format chosen
- [x] Batch strategy defined
- [x] Risks assessed
