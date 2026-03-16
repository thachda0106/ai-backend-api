"""Shared API schemas — error responses and common models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Standardized error response returned by all error handlers."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "detail": "Document with id '123' not found",
                    "code": "ENTITY_NOT_FOUND",
                },
                {
                    "detail": "Rate limit exceeded",
                    "code": "RATE_LIMIT_EXCEEDED",
                },
            ]
        }
    )

    detail: str = Field(..., description="Human-readable error message")
    code: str = Field(..., description="Machine-readable error code (e.g., ENTITY_NOT_FOUND)")
    field: str | None = Field(default=None, description="Field name for validation errors")
