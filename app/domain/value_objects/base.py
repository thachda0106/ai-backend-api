"""Base value object with immutability enforced."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ValueObject(BaseModel):
    """Base class for all domain value objects.

    Value objects are immutable, equality is based on all fields,
    and they are hashable (can be used as dict keys or in sets).
    """

    model_config = ConfigDict(frozen=True)
