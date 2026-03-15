"""Abstract vector repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.entities.search_result import SearchResult
from app.domain.value_objects.embedding import EmbeddingVector
from app.domain.value_objects.identifiers import ChunkId, DocumentId


class VectorRepository(ABC):
    """Abstract interface for vector storage and similarity search.

    This is the contract that Qdrant (or any vector DB) must implement.
    """

    @abstractmethod
    async def upsert(
        self,
        chunk_id: ChunkId,
        embedding: EmbeddingVector,
        metadata: dict[str, Any],
    ) -> None:
        """Insert or update a single vector with metadata."""

    @abstractmethod
    async def upsert_many(
        self,
        entries: list[tuple[ChunkId, EmbeddingVector, dict[str, Any]]],
    ) -> None:
        """Insert or update multiple vectors in a batch."""

    @abstractmethod
    async def search(
        self,
        query_embedding: EmbeddingVector,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform similarity search and return ranked results."""

    @abstractmethod
    async def delete(self, chunk_id: ChunkId) -> bool:
        """Delete a single vector. Returns True if deleted."""

    @abstractmethod
    async def delete_by_document(self, document_id: DocumentId) -> int:
        """Delete all vectors for a document. Returns count of deleted vectors."""

    @abstractmethod
    async def ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
    ) -> None:
        """Ensure the vector collection exists with the correct configuration."""
