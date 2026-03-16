---
phase: 4
plan: 4
wave: 2
depends_on: [1, 2]
files_modified:
  - app/api/routers/chat.py
autonomous: true

must_haves:
  truths:
    - "Chat endpoint supports both JSON response and SSE streaming"
    - "SSE uses sse-starlette EventSourceResponse"
    - "Streaming is controlled by the 'stream' field in the request body"
    - "Stream events use data-only SSE with JSON payloads"
---

# Plan 4.4: Chat Router with SSE Streaming

## Objective
Implement the `POST /chat` router that supports both non-streaming JSON responses and Server-Sent Events (SSE) streaming. This is the most complex endpoint — it bridges the RAGChatUseCase's streaming generator to SSE via `sse-starlette`.

## Context
- @app/api/schemas/chat.py — ChatRequest (with stream field), ChatResponse, StreamEvent (from Plan 4.1)
- @app/api/dependencies/container.py — get_rag_chat_use_case (from Plan 4.2)
- @app/core/security/api_key.py — RequireAPIKey
- @app/application/use_cases/rag_chat.py — RAGChatUseCase.execute() and .stream()
- @app/application/dto/chat.py — ChatRequest DTO, ChatResponseDTO, StreamChunk
- pyproject.toml — sse-starlette ^2.2 already in deps

## Tasks

<task type="auto">
  <name>Create chat router with streaming support</name>
  <files>
    app/api/routers/chat.py
  </files>
  <action>
    Create the chat router with dual-mode (JSON + SSE):

    ```python
    router = APIRouter(prefix="/chat", tags=["chat"])

    @router.post(
        "",
        summary="RAG chat",
        description="Chat with documents using RAG. Set stream=true for Server-Sent Events streaming.",
        responses={
            200: {"model": ChatApiResponse, "description": "Non-streaming JSON response"},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
        },
    )
    async def chat(
        body: ChatApiRequest,
        api_key: RequireAPIKey,
        use_case: RAGChatUseCaseDep,
    ) -> ChatApiResponse | EventSourceResponse:
    ```

    **Non-streaming path (stream=False):**
    1. Map API schema → `ChatRequest` DTO
    2. Call `use_case.execute(dto)`
    3. Map `ChatResponseDTO` → `ChatApiResponse`
    4. Return JSON 200

    **Streaming path (stream=True):**
    1. Map API schema → `ChatRequest` DTO
    2. Create an async generator that wraps `use_case.stream(dto)`:
       ```python
       async def event_generator():
           async for chunk in use_case.stream(dto):
               event_data = StreamEvent(
                   content=chunk.content,
                   done=chunk.done,
                   sources=[SourceResponse(...) for s in (chunk.sources or [])],
                   ...
               )
               yield event_data.model_dump_json()
       ```
    3. Return `EventSourceResponse(event_generator(), media_type="text/event-stream")`

    **SSE format:** Each event is `data: {json}\n\n`. The last event has `done: true` with sources and usage.

    **Client cancellation:** The `EventSourceResponse` handles client disconnects automatically. Add a try/except for `asyncio.CancelledError` in the generator to clean up gracefully.

    Do NOT import from sse_starlette at module level if it breaks typing — use TYPE_CHECKING guard.
  </action>
  <verify>python -m poetry run python -c "from app.api.routers.chat import router; print(f'Routes: {[r.path for r in router.routes]}')"</verify>
  <done>POST /chat works in both JSON and SSE streaming modes</done>
</task>

<task type="auto">
  <name>Update routers __init__.py to include chat</name>
  <files>
    app/api/routers/__init__.py
  </files>
  <action>
    Update the `register_routers` function (from Plan 4.3) to include the chat router:

    ```python
    from app.api.routers.chat import router as chat_router

    def register_routers(app: FastAPI) -> None:
        app.include_router(documents_router)
        app.include_router(search_router)
        app.include_router(chat_router)
    ```
  </action>
  <verify>python -m poetry run python -c "from app.api.routers import register_routers; print('Router registration OK')"</verify>
  <done>All three routers (documents, search, chat) registered via register_routers()</done>
</task>

## Success Criteria
- [ ] POST /chat with stream=false returns JSON ChatResponse
- [ ] POST /chat with stream=true returns SSE EventSourceResponse
- [ ] SSE events are JSON data with content deltas
- [ ] Final SSE event includes sources and token usage
- [ ] Client disconnection is handled gracefully
