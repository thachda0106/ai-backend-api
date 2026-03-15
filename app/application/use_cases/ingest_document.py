"""Document ingestion use case.

Handles the entry point for adding documents to the RAG system:
save document, create ingestion job, and enqueue background processing.
"""

from __future__ import annotations

import structlog

from app.application.dto.document import IngestDocumentRequest, IngestDocumentResponse
from app.domain.entities.document import Document
from app.domain.entities.ingestion_job import IngestionJob
from app.domain.repositories.document_repository import DocumentRepository
from app.domain.value_objects.identifiers import CollectionId
from app.infrastructure.queue.worker import BackgroundWorker

logger = structlog.get_logger(__name__)


class IngestDocumentUseCase:
    """Use case for ingesting a new document into the RAG system.

    Saves the document, creates an ingestion job, and enqueues
    the processing pipeline as a background task.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        background_worker: BackgroundWorker,
    ) -> None:
        self._document_repo = document_repository
        self._worker = background_worker
        # process_document_use_case will be injected in Plan 3.6
        self._process_use_case: object | None = None

    def set_process_use_case(self, process_use_case: object) -> None:
        """Set the processing pipeline use case (wired in Plan 3.6)."""
        self._process_use_case = process_use_case

    async def execute(self, request: IngestDocumentRequest) -> IngestDocumentResponse:
        """Ingest a document and enqueue processing.

        Args:
            request: Document ingestion request DTO.

        Returns:
            IngestDocumentResponse with document_id, job_id, and status.
        """
        # Create document entity
        collection_id = (
            CollectionId.from_str(request.collection_id)
            if request.collection_id
            else CollectionId()
        )

        document = Document(
            collection_id=collection_id,
            title=request.title,
            content=request.content,
            content_type=request.content_type,
            metadata=request.metadata,
        )

        # Save document
        document = await self._document_repo.save(document)

        # Create ingestion job
        job = IngestionJob(document_id=document.document_id)

        # Mark document as processing
        document.mark_processing()
        await self._document_repo.update(document)

        await logger.ainfo(
            "document_ingested",
            document_id=str(document.document_id.value),
            job_id=str(job.job_id.value),
            title=document.title,
            content_length=len(document.content),
        )

        # Enqueue background processing
        # The actual processing pipeline will be connected in Plan 3.6
        if self._process_use_case is not None:
            process = self._process_use_case
            await self._worker.enqueue(
                process.execute(document.document_id, job),  # type: ignore[attr-defined]
                task_name=f"process:{job.job_id.value}",
            )

        return IngestDocumentResponse(
            document_id=str(document.document_id.value),
            job_id=str(job.job_id.value),
            status="processing",
        )
