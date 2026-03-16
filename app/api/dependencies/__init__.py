"""API dependencies package — re-exports dependency functions and type aliases."""

from app.api.dependencies.container import (
    IngestUseCaseDep,
    RAGChatUseCaseDep,
    RateLimiterDep,
    SearchUseCaseDep,
    get_ingest_use_case,
    get_rag_chat_use_case,
    get_rate_limiter,
    get_search_use_case,
)

__all__ = [
    "IngestUseCaseDep",
    "RAGChatUseCaseDep",
    "RateLimiterDep",
    "SearchUseCaseDep",
    "get_ingest_use_case",
    "get_rag_chat_use_case",
    "get_rate_limiter",
    "get_search_use_case",
]
