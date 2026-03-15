"""Document processing pipeline use case.

Runs the full ingestion pipeline:
extract → chunk → embed → store in vector database.
Tracks progress through IngestionJob FSM.
"""

from __future__ import annotations

import time

import structlog

from app.domain.entities.chunk import Chunk
from app.domain.entities.document import Document
from app.domain.entities.ingestion_job import IngestionJob, IngestionStatus
from app.domain.repositories.chunk_repository import ChunkRepository
from app.domain.repositories.document_repository import DocumentRepository
from app.domain.repositories.vector_repository import VectorRepository
from app.domain.services.chunking_service import ChunkingStrategy
from app.domain.services.token_service import TokenService
from app.domain.value_objects.identifiers import DocumentId
from app.infrastructure.llm.base import EmbeddingProvider

logger = structlog.get_logger(__name__)

_EMBEDDING_BATCH_SIZE = 50


class ProcessDocumentUseCase:
    """Pipeline use case: chunk → embed → store.

    Runs as a background task, tracking progress through
    the IngestionJob FSM stages.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        vector_repository: VectorRepository,
        embedding_provider: EmbeddingProvider,
        chunking_strategy: ChunkingStrategy,
        token_service: TokenService,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        self._document_repo = document_repository
        self._chunk_repo = chunk_repository
        self._vector_repo = vector_repository
        self._embedding_provider = embedding_provider
        self._chunking_strategy = chunking_strategy
        self._token_service = token_service
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def execute(self, document_id: DocumentId, job: IngestionJob) -> None:
        """Run the full processing pipeline.

        Args:
            document_id: The document to process.
            job: The IngestionJob tracking this pipeline run.
        """
        start_time = time.monotonic()

        try:
            # ── Stage 1: EXTRACTING ──────────────────
            job.advance_status(IngestionStatus.EXTRACTING)

            document = await self._document_repo.get_by_id(document_id)
            if document is None:
                job.fail(f"Document {document_id.value} not found")
                return

            if not document.content.strip():
                job.fail("Document content is empty")
                document.mark_failed("Document content is empty")
                await self._document_repo.update(document)
                return

            await logger.ainfo(
                "pipeline_extracting",
                document_id=str(document_id.value),
                content_length=len(document.content),
            )

            # ── Stage 2: CHUNKING ────────────────────
            job.advance_status(IngestionStatus.CHUNKING)

            chunk_data_list = self._chunking_strategy.chunk(
                content=document.content,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )

            chunks = [
                Chunk(
                    document_id=document.document_id,
                    collection_id=document.collection_id,
                    content=cd.content,
                    chunk_index=cd.chunk_index,
                    start_char=cd.start_char,
                    end_char=cd.end_char,
                    token_count=self._token_service.count_tokens(cd.content, "gpt-4o"),
                )
                for cd in chunk_data_list
            ]

            chunks = await self._chunk_repo.save_many(chunks)
            job.record_progress(0, len(chunks))

            await logger.ainfo(
                "pipeline_chunked",
                document_id=str(document_id.value),
                chunk_count=len(chunks),
            )

            # ── Stage 3: EMBEDDING ───────────────────
            job.advance_status(IngestionStatus.EMBEDDING)

            total_tokens = 0
            for batch_start in range(0, len(chunks), _EMBEDDING_BATCH_SIZE):
                batch = chunks[batch_start : batch_start + _EMBEDDING_BATCH_SIZE]
                texts = [c.content for c in batch]

                embeddings = await self._embedding_provider.embed_batch(texts)

                for chunk, embedding in zip(batch, embeddings, strict=True):
                    chunk.set_embedding(embedding)

                processed = min(batch_start + len(batch), len(chunks))
                job.record_progress(processed, len(chunks))
                total_tokens += sum(c.token_count for c in batch)

            await logger.ainfo(
                "pipeline_embedded",
                document_id=str(document_id.value),
                chunks_embedded=len(chunks),
                total_tokens=total_tokens,
            )

            # ── Stage 4: STORING ─────────────────────
            job.advance_status(IngestionStatus.STORING)

            entries = [
                (
                    chunk.chunk_id,
                    chunk.embedding,
                    {
                        "document_id": str(chunk.document_id.value),
                        "collection_id": str(chunk.collection_id.value),
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                        "document_title": document.title,
                    },
                )
                for chunk in chunks
                if chunk.embedding is not None
            ]

            await self._vector_repo.upsert_many(entries)

            await logger.ainfo(
                "pipeline_stored",
                document_id=str(document_id.value),
                vectors_stored=len(entries),
            )

            # ── Stage 5: COMPLETED ───────────────────
            job.complete()
            document.mark_completed(
                chunk_count=len(chunks),
                token_count=total_tokens,
            )
            await self._document_repo.update(document)

            elapsed = time.monotonic() - start_time
            await logger.ainfo(
                "pipeline_completed",
                document_id=str(document_id.value),
                chunk_count=len(chunks),
                total_tokens=total_tokens,
                elapsed_seconds=round(elapsed, 3),
            )

        except Exception as exc:
            elapsed = time.monotonic() - start_time
            error_msg = f"Pipeline failed: {exc}"

            job.fail(error_msg)

            # Try to update document status
            try:
                doc = await self._document_repo.get_by_id(document_id)
                if doc is not None:
                    doc.mark_failed(error_msg)
                    await self._document_repo.update(doc)
            except Exception:
                pass  # Don't mask the original error

            await logger.aerror(
                "pipeline_failed",
                document_id=str(document_id.value),
                error=str(exc),
                elapsed_seconds=round(elapsed, 3),
            )
