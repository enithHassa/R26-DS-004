"""Reusable FastAPI dependencies (DB session, auth stubs)."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.shared.config.database import get_db as _get_db


def get_db() -> Generator[Session, None, None]:
    """Re-export of the shared DB dependency so routers don't reach into shared.*."""
    yield from _get_db()


DBSession = Depends(get_db)

__all__ = ["DBSession", "get_db"]
