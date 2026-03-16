"""Exception handler registration.

Maps domain exceptions to HTTP status codes and returns
consistent ErrorResponse JSON for all error cases.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.schemas.common import ErrorResponse
from app.domain.exceptions.base import (
    BusinessRuleViolation,
    DomainException,
    EntityNotFoundException,
    ValidationException,
)
from app.domain.exceptions.llm import (
    LLMConnectionException,
    LLMRateLimitException,
    TokenLimitExceededException,
)

logger = structlog.get_logger(__name__)


def _error_response(status_code: int, detail: str, code: str, **kwargs: Any) -> JSONResponse:
    """Build a JSON error response using ErrorResponse schema."""
    error = ErrorResponse(detail=detail, code=code, **kwargs)
    return JSONResponse(status_code=status_code, content=error.model_dump(exclude_none=True))


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI application.

    Maps domain exceptions to appropriate HTTP status codes.
    All responses use the ErrorResponse schema for consistency.
    """

    @app.exception_handler(EntityNotFoundException)
    async def entity_not_found_handler(
        request: Request,  # noqa: ARG001
        exc: EntityNotFoundException,
    ) -> JSONResponse:
        await logger.awarning("entity_not_found", entity_type=exc.entity_type, entity_id=exc.entity_id)
        return _error_response(404, exc.message, exc.code)

    @app.exception_handler(ValidationException)
    async def validation_exception_handler(
        request: Request,  # noqa: ARG001
        exc: ValidationException,
    ) -> JSONResponse:
        await logger.awarning("validation_error", field=exc.field, detail=exc.detail)
        return _error_response(422, exc.message, exc.code, field=exc.field)

    @app.exception_handler(BusinessRuleViolation)
    async def business_rule_handler(
        request: Request,  # noqa: ARG001
        exc: BusinessRuleViolation,
    ) -> JSONResponse:
        await logger.awarning("business_rule_violation", rule=exc.rule)
        return _error_response(409, exc.message, exc.code)

    @app.exception_handler(LLMRateLimitException)
    async def llm_rate_limit_handler(
        request: Request,  # noqa: ARG001
        exc: LLMRateLimitException,
    ) -> JSONResponse:
        await logger.awarning("llm_rate_limit", retry_after=exc.retry_after)
        response = _error_response(429, exc.message, exc.code)
        if exc.retry_after is not None:
            response.headers["Retry-After"] = str(int(exc.retry_after))
        return response

    @app.exception_handler(LLMConnectionException)
    async def llm_connection_handler(
        request: Request,  # noqa: ARG001
        exc: LLMConnectionException,
    ) -> JSONResponse:
        await logger.aerror("llm_connection_error", error=str(exc))
        return _error_response(502, exc.message, exc.code)

    @app.exception_handler(TokenLimitExceededException)
    async def token_limit_handler(
        request: Request,  # noqa: ARG001
        exc: TokenLimitExceededException,
    ) -> JSONResponse:
        await logger.awarning(
            "token_limit_exceeded", token_count=exc.token_count, max_tokens=exc.max_tokens
        )
        return _error_response(413, exc.message, exc.code)

    @app.exception_handler(DomainException)
    async def domain_exception_handler(
        request: Request,  # noqa: ARG001
        exc: DomainException,
    ) -> JSONResponse:
        """Catch-all for any DomainException not handled above."""
        await logger.awarning("domain_error", code=exc.code, message=exc.message)
        return _error_response(400, exc.message, exc.code)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request,  # noqa: ARG001
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle Pydantic request validation errors."""
        errors = exc.errors()
        first_error = errors[0] if errors else {"msg": "Validation error"}
        field = " → ".join(str(loc) for loc in first_error.get("loc", []))
        detail = first_error.get("msg", "Validation error")
        await logger.awarning("request_validation_error", field=field, detail=detail)
        return _error_response(422, f"{field}: {detail}" if field else detail, "VALIDATION_ERROR", field=field)

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,  # noqa: ARG001
        exc: Exception,
    ) -> JSONResponse:
        """Catch-all for unhandled exceptions — never leak internals."""
        await logger.aexception("unhandled_exception", error=str(exc))
        return _error_response(500, "Internal server error", "INTERNAL_ERROR")
