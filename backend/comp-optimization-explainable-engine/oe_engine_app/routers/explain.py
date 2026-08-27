"""POST /explain — calc trace + retrieve over Phase 2 chunks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from oe_engine_app.deps import get_session
from oe_engine_app.routers.calculate import CalculateRequest
from oe_engine_app.services import explain as explain_engine

router = APIRouter(tags=["explain"])


@router.post("/explain")
def post_explain(body: CalculateRequest) -> dict[str, Any]:
    session = get_session()
    try:
        return explain_engine.explain(
            session,
            assessment_year=body.assessment_year,
            income=body.income.model_dump(),
            claims=[c.model_dump() for c in body.claims],
            exclude_source_doc_id=body.exclude_source_doc_id,
            wht_already_paid=body.wht_already_paid or body.income.wht_already_paid,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No year view for assessment_year {body.assessment_year!r}",
        ) from None
    except ValueError as exc:
        if str(exc) == "no_rate_bands":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No rate bands remain for this year after filters.",
            ) from None
        raise
    finally:
        session.close()
