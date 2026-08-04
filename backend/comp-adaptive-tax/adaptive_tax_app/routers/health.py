"""Liveness and readiness probes for Adaptive Tax component."""

from __future__ import annotations

from fastapi import APIRouter, status

from adaptive_tax_app import __version__

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def live() -> dict[str, str]:
    return {"status": "ok", "component": "adaptive-tax", "version": __version__}


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready() -> dict[str, object]:
    checks = {"api_bootstrap": True}
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
