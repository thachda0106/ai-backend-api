"""FastAPI dependency functions for DI container access.

These functions extract use cases and services from the DI container
stored on app.state, providing clean Depends() injection for routers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.application.use_cases.ingest_document import IngestDocumentUseCase
from app.application.use_cases.rag_chat import RAGChatUseCase
from app.application.use_cases.search_documents import SearchDocumentsUseCase
from app.infrastructure.cache.rate_limiter import RedisRateLimiter


def get_ingest_use_case(request: Request) -> IngestDocumentUseCase:
    """Extract IngestDocumentUseCase from DI container."""
    return request.app.state.container.ingest_document()  # type: ignore[no-any-return]


def get_search_use_case(request: Request) -> SearchDocumentsUseCase:
    """Extract SearchDocumentsUseCase from DI container."""
    return request.app.state.container.search_documents()  # type: ignore[no-any-return]


def get_rag_chat_use_case(request: Request) -> RAGChatUseCase:
    """Extract RAGChatUseCase from DI container."""
    return request.app.state.container.rag_chat()  # type: ignore[no-any-return]


def get_rate_limiter(request: Request) -> RedisRateLimiter:
    """Extract RedisRateLimiter from DI container."""
    return request.app.state.container.rate_limiter()  # type: ignore[no-any-return]


# ── Type aliases for clean router signatures ──────

IngestUseCaseDep = Annotated[IngestDocumentUseCase, Depends(get_ingest_use_case)]
SearchUseCaseDep = Annotated[SearchDocumentsUseCase, Depends(get_search_use_case)]
RAGChatUseCaseDep = Annotated[RAGChatUseCase, Depends(get_rag_chat_use_case)]
RateLimiterDep = Annotated[RedisRateLimiter, Depends(get_rate_limiter)]
