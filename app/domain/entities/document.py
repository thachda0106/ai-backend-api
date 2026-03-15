"""Document entity with status transitions."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from app.domain.entities.base import Entity
from app.domain.value_objects.identifiers import CollectionId, DocumentId


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Entity):
    """A text document submitted for RAG processing.

    Documents are the primary input to the ingestion pipeline.
    Each document belongs to a collection and goes through
    chunking → embedding → vector storage.
    """

    document_id: DocumentId = Field(default_factory=DocumentId)
    collection_id: CollectionId
    title: str
    content: str
    content_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: DocumentStatus = DocumentStatus.PENDING
    chunk_count: int = 0
    token_count: int = 0
    error_message: str | None = None

    def mark_processing(self) -> None:
        """Transition document to processing status."""
        self.status = DocumentStatus.PROCESSING
        self.error_message = None
        self.update()

    def mark_completed(self, chunk_count: int, token_count: int) -> None:
        """Transition document to completed status with counts.

        Args:
            chunk_count: Number of chunks created.
            token_count: Total tokens in the document.
        """
        self.status = DocumentStatus.COMPLETED
        self.chunk_count = chunk_count
        self.token_count = token_count
        self.error_message = None
        self.update()

    def mark_failed(self, error: str) -> None:
        """Transition document to failed status with error message.

        Args:
            error: Description of the failure.
        """
        self.status = DocumentStatus.FAILED
        self.error_message = error
        self.update()

    @property
    def is_processable(self) -> bool:
        """Check if document can be processed (pending or failed)."""
        return self.status in (DocumentStatus.PENDING, DocumentStatus.FAILED)
