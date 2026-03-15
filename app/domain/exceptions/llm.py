"""LLM-related domain exceptions."""

from __future__ import annotations

from app.domain.exceptions.base import DomainException


class LLMException(DomainException):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, code: str = "LLM_ERROR") -> None:
        super().__init__(message=message, code=code)


class LLMConnectionException(LLMException):
    """Raised when the LLM service is unreachable."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"LLM connection failed: {detail}",
            code="LLM_CONNECTION_ERROR",
        )


class LLMRateLimitException(LLMException):
    """Raised when the LLM API rate limit is exceeded."""

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "LLM rate limit exceeded"
        if retry_after is not None:
            msg += f", retry after {retry_after}s"
        super().__init__(message=msg, code="LLM_RATE_LIMIT")


class TokenLimitExceededException(LLMException):
    """Raised when the token limit for a request is exceeded."""

    def __init__(self, token_count: int, max_tokens: int) -> None:
        self.token_count = token_count
        self.max_tokens = max_tokens
        super().__init__(
            message=f"Token limit exceeded: {token_count} > {max_tokens}",
            code="TOKEN_LIMIT_EXCEEDED",
        )


class EmbeddingException(LLMException):
    """Raised when embedding generation fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            message=f"Embedding generation failed: {detail}",
            code="EMBEDDING_ERROR",
        )
