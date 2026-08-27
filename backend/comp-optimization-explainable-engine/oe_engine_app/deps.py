"""Session factory — tests monkeypatch SessionLocal here."""

from __future__ import annotations

from backend.shared.config.database import SessionLocal as _SessionLocal

SessionLocal = _SessionLocal


def get_session():
    return SessionLocal()

