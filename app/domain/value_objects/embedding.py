"""Embedding vector value object."""

from __future__ import annotations

from pydantic import model_validator

from app.domain.value_objects.base import ValueObject


class EmbeddingVector(ValueObject):
    """Immutable embedding vector with model metadata.

    Attributes:
        values: The embedding values as an immutable tuple.
        model: The model name that generated this embedding.
        dimensions: The expected dimensionality of the vector.
    """

    values: tuple[float, ...]
    model: str
    dimensions: int

    @model_validator(mode="after")
    def validate_dimensions(self) -> EmbeddingVector:
        """Ensure the vector length matches the declared dimensions."""
        if len(self.values) != self.dimensions:
            msg = f"Expected {self.dimensions} dimensions, got {len(self.values)}"
            raise ValueError(msg)
        return self
