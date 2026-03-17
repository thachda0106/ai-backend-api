"""Unit tests for IngestDocumentUseCase — updated for ARQ queue.

Mocks: DocumentRepository, ArqRedis pool.
No I/O — tests pure orchestration logic.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.dto.document import IngestDocumentRequest, IngestDocumentResponse
from app.application.use_cases.ingest_document import IngestDocumentUseCase
from app.domain.entities.document import Document, DocumentStatus
from app.domain.value_objects.tenant_id import TenantId


@pytest.fixture
def tenant_id() -> TenantId:
    return TenantId()


@pytest.fixture
def document_repo() -> MagicMock:
    repo = MagicMock()

    async def _save(doc: Document) -> Document:
        return doc

    async def _update(doc: Document) -> Document:
        return doc

    async def _find_duplicate(*args: object, **kwargs: object) -> None:
        return None  # no duplicate by default

    repo.save = AsyncMock(side_effect=_save)
    repo.update = AsyncMock(side_effect=_update)
    repo.find_duplicate = AsyncMock(side_effect=_find_duplicate)
    return repo


@pytest.fixture
def arq_pool() -> MagicMock:
    """Mock ARQ Redis pool — replaces BackgroundWorker."""
    pool = MagicMock()
    mock_job = MagicMock()
    mock_job.job_id = "arq-test-job-id"
    pool.enqueue_job = AsyncMock(return_value=mock_job)
    return pool


@pytest.fixture
def use_case(document_repo: MagicMock, arq_pool: MagicMock) -> IngestDocumentUseCase:
    return IngestDocumentUseCase(
        document_repository=document_repo,
        arq_pool=arq_pool,
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
        tenant_id: TenantId,
    ) -> None:
        """execute() returns a valid IngestDocumentResponse."""
        result = await use_case.execute(ingest_request, tenant_id)

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
        tenant_id: TenantId,
    ) -> None:
        """Document is saved exactly once."""
        await use_case.execute(ingest_request, tenant_id)
        document_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_document_marked_processing(
        self,
        use_case: IngestDocumentUseCase,
        document_repo: MagicMock,
        ingest_request: IngestDocumentRequest,
        tenant_id: TenantId,
    ) -> None:
        """Document is transitioned to PROCESSING status and the update is persisted."""
        await use_case.execute(ingest_request, tenant_id)

        document_repo.update.assert_called_once()
        updated_doc: Document = document_repo.update.call_args[0][0]
        assert updated_doc.status == DocumentStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_arq_job_enqueued(
        self,
        use_case: IngestDocumentUseCase,
        arq_pool: MagicMock,
        ingest_request: IngestDocumentRequest,
        tenant_id: TenantId,
    ) -> None:
        """ARQ enqueue_job() is called with correct task name and args."""
        await use_case.execute(ingest_request, tenant_id)

        arq_pool.enqueue_job.assert_called_once()
        call_args = arq_pool.enqueue_job.call_args
        assert call_args[0][0] == "process_document_task"
        # First positional arg after task name is tenant_id
        assert call_args[0][1] == str(tenant_id)

    @pytest.mark.asyncio
    async def test_response_ids_are_strings(
        self,
        use_case: IngestDocumentUseCase,
        ingest_request: IngestDocumentRequest,
        tenant_id: TenantId,
    ) -> None:
        """document_id and job_id are returned as string UUIDs."""
        result = await use_case.execute(ingest_request, tenant_id)
        assert len(result.document_id) == 36
        assert len(result.job_id) == 36

    @pytest.mark.asyncio
    async def test_custom_collection_id_used(
        self,
        use_case: IngestDocumentUseCase,
        document_repo: MagicMock,
        ingest_request: IngestDocumentRequest,
        tenant_id: TenantId,
    ) -> None:
        """When collection_id is provided, it's applied to the document."""
        custom_id = str(uuid.uuid4())
        ingest_request.collection_id = custom_id

        await use_case.execute(ingest_request, tenant_id)

        saved_doc: Document = document_repo.save.call_args[0][0]
        assert str(saved_doc.collection_id.value) == custom_id

    @pytest.mark.asyncio
    async def test_duplicate_content_returns_existing(
        self,
        document_repo: MagicMock,
        arq_pool: MagicMock,
        ingest_request: IngestDocumentRequest,
        tenant_id: TenantId,
    ) -> None:
        """If find_duplicate() returns an existing doc, no new doc is saved."""
        from tests.conftest import make_collection_id, make_document_id
        existing_doc = Document(
            tenant_id=tenant_id,
            document_id=make_document_id(),
            collection_id=make_collection_id(),
            title="Existing",
            content=ingest_request.content,
            content_type="text/plain",
        )
        document_repo.find_duplicate = AsyncMock(return_value=existing_doc)

        use_case = IngestDocumentUseCase(
            document_repository=document_repo,
            arq_pool=arq_pool,
        )
        result = await use_case.execute(ingest_request, tenant_id)

        assert result.status == "duplicate"
        document_repo.save.assert_not_called()
        arq_pool.enqueue_job.assert_not_called()
