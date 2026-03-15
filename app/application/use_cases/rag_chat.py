"""RAG chat use case.

The crown jewel: search → context building → prompt → LLM response.
Supports both non-streaming and streaming (SSE) responses.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator

import structlog

from app.application.dto.chat import (
    ChatRequest,
    ChatResponseDTO,
    SourceDTO,
    StreamChunk,
)
from app.application.dto.search import SearchRequest
from app.application.services.context_service import ContextService
from app.application.services.prompt_service import PromptService
from app.application.use_cases.search_documents import SearchDocumentsUseCase
from app.domain.entities.chat import ChatMessage, MessageRole
from app.domain.repositories.chat_repository import ChatHistoryRepository
from app.domain.services.token_service import TokenService
from app.infrastructure.llm.base import ChatProvider

logger = structlog.get_logger(__name__)


class RAGChatUseCase:
    """Retrieval-Augmented Generation chat use case.

    Pipeline: search → context → prompt → LLM → response.
    Supports streaming for real-time token delivery.
    """

    def __init__(
        self,
        search_use_case: SearchDocumentsUseCase,
        chat_provider: ChatProvider,
        prompt_service: PromptService,
        context_service: ContextService,
        chat_history_repository: ChatHistoryRepository,
        token_service: TokenService,
    ) -> None:
        self._search = search_use_case
        self._chat = chat_provider
        self._prompt_service = prompt_service
        self._context_service = context_service
        self._history_repo = chat_history_repository
        self._token_service = token_service

    async def execute(self, request: ChatRequest) -> ChatResponseDTO:
        """Execute RAG chat (non-streaming).

        Args:
            request: Chat request with message and optional parameters.

        Returns:
            ChatResponseDTO with assistant message, sources, and usage.
        """
        start_time = time.monotonic()

        # 1. Search for relevant context
        search_request = SearchRequest(
            query=request.message,
            collection_id=request.conversation_id,
            top_k=request.top_k,
        )
        search_response = await self._search.execute(search_request)

        # 2. Build context from search results (map DTOs back for context service)
        from app.domain.entities.search_result import SearchResult
        from app.domain.value_objects.identifiers import ChunkId, CollectionId, DocumentId

        domain_results = [
            SearchResult(
                chunk_id=ChunkId.from_str(r.chunk_id),
                document_id=DocumentId.from_str(r.document_id),
                collection_id=CollectionId(),
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                document_title=r.document_title,
                chunk_index=r.chunk_index,
            )
            for r in search_response.results
        ]

        context, used_results = self._context_service.build_context(domain_results)

        # 3. Get chat history for continuity
        history: list[ChatMessage] = []
        if request.user_id:
            from app.domain.value_objects.identifiers import UserId

            user_id = UserId.from_str(request.user_id)
            history = await self._history_repo.get_history(user_id, limit=5)

        # 4. Build prompt
        messages = self._prompt_service.build_rag_prompt(
            query=request.message,
            context=context,
            history=history,
        )

        # 5. Get LLM response
        chat_response = await self._chat.complete(messages)

        # 6. Save to history
        if request.user_id:
            from app.domain.value_objects.identifiers import UserId

            user_id = UserId.from_str(request.user_id)
            user_msg = ChatMessage(role=MessageRole.USER, content=request.message)
            await self._history_repo.save_message(user_id, user_msg)
            await self._history_repo.save_message(user_id, chat_response.message)

        # 7. Build sources
        sources = _build_sources(used_results)

        elapsed = time.monotonic() - start_time
        usage = chat_response.token_usage

        await logger.ainfo(
            "rag_chat_completed",
            query_length=len(request.message),
            context_results=len(used_results),
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            elapsed_seconds=round(elapsed, 3),
        )

        return ChatResponseDTO(
            message=chat_response.message.content,
            sources=sources,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            total_tokens=usage.total_tokens if usage else 0,
        )

    async def stream(self, request: ChatRequest) -> AsyncGenerator[StreamChunk, None]:
        """Stream RAG chat response via SSE.

        Args:
            request: Chat request with message and optional parameters.

        Yields:
            StreamChunk with content deltas and final metadata.
        """
        start_time = time.monotonic()

        # 1-4. Same setup as execute()
        search_request = SearchRequest(
            query=request.message,
            collection_id=request.conversation_id,
            top_k=request.top_k,
        )
        search_response = await self._search.execute(search_request)

        from app.domain.entities.search_result import SearchResult
        from app.domain.value_objects.identifiers import ChunkId, CollectionId, DocumentId

        domain_results = [
            SearchResult(
                chunk_id=ChunkId.from_str(r.chunk_id),
                document_id=DocumentId.from_str(r.document_id),
                collection_id=CollectionId(),
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                document_title=r.document_title,
                chunk_index=r.chunk_index,
            )
            for r in search_response.results
        ]

        context, used_results = self._context_service.build_context(domain_results)

        history: list[ChatMessage] = []
        if request.user_id:
            from app.domain.value_objects.identifiers import UserId

            user_id = UserId.from_str(request.user_id)
            history = await self._history_repo.get_history(user_id, limit=5)

        messages = self._prompt_service.build_rag_prompt(
            query=request.message,
            context=context,
            history=history,
        )

        # 5. Stream LLM response
        full_content = ""
        async for delta in self._chat.stream(messages):
            full_content += delta
            yield StreamChunk(content=delta)

        # 6. Final chunk with sources and usage
        sources = _build_sources(used_results)

        # Estimate tokens for streaming (exact usage not available)
        prompt_tokens = self._token_service.count_tokens(
            " ".join(m.content for m in messages), "gpt-4o"
        )
        completion_tokens = self._token_service.count_tokens(full_content, "gpt-4o")

        yield StreamChunk(
            content="",
            done=True,
            sources=sources,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

        # 7. Save to history
        if request.user_id:
            from app.domain.value_objects.identifiers import UserId

            user_id = UserId.from_str(request.user_id)
            user_msg = ChatMessage(role=MessageRole.USER, content=request.message)
            assistant_msg = ChatMessage(role=MessageRole.ASSISTANT, content=full_content)
            await self._history_repo.save_message(user_id, user_msg)
            await self._history_repo.save_message(user_id, assistant_msg)

        elapsed = time.monotonic() - start_time
        await logger.ainfo(
            "rag_stream_completed",
            query_length=len(request.message),
            context_results=len(used_results),
            completion_tokens=completion_tokens,
            elapsed_seconds=round(elapsed, 3),
        )


def _build_sources(
    results: list,
) -> list[SourceDTO]:
    """Map search results to source citation DTOs."""
    from app.domain.entities.search_result import SearchResult

    sources: list[SourceDTO] = []
    for i, result in enumerate(results):
        if isinstance(result, SearchResult):
            sources.append(
                SourceDTO(
                    index=i + 1,
                    chunk_id=str(result.chunk_id.value),
                    document_id=str(result.document_id.value),
                    document_title=result.document_title,
                    content=result.content[:200],  # Truncate for preview
                    score=result.score,
                )
            )
    return sources
