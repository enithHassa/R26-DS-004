"""Admin param override endpoints (Phase 4 viva adaptivity)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from adaptive_tax_app.schemas.params import ParamResetResponse
from adaptive_tax_app.services.param_store import (
    read_param_override,
    seed_pre_amend_override,
)

router = APIRouter(prefix="/admin/params", tags=["admin-params"])


@router.post(
    "/reset-to-pre-amend",
    response_model=ParamResetResponse,
    summary="Seed pre-amend Sec 52 cap (1.2M) into runtime override for viva T1",
)
def reset_to_pre_amend() -> ParamResetResponse:
    """Copy ontology ``pre_amend_2025`` QP cap into the active override file."""
    try:
        result = seed_pre_amend_override()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"failed to write param override: {exc}",
        ) from exc

    return ParamResetResponse(
        ok=True,
        override_path=str(result.path),
        concept_id=result.concept_id,
        qualifying_payment_cap=format(result.cap_amount, "f"),
        override=read_param_override(),
    )
