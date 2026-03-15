"""In-memory chunk repository for development and testing.

Thread-safe implementation using asyncio.Lock.
"""

from __future__ import annotations

import asyncio

from app.domain.entities.chunk import Chunk
from app.domain.repositories.chunk_repository import ChunkRepository
from app.domain.value_objects.identifiers import ChunkId, DocumentId


class InMemoryChunkRepository(ChunkRepository):
    """In-memory chunk storage.

    All data is lost on process restart. Suitable for development
    and testing only.
    """

    def __init__(self) -> None:
        self._store: dict[str, Chunk] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(self, chunk_id: ChunkId) -> Chunk | None:
        """Retrieve a chunk by its ID."""
        return self._store.get(str(chunk_id.value))

    async def get_by_document(self, document_id: DocumentId) -> list[Chunk]:
        """Retrieve all chunks belonging to a document."""
        matching = [
            chunk
            for chunk in self._store.values()
            if chunk.document_id == document_id
        ]
        # Sort by chunk_index for consistent ordering
        matching.sort(key=lambda c: c.chunk_index)
        return matching

    async def save_many(self, chunks: list[Chunk]) -> list[Chunk]:
        """Persist multiple chunks in a batch."""
        async with self._lock:
            for chunk in chunks:
                key = str(chunk.chunk_id.value)
                self._store[key] = chunk
            return chunks

    async def delete_by_document(self, document_id: DocumentId) -> int:
        """Delete all chunks for a document."""
        async with self._lock:
            to_delete = [
                key
                for key, chunk in self._store.items()
                if chunk.document_id == document_id
            ]
            for key in to_delete:
                del self._store[key]
            return len(to_delete)

    async def count_by_document(self, document_id: DocumentId) -> int:
        """Count chunks belonging to a document."""
        return sum(
            1
            for chunk in self._store.values()
            if chunk.document_id == document_id
        )
