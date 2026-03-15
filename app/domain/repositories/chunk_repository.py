"""Abstract chunk repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.chunk import Chunk
from app.domain.value_objects.identifiers import ChunkId, DocumentId


class ChunkRepository(ABC):
    """Abstract interface for chunk persistence.

    Handles storage of document chunks, supporting
    batch operations for the ingestion pipeline.
    """

    @abstractmethod
    async def get_by_id(self, chunk_id: ChunkId) -> Chunk | None:
        """Retrieve a chunk by its ID. Returns None if not found."""

    @abstractmethod
    async def get_by_document(self, document_id: DocumentId) -> list[Chunk]:
        """Retrieve all chunks belonging to a document."""

    @abstractmethod
    async def save_many(self, chunks: list[Chunk]) -> list[Chunk]:
        """Persist multiple chunks in a batch. Returns the saved chunks."""

    @abstractmethod
    async def delete_by_document(self, document_id: DocumentId) -> int:
        """Delete all chunks for a document. Returns count of deleted chunks."""

    @abstractmethod
    async def count_by_document(self, document_id: DocumentId) -> int:
        """Count chunks belonging to a document."""
