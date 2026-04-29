"""Structured logging with Loguru -- audit-friendly JSON or colored console."""

from __future__ import annotations

import sys

from loguru import logger

from backend.shared.config.settings import Settings
from backend.shared.request_context import get_request_id


def configure_logging(settings: Settings) -> None:
    """Configure Loguru sinks once per process.

    - Development (default): human-readable lines with ``request_id`` in ``extra``.
    - Audit / aggregation: set ``LOG_JSON=true`` for newline-delimited JSON (Azure Monitor,
      Datadog, ELK-friendly).

    Must run before serving traffic (call from FastAPI module import path).
    """

    logger.remove()

    def patch_record(record: dict) -> None:
        record["extra"].setdefault("request_id", get_request_id())

    logger.configure(patcher=patch_record)

    level = settings.LOG_LEVEL.upper()

    if settings.LOG_JSON:
        logger.add(sys.stderr, level=level, serialize=True)
        return

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[request_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, level=level, format=fmt)
