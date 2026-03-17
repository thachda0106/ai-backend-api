"""Unit tests for domain identifier value objects."""

from __future__ import annotations

import uuid

import pytest

from app.domain.value_objects.identifiers import (
    ChunkId,
    CollectionId,
    DocumentId,
    IngestionJobId,
    UserId,
)


class TestDocumentId:
    def test_generates_unique_id_by_default(self) -> None:
        id1 = DocumentId()
        id2 = DocumentId()
        assert id1 != id2

    def test_equality_by_value(self) -> None:
        fixed = uuid.UUID("12345678-1234-5678-1234-567812345678")
        assert DocumentId(value=fixed) == DocumentId(value=fixed)

    def test_str_returns_uuid_string(self) -> None:
        fixed = uuid.UUID("12345678-1234-5678-1234-567812345678")
        doc_id = DocumentId(value=fixed)
        assert str(doc_id) == "12345678-1234-5678-1234-567812345678"

    def test_from_str_roundtrip(self) -> None:
        raw = str(uuid.uuid4())
        doc_id = DocumentId.from_str(raw)
        assert str(doc_id) == raw

    def test_from_str_invalid_raises(self) -> None:
        with pytest.raises(Exception):
            DocumentId.from_str("not-a-uuid")

    def test_is_immutable(self) -> None:
        doc_id = DocumentId()
        with pytest.raises(Exception):
            doc_id.value = uuid.uuid4()  # type: ignore[misc]


class TestCollectionId:
    def test_generates_unique_id_by_default(self) -> None:
        id1 = CollectionId()
        id2 = CollectionId()
        assert id1 != id2

    def test_from_str_roundtrip(self) -> None:
        raw = str(uuid.uuid4())
        col_id = CollectionId.from_str(raw)
        assert str(col_id) == raw


class TestChunkId:
    def test_from_str_roundtrip(self) -> None:
        raw = str(uuid.uuid4())
        chunk_id = ChunkId.from_str(raw)
        assert str(chunk_id) == raw


class TestIngestionJobId:
    def test_auto_generates_uuid(self) -> None:
        job_id = IngestionJobId()
        assert isinstance(job_id.value, uuid.UUID)


class TestUserId:
    def test_equality(self) -> None:
        fixed = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        assert UserId(value=fixed) == UserId(value=fixed)

    def test_inequality(self) -> None:
        assert UserId() != UserId()
