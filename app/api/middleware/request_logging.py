"""Request logging middleware.

Binds a structured logging context per request with request_id,
measures request duration, and adds X-Request-ID to responses.
Uses @app.middleware("http") pattern — NOT BaseHTTPMiddleware.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging.context import (
    RequestContext,
    bind_request_context,
    clear_request_context,
)

logger = structlog.get_logger(__name__)


async def request_logging_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Log each HTTP request with structured context.

    Binds request_id to structlog for the duration of the request,
    measures latency, and adds X-Request-ID response header.
    """
    # Skip logging for health checks
    if request.url.path == "/health":
        return await call_next(request)

    # Generate request context
    request_id = str(uuid.uuid4())
    context = RequestContext(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else None,
    )
    bind_request_context(context)

    await logger.ainfo(
        "request_started",
        method=request.method,
        path=request.url.path,
        request_id=request_id,
    )

    start_time = time.monotonic()

    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        await logger.ainfo(
            "request_completed",
            status_code=response.status_code if "response" in dir() else 500,
            duration_ms=duration_ms,
        )
        clear_request_context()

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    return response
