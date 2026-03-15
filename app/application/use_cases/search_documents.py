"""Semantic search use case.

Embeds a query, searches the vector store, and returns
ranked results with metadata.
"""

from __future__ import annotations

import time

import structlog

from app.application.dto.search import SearchRequest, SearchResponse, SearchResultDTO
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.services.token_service import TokenService
from app.infrastructure.llm.base import EmbeddingProvider

logger = structlog.get_logger(__name__)


class SearchDocumentsUseCase:
    """Use case for semantic document search.

    Embeds the query, searches Qdrant, and returns
    ranked results mapped to DTOs.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_repository: VectorRepository,
        token_service: TokenService,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_repo = vector_repository
        self._token_service = token_service

    async def execute(self, request: SearchRequest) -> SearchResponse:
        """Execute semantic search.

        Args:
            request: Search request with query, optional filters, top_k.

        Returns:
            SearchResponse with ranked results and token counts.
        """
        start_time = time.monotonic()

        # Count query tokens
        query_tokens = self._token_service.count_tokens(request.query, "gpt-4o")

        # Embed query
        query_embedding = await self._embedding_provider.embed(request.query)

        # Build filters
        filters = dict(request.filters) if request.filters else None
        if request.collection_id:
            filters = filters or {}
            filters["collection_id"] = request.collection_id

        # Search vectors
        results = await self._vector_repo.search(
            query_embedding=query_embedding,
            top_k=request.top_k,
            filters=filters,
        )

        # Map to DTOs
        result_dtos = [
            SearchResultDTO(
                chunk_id=str(r.chunk_id.value),
                document_id=str(r.document_id.value),
                content=r.content,
                score=r.score,
                metadata=r.metadata,
                document_title=r.document_title,
                chunk_index=r.chunk_index,
            )
            for r in results
        ]

        elapsed = time.monotonic() - start_time

        await logger.ainfo(
            "search_completed",
            query_length=len(request.query),
            query_tokens=query_tokens,
            top_k=request.top_k,
            results_count=len(result_dtos),
            has_filters=filters is not None,
            elapsed_seconds=round(elapsed, 3),
        )

        return SearchResponse(
            results=result_dtos,
            total=len(result_dtos),
            query_tokens=query_tokens,
        )
