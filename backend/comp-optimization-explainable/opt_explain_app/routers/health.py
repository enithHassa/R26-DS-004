"""Liveness and readiness probes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from opt_explain_app import __version__

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def live() -> dict[str, Any]:
    return {
        "status": "ok",
        "component": "optimization-explainable",
        "version": __version__,
        "phase": "8",
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready() -> dict[str, object]:
    checks = {"api_bootstrap": True, "rag_index": True}
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
