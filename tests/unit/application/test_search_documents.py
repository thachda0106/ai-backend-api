"""Unit tests for SearchDocumentsUseCase.

Mocks: EmbeddingProvider, VectorRepository, TokenService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.search import SearchRequest, SearchResponse
from app.application.use_cases.search_documents import SearchDocumentsUseCase
from app.domain.entities.search_result import SearchResult
from app.domain.value_objects.identifiers import ChunkId, CollectionId, DocumentId


def make_search_result(score: float = 0.9) -> SearchResult:
    return SearchResult(
        chunk_id=ChunkId(),
        document_id=DocumentId(),
        collection_id=CollectionId(),
        content="Relevant chunk content",
        score=score,
        metadata={"source": "test"},
        document_title="Test Doc",
        chunk_index=0,
    )



@pytest.fixture
def embedding_provider() -> MagicMock:
    provider = MagicMock()
    provider.embed = AsyncMock(return_value=[0.1] * 1536)
    return provider


@pytest.fixture
def vector_repo() -> MagicMock:
    repo = MagicMock()
    repo.search = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def token_service() -> MagicMock:
    svc = MagicMock()
    svc.count_tokens = MagicMock(return_value=5)
    return svc


@pytest.fixture
def use_case(
    embedding_provider: MagicMock,
    vector_repo: MagicMock,
    token_service: MagicMock,
) -> SearchDocumentsUseCase:
    return SearchDocumentsUseCase(
        embedding_provider=embedding_provider,
        vector_repository=vector_repo,
        token_service=token_service,
    )


class TestSearchDocumentsUseCase:
    @pytest.mark.asyncio
    async def test_returns_search_response(self, use_case: SearchDocumentsUseCase) -> None:
        request = SearchRequest(query="What is RAG?", top_k=5)
        result = await use_case.execute(request)
        assert isinstance(result, SearchResponse)

    @pytest.mark.asyncio
    async def test_embeds_query(
        self,
        use_case: SearchDocumentsUseCase,
        embedding_provider: MagicMock,
    ) -> None:
        """The query string is passed to the embedding provider."""
        request = SearchRequest(query="What is RAG?", top_k=5)
        await use_case.execute(request)
        embedding_provider.embed.assert_called_once_with("What is RAG?")

    @pytest.mark.asyncio
    async def test_empty_results_returns_zero_total(
        self,
        use_case: SearchDocumentsUseCase,
        vector_repo: MagicMock,
    ) -> None:
        """Zero vector results → total=0 in response."""
        vector_repo.search.return_value = []
        request = SearchRequest(query="empty", top_k=5)
        result = await use_case.execute(request)
        assert result.total == 0
        assert result.results == []

    @pytest.mark.asyncio
    async def test_results_mapped_to_dtos(
        self,
        use_case: SearchDocumentsUseCase,
        vector_repo: MagicMock,
    ) -> None:
        """SearchResult domain objects are correctly mapped to SearchResultDTO."""
        sr = make_search_result(score=0.95)
        vector_repo.search.return_value = [sr]

        request = SearchRequest(query="test query", top_k=3)
        result = await use_case.execute(request)

        assert result.total == 1
        dto = result.results[0]
        assert dto.score == 0.95
        assert dto.content == "Relevant chunk content"
        assert dto.document_title == "Test Doc"

    @pytest.mark.asyncio
    async def test_collection_id_filter_added(
        self,
        use_case: SearchDocumentsUseCase,
        vector_repo: MagicMock,
    ) -> None:
        """collection_id is passed as a filter to vector repository."""
        import uuid
        col_id = str(uuid.uuid4())
        request = SearchRequest(query="test", top_k=5, collection_id=col_id)
        await use_case.execute(request)

        _, kwargs = vector_repo.search.call_args
        # Filters must include the collection_id
        assert kwargs.get("filters") is not None
        assert kwargs["filters"].get("collection_id") == col_id

    @pytest.mark.asyncio
    async def test_query_tokens_reported(
        self,
        use_case: SearchDocumentsUseCase,
        token_service: MagicMock,
    ) -> None:
        """query_tokens in response comes from the token_service."""
        token_service.count_tokens.return_value = 7
        request = SearchRequest(query="token test", top_k=5)
        result = await use_case.execute(request)
        assert result.query_tokens == 7
