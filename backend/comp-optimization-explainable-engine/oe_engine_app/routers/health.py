"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from oe_engine_app import __version__
from oe_engine_app.deps import get_session
from oe_engine_app.services.chunk_coverage import ready_checks

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def live() -> dict[str, Any]:
    return {
        "status": "ok",
        "component": "optimization-explainable-engine",
        "version": __version__,
        "phase": "7",
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready() -> dict[str, object]:
    session = None
    try:
        session = get_session()
        checks = ready_checks(session)
    except Exception:  # noqa: BLE001
        checks = {
            "api_bootstrap": True,
            "rag_index": False,
            "chunk_coverage": True,
            "chunk_count": 0,
            "promoted_doc_count": 0,
            "promoted_without_chunks": [],
        }
    finally:
        if session is not None:
            session.close()
    degraded = (not checks.get("api_bootstrap")) or (checks.get("chunk_coverage") is False)
    return {"status": "degraded" if degraded else "ok", "checks": checks}
