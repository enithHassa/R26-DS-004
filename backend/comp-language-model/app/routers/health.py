"""Liveness and readiness probes for language-model component."""

from __future__ import annotations

from fastapi import APIRouter, status

from app import __version__

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def live() -> dict[str, str]:
    return {"status": "ok", "component": "language-model", "version": __version__}


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready() -> dict[str, object]:
    checks = {"api_bootstrap": True}
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
