"""
app/utils/logger.py
───────────────────
Structured JSON logging via structlog.

Why structlog?
  • Machine-parseable JSON: compatible with Datadog, CloudWatch, Loki, etc.
  • Context binding: add request_id, user_id, etc. without touching every call.
  • Zero overhead in production if level is WARNING+.

Usage:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Event name", key=value, ...)
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    """Call once at startup."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer()
            if settings.ENV == "development"
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so uvicorn/httpx logs are captured
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stdout,
    )


configure_logging()


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
