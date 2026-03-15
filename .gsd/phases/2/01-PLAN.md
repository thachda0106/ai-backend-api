---
phase: 2
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/infrastructure/llm/__init__.py
  - app/infrastructure/llm/base.py
  - app/infrastructure/llm/openai_embedding.py
  - app/infrastructure/llm/openai_chat.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "LLM provider abstraction exists as ABC (embedding + chat)"
    - "OpenAI embedding service handles batch processing with retries"
    - "OpenAI chat service supports streaming via async generators"
    - "Both services use SecretStr-based config from settings"
---

# Plan 2.1: LLM Provider Abstraction + OpenAI Client

## Objective
Implement the LLM provider abstraction layer and concrete OpenAI implementations for embeddings and chat completions. This is the core AI integration — all downstream services (vector search, RAG chat) depend on this.

## Context
- @app/core/config/settings.py — OpenAISettings with api_key, model, embedding_model
- @app/domain/value_objects/embedding.py — EmbeddingVector value object
- @app/domain/exceptions/llm.py — LLM exception hierarchy
- @.gsd/phases/1/RESEARCH.md — dependency-injector patterns (Factory/Singleton)

## Tasks

<task type="auto">
  <name>Create LLM provider abstraction interfaces</name>
  <files>app/infrastructure/llm/base.py</files>
  <action>
    Create two abstract base classes:
    
    1. `EmbeddingProvider(ABC)`:
       - `async def embed(self, text: str) -> EmbeddingVector`
       - `async def embed_batch(self, texts: list[str]) -> list[EmbeddingVector]`
    
    2. `ChatProvider(ABC)`:
       - `async def complete(self, messages: list[ChatMessage]) -> ChatMessage`
       - `async def stream(self, messages: list[ChatMessage]) -> AsyncGenerator[str, None]`
    
    Import types from domain layer. These ABCs live in infrastructure (not domain) because they are integration-layer concerns — the domain doesn't know about LLMs directly.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.llm.base import EmbeddingProvider, ChatProvider; import inspect; assert inspect.isabstract(EmbeddingProvider); assert inspect.isabstract(ChatProvider); print('OK')"</verify>
  <done>Both ABCs importable and abstract</done>
</task>

<task type="auto">
  <name>Implement OpenAI embedding service</name>
  <files>app/infrastructure/llm/openai_embedding.py</files>
  <action>
    Implement `OpenAIEmbeddingService(EmbeddingProvider)`:
    
    - Constructor takes `settings: OpenAISettings`
    - Creates `openai.AsyncOpenAI(api_key=settings.api_key.get_secret_value())`
    - `embed()`: calls `client.embeddings.create()`, returns `EmbeddingVector`
    - `embed_batch()`: sends multiple texts in a single API call via `input=[...]`
    - Retry logic: wrap calls with `tenacity` or manual retry (3 attempts, exponential backoff)
    - Map OpenAI errors to domain exceptions:
      - `openai.RateLimitError` → `LLMRateLimitException`
      - `openai.APIConnectionError` → `LLMConnectionException`
      - `openai.APIError` → `EmbeddingException`
    - Log all calls with structlog (model, dimensions, latency)
    
    AVOID: Don't store the async client as instance variable at init time if the event loop isn't running yet — create lazily or accept it as a parameter.
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.llm.openai_embedding import OpenAIEmbeddingService; print('OK')"</verify>
  <done>OpenAIEmbeddingService importable with embed() and embed_batch() methods</done>
</task>

<task type="auto">
  <name>Implement OpenAI chat completion service</name>
  <files>app/infrastructure/llm/openai_chat.py</files>
  <action>
    Implement `OpenAIChatService(ChatProvider)`:
    
    - Constructor takes `settings: OpenAISettings`
    - Creates `openai.AsyncOpenAI(api_key=...)`
    - `complete()`: calls `client.chat.completions.create(stream=False)`, returns ChatMessage
    - `stream()`: calls `client.chat.completions.create(stream=True)`, yields content deltas as `AsyncGenerator[str, None]`
    - Return `TokenUsage` with prompt/completion/total tokens from API response
    - Map errors same as embedding service
    - Log model, token usage, latency
    
    The stream method must properly handle the SSE stream from OpenAI and yield only content deltas (not full objects).
  </action>
  <verify>python -m poetry run python -c "from app.infrastructure.llm.openai_chat import OpenAIChatService; print('OK')"</verify>
  <done>OpenAIChatService importable with complete() and stream() methods</done>
</task>

## Success Criteria
- [ ] `EmbeddingProvider` and `ChatProvider` ABCs defined
- [ ] `OpenAIEmbeddingService` implements embed/embed_batch with retry + error mapping
- [ ] `OpenAIChatService` implements complete/stream with token usage tracking
- [ ] All services use structlog for observability
