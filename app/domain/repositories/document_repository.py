"""Abstract document repository interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.entities.document import Document
from app.domain.value_objects.identifiers import CollectionId, DocumentId
from app.domain.value_objects.pagination import PaginationParams


class DocumentRepository(ABC):
    """Abstract interface for document persistence.

    Implementations may use in-memory storage, databases,
    or any other persistence mechanism.
    """

    @abstractmethod
    async def get_by_id(self, document_id: DocumentId) -> Document | None:
        """Retrieve a document by its ID.

        Returns None if not found.
        """

    @abstractmethod
    async def get_by_collection(
        self,
        collection_id: CollectionId,
        pagination: PaginationParams,
    ) -> list[Document]:
        """Retrieve documents belonging to a collection with pagination."""

    @abstractmethod
    async def save(self, document: Document) -> Document:
        """Persist a new document. Returns the saved document."""

    @abstractmethod
    async def update(self, document: Document) -> Document:
        """Update an existing document. Returns the updated document."""

    @abstractmethod
    async def delete(self, document_id: DocumentId) -> bool:
        """Delete a document by ID. Returns True if deleted."""

    @abstractmethod
    async def count_by_collection(self, collection_id: CollectionId) -> int:
        """Count documents in a collection."""
