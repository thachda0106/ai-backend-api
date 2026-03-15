"""In-memory document repository for development and testing.

Thread-safe implementation using asyncio.Lock.
"""

from __future__ import annotations

import asyncio

from app.domain.entities.document import Document
from app.domain.repositories.document_repository import DocumentRepository
from app.domain.value_objects.identifiers import CollectionId, DocumentId
from app.domain.value_objects.pagination import PaginationParams


class InMemoryDocumentRepository(DocumentRepository):
    """In-memory document storage.

    All data is lost on process restart. Suitable for development
    and testing only. Production should use a persistent store.
    """

    def __init__(self) -> None:
        self._store: dict[str, Document] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(self, document_id: DocumentId) -> Document | None:
        """Retrieve a document by its ID."""
        return self._store.get(str(document_id.value))

    async def get_by_collection(
        self,
        collection_id: CollectionId,
        pagination: PaginationParams,
    ) -> list[Document]:
        """Retrieve documents in a collection with pagination."""
        matching = [
            doc
            for doc in self._store.values()
            if doc.collection_id == collection_id
        ]
        # Sort by created_at descending for consistency
        matching.sort(key=lambda d: d.created_at, reverse=True)

        start = pagination.offset
        end = start + pagination.limit
        return matching[start:end]

    async def save(self, document: Document) -> Document:
        """Persist a new document."""
        async with self._lock:
            key = str(document.document_id.value)
            self._store[key] = document
            return document

    async def update(self, document: Document) -> Document:
        """Update an existing document."""
        async with self._lock:
            key = str(document.document_id.value)
            self._store[key] = document
            return document

    async def delete(self, document_id: DocumentId) -> bool:
        """Delete a document by ID."""
        async with self._lock:
            key = str(document_id.value)
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def count_by_collection(self, collection_id: CollectionId) -> int:
        """Count documents in a collection."""
        return sum(
            1
            for doc in self._store.values()
            if doc.collection_id == collection_id
        )
