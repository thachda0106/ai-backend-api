"""Shared pytest fixtures and test utilities."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.entities.document import Document, DocumentStatus
from app.domain.entities.ingestion_job import IngestionJob
from app.domain.value_objects.identifiers import CollectionId, DocumentId


# ── Domain Builders ────────────────────────────────────────────────────────────


def make_collection_id() -> CollectionId:
    return CollectionId(value=uuid.uuid4())


def make_document_id() -> DocumentId:
    return DocumentId(value=uuid.uuid4())


def make_document(
    *,
    title: str = "Test Document",
    content: str = "This is test content for the document.",
    collection_id: CollectionId | None = None,
    status: DocumentStatus = DocumentStatus.PENDING,
) -> Document:
    """Build a Document entity with sensible defaults."""
    return Document(
        document_id=make_document_id(),
        collection_id=collection_id or make_collection_id(),
        title=title,
        content=content,
        status=status,
    )


# ── Mock Repositories ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_document_repo() -> MagicMock:
    """Mock DocumentRepository with async save/get methods."""
    repo = MagicMock()
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_vector_repo() -> MagicMock:
    """Mock VectorRepository with async search/upsert methods."""
    repo = MagicMock()
    repo.upsert = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_background_worker() -> MagicMock:
    """Mock BackgroundWorker."""
    worker = MagicMock()
    worker.enqueue = AsyncMock()
    return worker


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    """Mock EmbeddingProvider that returns a fixed 1536-dim vector."""
    provider = MagicMock()
    provider.embed = AsyncMock(return_value=[0.1] * 1536)
    return provider


@pytest.fixture
def mock_chat_provider() -> MagicMock:
    """Mock ChatProvider for non-streaming and streaming responses."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value="This is a test response.")
    provider.stream = AsyncMock()
    return provider


@pytest.fixture
def mock_token_service() -> MagicMock:
    """Mock TokenService that returns a fixed count."""
    svc = MagicMock()
    svc.count_tokens = MagicMock(return_value=10)
    svc.count_messages_tokens = MagicMock(return_value=20)
    return svc


@pytest.fixture
def sample_document() -> Document:
    """A valid Document entity ready for testing."""
    return make_document()
