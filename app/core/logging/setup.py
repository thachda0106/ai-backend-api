"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO", debug: bool = False) -> None:
    """Configure structured logging for the application.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        debug: If True, use console renderer for human-readable output.
               If False, use JSON renderer for production.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        # Human-readable console output for development
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        # JSON output for production (machine-parseable)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Silence noisy third-party loggers
    for logger_name in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str | None = None, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Get a bound structlog logger.

    Args:
        name: Logger name (typically __name__).
        **initial_values: Initial context values to bind to the logger.

    Returns:
        A bound structlog logger instance.
    """
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name, **initial_values)
    return logger
