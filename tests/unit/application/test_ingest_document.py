"""Unit tests for IngestDocumentUseCase.

Mocks: DocumentRepository, BackgroundWorker.
No I/O — tests pure orchestration logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.application.dto.document import IngestDocumentRequest, IngestDocumentResponse
from app.application.use_cases.ingest_document import IngestDocumentUseCase
from app.domain.entities.document import Document, DocumentStatus
from tests.conftest import make_document


@pytest.fixture
def document_repo() -> MagicMock:
    repo = MagicMock()
    # save() returns the same document it received
    async def _save(doc: Document) -> Document:
        return doc

    async def _update(doc: Document) -> Document:
        return doc

    repo.save = AsyncMock(side_effect=_save)
    repo.update = AsyncMock(side_effect=_update)
    return repo


@pytest.fixture
def background_worker() -> MagicMock:
    worker = MagicMock()
    worker.enqueue = AsyncMock()
    return worker


@pytest.fixture
def use_case(document_repo: MagicMock, background_worker: MagicMock) -> IngestDocumentUseCase:
    return IngestDocumentUseCase(
        document_repository=document_repo,
        background_worker=background_worker,
    )


@pytest.fixture
def ingest_request() -> IngestDocumentRequest:
    return IngestDocumentRequest(
        title="Test Document",
        content="This is the content of the test document.",
        content_type="text/plain",
        metadata={"source": "unit-test"},
    )


class TestIngestDocumentUseCase:
    @pytest.mark.asyncio
    async def test_returns_ingest_response(
        self,
        use_case: IngestDocumentUseCase,
        ingest_request: IngestDocumentRequest,
    ) -> None:
        """execute() returns a valid IngestDocumentResponse."""
        result = await use_case.execute(ingest_request)

        assert isinstance(result, IngestDocumentResponse)
        assert result.status == "processing"
        assert result.document_id is not None
        assert result.job_id is not None

    @pytest.mark.asyncio
    async def test_saves_document_once(
        self,
        use_case: IngestDocumentUseCase,
        document_repo: MagicMock,
        ingest_request: IngestDocumentRequest,
    ) -> None:
        """Document is saved exactly once."""
        await use_case.execute(ingest_request)
        document_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_document_marked_processing(
        self,
        use_case: IngestDocumentUseCase,
        document_repo: MagicMock,
        ingest_request: IngestDocumentRequest,
    ) -> None:
        """Document is transitioned to PROCESSING status and the update is persisted."""
        await use_case.execute(ingest_request)

        # update() is called after mark_processing()
        document_repo.update.assert_called_once()
        updated_doc: Document = document_repo.update.call_args[0][0]
        assert updated_doc.status == DocumentStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_no_background_enqueue_without_process_use_case(
        self,
        use_case: IngestDocumentUseCase,
        background_worker: MagicMock,
        ingest_request: IngestDocumentRequest,
    ) -> None:
        """Without a process_use_case wired, background_worker.enqueue is NOT called."""
        await use_case.execute(ingest_request)
        background_worker.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_response_ids_are_strings(
        self,
        use_case: IngestDocumentUseCase,
        ingest_request: IngestDocumentRequest,
    ) -> None:
        """document_id and job_id are returned as string UUIDs."""
        result = await use_case.execute(ingest_request)
        # Should be valid UUID strings (36 chars with dashes)
        assert len(result.document_id) == 36
        assert len(result.job_id) == 36

    @pytest.mark.asyncio
    async def test_custom_collection_id_used(
        self,
        use_case: IngestDocumentUseCase,
        document_repo: MagicMock,
        ingest_request: IngestDocumentRequest,
    ) -> None:
        """When collection_id is provided, it's applied to the document."""
        import uuid
        custom_id = str(uuid.uuid4())
        ingest_request.collection_id = custom_id

        await use_case.execute(ingest_request)

        saved_doc: Document = document_repo.save.call_args[0][0]
        assert str(saved_doc.collection_id.value) == custom_id
