"""FastAPI application factory and entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.container import Container
from app.core.config.settings import get_settings
from app.core.logging.setup import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    logger = get_logger("app.main")
    logger.info("Application starting", app_name=app.title, version=app.version)

    # Startup: initialize resources
    # Phase 2 will add: container.init_resources()
    yield

    # Shutdown: cleanup resources
    logger.info("Application shutting down")
    # Phase 2 will add: container.shutdown_resources()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    # Configure structured logging
    configure_logging(
        log_level=settings.log_level,
        debug=settings.debug,
    )

    logger = get_logger("app.main")

    # Create DI container
    container = Container()

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Production-grade AI Backend API with RAG capabilities",
        lifespan=lifespan,
    )

    # Store container on app state for access in dependencies
    app.state.container = container  # type: ignore[attr-defined]

    # Wire container to modules
    # Note: wiring is configured in Container.wiring_config
    container.wire(modules=["app.main"])

    # ──────────────────────────────────────────────
    # Health check endpoint
    # ──────────────────────────────────────────────

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "version": "0.1.0",
            "app_name": settings.app_name,
        }

    # ──────────────────────────────────────────────
    # Global exception handler
    # ──────────────────────────────────────────────

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Any,  # noqa: ARG001
        exc: Exception,
    ) -> JSONResponse:
        """Catch unhandled exceptions and return a clean error response."""
        logger.exception("Unhandled exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "code": "INTERNAL_ERROR",
            },
        )

    logger.info(
        "Application configured",
        debug=settings.debug,
        log_level=settings.log_level,
    )

    return app


# Application instance for uvicorn: `uvicorn app.main:app`
app = create_app()
