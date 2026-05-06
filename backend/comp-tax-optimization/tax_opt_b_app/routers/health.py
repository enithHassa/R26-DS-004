"""Liveness and readiness probes (no database dependency for Function 1)."""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from tax_opt_b_app import __version__

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
def live() -> dict[str, str]:
    return {"status": "ok", "component": "tax-optimization", "version": __version__}


@router.get("/ready", status_code=status.HTTP_200_OK)
def ready(request: Request) -> dict[str, object]:
    rules_ok = hasattr(request.app.state, "tax_opt_b_rules") and request.app.state.tax_opt_b_rules is not None
    return {
        "status": "ok" if rules_ok else "degraded",
        "checks": {"rules_loaded": rules_ok},
    }
