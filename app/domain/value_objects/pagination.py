"""Pagination value object."""

from __future__ import annotations

from pydantic import Field

from app.domain.value_objects.base import ValueObject


class PaginationParams(ValueObject):
    """Immutable pagination parameters with validation.

    Attributes:
        offset: Number of items to skip (>= 0).
        limit: Maximum number of items to return (1-100).
    """

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=100)
