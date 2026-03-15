"""Search-related domain exceptions."""

from __future__ import annotations

from app.domain.exceptions.base import DomainException, EntityNotFoundException, ValidationException


class SearchException(DomainException):
    """Base exception for search-related errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="SEARCH_ERROR")


class EmptyQueryException(ValidationException):
    """Raised when a search query is empty."""

    def __init__(self) -> None:
        super().__init__(field="query", detail="Search query cannot be empty")


class CollectionNotFoundException(EntityNotFoundException):
    """Raised when a collection cannot be found."""

    def __init__(self, collection_id: str) -> None:
        super().__init__(entity_type="Collection", entity_id=collection_id)
