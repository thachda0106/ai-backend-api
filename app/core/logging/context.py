"""Request context management for structured logging."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import structlog


@dataclass(frozen=True)
class RequestContext:
    """Immutable context for a single HTTP request."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    method: str = ""
    path: str = ""
    user_id: str | None = None
    client_ip: str | None = None


def bind_request_context(context: RequestContext) -> None:
    """Bind request context variables to structlog for the current async context.

    This uses structlog's contextvars integration, so the bound values
    will be automatically included in all log messages within the same
    async context (request scope).

    Args:
        context: The request context to bind.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=context.request_id,
        method=context.method,
        path=context.path,
        user_id=context.user_id,
        client_ip=context.client_ip,
    )


def clear_request_context() -> None:
    """Clear the request context after request completion."""
    structlog.contextvars.clear_contextvars()


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())
