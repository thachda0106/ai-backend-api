"""API key authentication for FastAPI."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import SecretStr

# API key header scheme
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str, expected_key: SecretStr) -> bool:
    """Verify an API key using timing-safe comparison.

    Args:
        api_key: The API key to verify.
        expected_key: The expected API key (as SecretStr).

    Returns:
        True if the key matches, False otherwise.
    """
    return hmac.compare_digest(
        api_key.encode("utf-8"),
        expected_key.get_secret_value().encode("utf-8"),
    )


async def get_api_key(
    api_key: Annotated[str | None, Security(_api_key_header)],
) -> str:
    """FastAPI dependency to validate API key from X-API-Key header.

    Raises:
        HTTPException: 401 if key is missing, 403 if key is invalid.

    Returns:
        The validated API key string.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide X-API-Key header.",
        )

    # Import here to avoid circular imports during container wiring
    from app.core.config.settings import get_settings

    settings = get_settings()

    if not verify_api_key(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key


# Type alias for use in router dependencies
RequireAPIKey = Annotated[str, Depends(get_api_key)]
