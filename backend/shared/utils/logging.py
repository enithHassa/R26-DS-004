"""Centralized loguru configuration for all backend services.

Import :func:`configure_logging` once at application startup (e.g. in the
FastAPI lifespan) to route stdlib logging, uvicorn, and SQLAlchemy logs
through loguru, and to install JSON-ish formatting in production.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from loguru import logger

from backend.shared.config.settings import settings

_CONFIGURED = False


class _InterceptHandler(logging.Handler):
    """Redirect stdlib logging records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging(service_name: str = "tax-advisory", **extra: Any) -> None:
    """Initialise loguru + stdlib logging interception.

    Safe to call multiple times; only the first call applies the config.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger.remove()

    is_dev = settings.APP_ENV != "production"
    level = settings.LOG_LEVEL.upper()

    if is_dev:
        fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
            "<level>{level: <8}</level> "
            "<cyan>{extra[service]}</cyan> "
            "<magenta>{name}:{function}:{line}</magenta> - "
            "<level>{message}</level>"
        )
    else:
        fmt = (
            '{{"ts":"{time:YYYY-MM-DDTHH:mm:ss.SSSZ}",'
            '"level":"{level}","service":"{extra[service]}",'
            '"logger":"{name}","message":"{message}"}}'
        )

    logger.configure(extra={"service": service_name, **extra})
    logger.add(
        sys.stdout,
        level=level,
        format=fmt,
        backtrace=is_dev,
        diagnose=is_dev,
        enqueue=False,
    )

    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        stdlib = logging.getLogger(noisy)
        stdlib.handlers = [_InterceptHandler()]
        stdlib.propagate = False

    _CONFIGURED = True
    logger.info("Logging configured (env={}, level={})", settings.APP_ENV, level)


__all__ = ["configure_logging", "logger"]
