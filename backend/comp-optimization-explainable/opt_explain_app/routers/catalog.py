"""GET /years, /acts/{ya}, /reliefs/{ya}, POST /index/refresh."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from opt_explain_app.services import compare as compare_service
from opt_explain_app.services import rag_index

router = APIRouter(tags=["catalog"])


def _unknown_year(assessment_year: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No RAG index for assessment_year {assessment_year!r}",
    )


@router.get("/years")
def get_years() -> dict[str, Any]:
    years = rag_index.list_years()
    return {
        "assessment_years": [row["assessment_year"] for row in years],
        "years": years,
        "year_count": len(years),
    }


@router.get("/acts/{assessment_year}")
def get_acts(assessment_year: str) -> dict[str, Any]:
    acts = rag_index.acts_for_year(assessment_year)
    if acts is None:
        raise _unknown_year(assessment_year)
    return {
        "assessment_year": assessment_year,
        "acts": acts,
        "act_count": len(acts),
    }


@router.get("/reliefs/{assessment_year}")
def get_reliefs(
    assessment_year: str,
    exclude_source_doc_id: str | None = Query(default=None),
) -> dict[str, Any]:
    docs = rag_index.reliefs_for_year(assessment_year, exclude_source_doc_id)
    if docs is None:
        raise _unknown_year(assessment_year)
    return {
        "assessment_year": assessment_year,
        "exclude_source_doc_id": (exclude_source_doc_id or "").strip() or None,
        "entries": docs,
        "entry_count": len(docs),
    }


@router.get("/rates/{assessment_year}")
def get_rates(
    assessment_year: str,
    exclude_source_doc_id: str | None = Query(default=None),
) -> dict[str, Any]:
    docs = rag_index.rates_for_year(assessment_year, exclude_source_doc_id)
    if docs is None:
        raise _unknown_year(assessment_year)
    return {
        "assessment_year": assessment_year,
        "exclude_source_doc_id": (exclude_source_doc_id or "").strip() or None,
        "bands": docs,
        "band_count": len(docs),
    }


@router.get("/compare")
def get_compare(
    exclude_source_doc_id: str | None = Query(default=None),
    compare_group_id: str | None = Query(default=None),
) -> dict[str, Any]:
    """Cross-year relief caps from the RAG index (updates when new acts are promoted)."""
    payload = compare_service.compare_reliefs(
        exclude_source_doc_id=exclude_source_doc_id,
        compare_group_id=compare_group_id,
    )
    if not payload["assessment_years"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RAG index has no assessment years — run POST /index/refresh",
        )
    return payload


@router.post("/index/refresh")
def post_index_refresh() -> dict[str, Any]:
    result = rag_index.refresh_index()
    result["status"] = "ok"
    return result
