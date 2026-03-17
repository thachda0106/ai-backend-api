"""Document ingestion use case — CRIT-3 Fix.

Saves the document, creates an ingestion job, then enqueues
processing via ARQ (Redis-backed, survives restarts, multi-worker).
"""

from __future__ import annotations

import structlog
from arq import ArqRedis

from app.application.dto.document import IngestDocumentRequest, IngestDocumentResponse
from app.domain.entities.document import Document
from app.domain.entities.ingestion_job import IngestionJob
from app.domain.repositories.document_repository import DocumentRepository
from app.domain.value_objects.identifiers import CollectionId
from app.domain.value_objects.tenant_id import TenantId

logger = structlog.get_logger(__name__)


class IngestDocumentUseCase:
    """Ingest a document into the RAG system.

    Saves the document, creates an ingestion tracking job,
    then enqueues the full processing pipeline via ARQ so
    that any worker replica can pick it up — even after a restart.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        arq_pool: ArqRedis,
    ) -> None:
        self._document_repo = document_repository
        self._arq = arq_pool

    async def execute(
        self,
        request: IngestDocumentRequest,
        tenant_id: TenantId,
    ) -> IngestDocumentResponse:
        """Ingest a document and enqueue background processing.

        Args:
            request:   Document ingestion request DTO.
            tenant_id: The owning tenant (resolved from API key).

        Returns:
            IngestDocumentResponse with document_id, job_id, and status.
        """
        # 1. Build collection id
        collection_id = (
            CollectionId.from_str(request.collection_id)
            if request.collection_id
            else CollectionId()
        )

        # 2. Content deduplication — check for existing identical document
        if hasattr(self._document_repo, "find_duplicate"):
            existing = await self._document_repo.find_duplicate(  # type: ignore[attr-defined]
                tenant_id, request.content
            )
            if existing is not None:
                await logger.ainfo(
                    "document_duplicate_detected",
                    tenant_id=str(tenant_id),
                    existing_document_id=str(existing.document_id.value),
                )
                return IngestDocumentResponse(
                    document_id=str(existing.document_id.value),
                    job_id="duplicate",
                    status="duplicate",
                )

        # 3. Create and persist document
        document = Document(
            tenant_id=tenant_id,
            collection_id=collection_id,
            title=request.title,
            content=request.content,
            content_type=request.content_type,
            metadata=request.metadata,
        )
        document = await self._document_repo.save(document)

        # 4. Create ingestion job tracker
        job = IngestionJob(document_id=document.document_id)

        # 5. Transition document to PROCESSING
        document.mark_processing()
        await self._document_repo.update(document)

        # 6. Enqueue processing via ARQ — survives restarts, multi-worker safe
        arq_job = await self._arq.enqueue_job(
            "process_document_task",
            str(tenant_id),
            str(document.document_id.value),
            str(job.job_id.value),
        )

        arq_job_id = arq_job.job_id if arq_job else "unknown"

        await logger.ainfo(
            "document_ingested",
            tenant_id=str(tenant_id),
            document_id=str(document.document_id.value),
            job_id=str(job.job_id.value),
            arq_job_id=arq_job_id,
            title=document.title,
            content_length=len(document.content),
        )

        return IngestDocumentResponse(
            document_id=str(document.document_id.value),
            job_id=str(job.job_id.value),
            status="processing",
        )
