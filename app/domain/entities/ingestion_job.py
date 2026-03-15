"""IngestionJob entity for tracking document processing pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import Field

from app.domain.entities.base import Entity
from app.domain.value_objects.identifiers import DocumentId, IngestionJobId


class IngestionStatus(str, Enum):
    """Ingestion pipeline status stages."""

    QUEUED = "queued"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    STORING = "storing"
    COMPLETED = "completed"
    FAILED = "failed"


# Valid status transitions
_VALID_TRANSITIONS: dict[IngestionStatus, set[IngestionStatus]] = {
    IngestionStatus.QUEUED: {IngestionStatus.EXTRACTING, IngestionStatus.FAILED},
    IngestionStatus.EXTRACTING: {IngestionStatus.CHUNKING, IngestionStatus.FAILED},
    IngestionStatus.CHUNKING: {IngestionStatus.EMBEDDING, IngestionStatus.FAILED},
    IngestionStatus.EMBEDDING: {IngestionStatus.STORING, IngestionStatus.FAILED},
    IngestionStatus.STORING: {IngestionStatus.COMPLETED, IngestionStatus.FAILED},
    IngestionStatus.COMPLETED: set(),
    IngestionStatus.FAILED: {IngestionStatus.QUEUED},  # Allow retry
}


class IngestionJob(Entity):
    """Tracks the progress of a document through the ingestion pipeline.

    The pipeline stages are:
    QUEUED → EXTRACTING → CHUNKING → EMBEDDING → STORING → COMPLETED
    Any stage can transition to FAILED, and FAILED can retry (→ QUEUED).
    """

    job_id: IngestionJobId = Field(default_factory=IngestionJobId)
    document_id: DocumentId
    status: IngestionStatus = IngestionStatus.QUEUED
    total_chunks: int = 0
    processed_chunks: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def advance_status(self, new_status: IngestionStatus) -> None:
        """Advance to a new pipeline status with transition validation.

        Args:
            new_status: The target status.

        Raises:
            ValueError: If the transition is not valid.
        """
        valid = _VALID_TRANSITIONS.get(self.status, set())
        if new_status not in valid:
            msg = f"Invalid transition: {self.status.value} → {new_status.value}"
            raise ValueError(msg)

        self.status = new_status

        if new_status == IngestionStatus.EXTRACTING and self.started_at is None:
            self.started_at = datetime.now(timezone.utc)

        self.update()

    def record_progress(self, processed: int, total: int) -> None:
        """Update chunk processing progress.

        Args:
            processed: Number of chunks processed so far.
            total: Total number of chunks to process.
        """
        self.processed_chunks = processed
        self.total_chunks = total
        self.update()

    def fail(self, error: str) -> None:
        """Mark the job as failed with an error message.

        Args:
            error: Description of the failure.
        """
        self.status = IngestionStatus.FAILED
        self.error_message = error
        self.update()

    def complete(self) -> None:
        """Mark the job as completed."""
        self.status = IngestionStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = None
        self.update()

    @property
    def progress(self) -> float:
        """Calculate processing progress as a percentage (0.0 to 1.0)."""
        if self.total_chunks == 0:
            return 0.0
        return self.processed_chunks / self.total_chunks
