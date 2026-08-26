"""POST /explain — live OpenAI narrative from calc trace + RAG quotes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from opt_explain_app.routers.calculate import CalculateRequest
from opt_explain_app.services import explain as explain_engine
from opt_explain_app.services import rag_index

router = APIRouter(tags=["explain"])


@router.post("/explain")
def post_explain(body: CalculateRequest) -> dict[str, Any]:
    rag_index.ensure_index()
    try:
        return explain_engine.explain(
            assessment_year=body.assessment_year,
            income=body.income.model_dump(),
            claims=[c.model_dump() for c in body.claims],
            exclude_source_doc_id=body.exclude_source_doc_id,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No RAG index for assessment_year {body.assessment_year!r}",
        ) from None
    except ValueError as exc:
        if str(exc) == "no_rate_bands":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No rate bands remain for this year after filters.",
            ) from None
        raise
    except explain_engine.ExplainError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
