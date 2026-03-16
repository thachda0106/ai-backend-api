"""Rate limiting middleware.

Enforces per-key rate limits using the existing RedisRateLimiter.
Returns 429 with ErrorResponse when limit exceeded.
Uses @app.middleware("http") pattern — NOT BaseHTTPMiddleware.
"""

from __future__ import annotations

import structlog
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.api.schemas.common import ErrorResponse
from app.infrastructure.cache.rate_limiter import RedisRateLimiter

logger = structlog.get_logger(__name__)


def create_rate_limit_middleware(
    rate_limiter: RedisRateLimiter,
) -> ...:
    """Create a rate limit middleware function closed over the rate limiter.

    Args:
        rate_limiter: The Redis-backed rate limiter instance.

    Returns:
        Middleware function for use with @app.middleware("http").
    """

    async def rate_limit_middleware(
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Enforce rate limits per API key or client IP."""
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        # Extract rate limit key: API key or client IP
        rate_key = request.headers.get("X-API-Key") or (
            request.client.host if request.client else "unknown"
        )

        try:
            allowed = await rate_limiter.is_allowed(rate_key)
        except Exception:
            # If Redis is down, allow the request (graceful degradation)
            await logger.awarning("rate_limiter_unavailable", key=rate_key)
            return await call_next(request)

        if not allowed:
            error = ErrorResponse(
                detail="Rate limit exceeded. Please try again later.",
                code="RATE_LIMIT_EXCEEDED",
            )
            return JSONResponse(
                status_code=429,
                content=error.model_dump(),
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)

        # Add rate limit info headers
        try:
            remaining = await rate_limiter.get_remaining(rate_key)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Limit"] = str(rate_limiter._requests_per_minute)
        except Exception:
            pass  # Don't fail request if header computation fails

        return response

    return rate_limit_middleware
