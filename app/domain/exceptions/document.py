"""Document-related domain exceptions."""

from __future__ import annotations

from app.domain.exceptions.base import DomainException, EntityNotFoundException, ValidationException


class DocumentNotFoundException(EntityNotFoundException):
    """Raised when a document cannot be found."""

    def __init__(self, document_id: str) -> None:
        super().__init__(entity_type="Document", entity_id=document_id)


class DocumentAlreadyExistsException(DomainException):
    """Raised when trying to create a document that already exists."""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            message=f"Document '{document_id}' already exists",
            code="DOCUMENT_ALREADY_EXISTS",
        )


class InvalidDocumentContentException(ValidationException):
    """Raised when document content is invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(field="content", detail=detail)


class ChunkingException(DomainException):
    """Raised when document chunking fails."""

    def __init__(self, document_id: str, detail: str) -> None:
        self.document_id = document_id
        super().__init__(
            message=f"Chunking failed for document '{document_id}': {detail}",
            code="CHUNKING_ERROR",
        )
