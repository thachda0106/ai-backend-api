"""Chat API router."""

import asyncio
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, Depends, Request, status
from sse_starlette.sse import EventSourceResponse

from app.api.dependencies.container import RAGChatUseCaseDep
from app.api.schemas.chat import ChatRequest as ApiChatRequest
from app.api.schemas.chat import ChatResponse as ApiChatResponse
from app.api.schemas.chat import SourceResponse as ApiSourceResponse
from app.api.schemas.common import ErrorResponse
from app.application.dto.chat import ChatRequest as DtoChatRequest
from app.core.security.api_key import RequireAPIKey

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
    dependencies=[Depends(RequireAPIKey)],
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        413: {"model": ErrorResponse, "description": "Content Too Large (Token Limit Exceeded)"},
        429: {"model": ErrorResponse, "description": "Too Many Requests"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
        502: {"model": ErrorResponse, "description": "Bad Gateway (LLM Provider Error)"},
    },
)


@router.post(
    "",
    response_model=ApiChatResponse,
    status_code=status.HTTP_200_OK,
    summary="RAG Chat endpoint",
    description="Send a message to the AI assistant. Supports both complete JSON responses and Server-Sent Events (SSE) streaming via the `stream` flag.",
)
async def chat(
    request: ApiChatRequest,
    use_case: RAGChatUseCaseDep,
    http_request: Request,
) -> ApiChatResponse | EventSourceResponse:
    """Handle chat request (streaming or non-streaming)."""
    # Map API schema to Application DTO
    dto_request = DtoChatRequest(
        message=request.message,
        conversation_id=request.conversation_id,
        user_id=request.user_id,
        top_k=request.top_k,
    )

    if request.stream:
        # Handle SSE Streaming
        return EventSourceResponse(
            _stream_generator(use_case, dto_request, http_request),
            media_type="text/event-stream",
        )

    # Handle Non-Streaming (JSON)
    dto_response = await use_case.execute(dto_request)

    # Map DTO sources to API sources
    api_sources = [
        ApiSourceResponse(
            index=s.index,
            chunk_id=s.chunk_id,
            document_id=s.document_id,
            document_title=s.document_title,
            content=s.content,
            score=s.score,
        )
        for s in dto_response.sources
    ]

    return ApiChatResponse(
        message=dto_response.message,
        sources=api_sources,
        prompt_tokens=dto_response.prompt_tokens,
        completion_tokens=dto_response.completion_tokens,
        total_tokens=dto_response.total_tokens,
    )


async def _stream_generator(
    use_case: RAGChatUseCaseDep,
    request: DtoChatRequest,
    http_request: Request,
) -> AsyncGenerator[str, None]:
    """Generate SSE events from the use case stream.

    Yields JSON strings matching the StreamEvent schema.
    FastAPI's EventSourceResponse will format these as `data: {json}`.
    """
    try:
        async for chunk in use_case.stream(request):
            # Check if client disconnected
            if await http_request.is_disconnected():
                await logger.ainfo("client_disconnected_during_stream")
                break

            # chunk is a StreamChunk DTO. We yield its JSON representation
            # which matches the StreamEvent API schema.
            yield chunk.model_dump_json(exclude_none=True)

    except asyncio.CancelledError:
        await logger.ainfo("stream_cancelled_by_client")
        raise
