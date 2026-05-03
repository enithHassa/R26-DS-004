"""Liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import text

from app import __version__
from backend.shared.config.database import engine

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def live() -> dict[str, str]:
    return {"status": "ok", "component": "personalized-recommendation", "version": __version__}


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready() -> dict[str, object]:
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "checks": {"database": db_ok},
    }
