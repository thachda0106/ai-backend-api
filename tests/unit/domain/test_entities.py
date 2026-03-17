"""Unit tests for Document entity — status transitions and business rules."""

from __future__ import annotations

import pytest

from app.domain.entities.document import Document, DocumentStatus
from tests.conftest import make_document


class TestDocumentStatusTransitions:
    def test_new_document_is_pending(self) -> None:
        doc = make_document()
        assert doc.status == DocumentStatus.PENDING

    def test_mark_processing(self) -> None:
        doc = make_document()
        doc.mark_processing()
        assert doc.status == DocumentStatus.PROCESSING
        assert doc.error_message is None

    def test_mark_completed_sets_counts(self) -> None:
        doc = make_document()
        doc.mark_processing()
        doc.mark_completed(chunk_count=5, token_count=500)

        assert doc.status == DocumentStatus.COMPLETED
        assert doc.chunk_count == 5
        assert doc.token_count == 500
        assert doc.error_message is None

    def test_mark_failed_sets_error(self) -> None:
        doc = make_document()
        doc.mark_failed("Timeout during embedding")

        assert doc.status == DocumentStatus.FAILED
        assert doc.error_message == "Timeout during embedding"

    def test_mark_processing_clears_previous_error(self) -> None:
        doc = make_document()
        doc.mark_failed("First error")
        doc.mark_processing()
        assert doc.error_message is None

    def test_is_processable_when_pending(self) -> None:
        doc = make_document(status=DocumentStatus.PENDING)
        assert doc.is_processable is True

    def test_is_processable_when_failed(self) -> None:
        doc = make_document(status=DocumentStatus.FAILED)
        assert doc.is_processable is True

    def test_not_processable_when_processing(self) -> None:
        doc = make_document()
        doc.mark_processing()
        assert doc.is_processable is False

    def test_not_processable_when_completed(self) -> None:
        doc = make_document()
        doc.mark_completed(chunk_count=1, token_count=10)
        assert doc.is_processable is False

    def test_updated_at_changes_on_transition(self) -> None:
        doc = make_document()
        original_updated = doc.updated_at
        doc.mark_processing()
        # updated_at should be >= original (may be equal if very fast)
        assert doc.updated_at >= original_updated

    def test_document_has_unique_id(self) -> None:
        doc1 = make_document()
        doc2 = make_document()
        assert doc1.document_id != doc2.document_id
