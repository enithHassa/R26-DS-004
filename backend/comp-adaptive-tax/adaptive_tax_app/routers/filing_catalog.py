"""GET /api/v1/filing-catalog — Phase 6 catalog-driven UI source of truth."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from adaptive_tax_app.schemas.filing_catalog import (
    FilingCatalogExplainResponseV1,
    FilingCatalogResponseV1,
    UnsupportedCatalogItemV1,
    UnsupportedCatalogResponseV1,
)
from adaptive_tax_app.services.filing_catalog import (
    explain_component,
    get_filing_catalog_for_year,
    list_unsupported_components,
)
from backend.shared.config.database import get_db

router = APIRouter(tags=["filing-catalog"])

AssessmentYear = Literal["2024_25", "2025_26"]


@router.get(
    "/filing-catalog",
    response_model=FilingCatalogResponseV1,
    summary="YA-filtered filing component catalog for the calculator UI",
)
def get_filing_catalog(
    assessment_year: AssessmentYear = Query(default="2024_25"),
) -> FilingCatalogResponseV1:
    try:
        return get_filing_catalog_for_year(assessment_year)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get(
    "/filing-catalog/unsupported",
    response_model=UnsupportedCatalogResponseV1,
    summary="Unsupported / pending engine rules from catalog (Phase 6.8 queue source)",
)
def get_unsupported_filing_rules() -> UnsupportedCatalogResponseV1:
    rows = list_unsupported_components()
    return UnsupportedCatalogResponseV1(
        count=len(rows),
        items=[
            UnsupportedCatalogItemV1(
                component_id=r.component_id,
                display_name=r.display_name,
                section=r.section,
                paragraph=r.paragraph,
                engine_handler=r.engine_handler,
                engine_support=r.engine_support,
                status=r.status,
                source_doc_id=r.source_doc_id,
                source_quote=r.source_quote,
            )
            for r in rows
        ],
    )


@router.get(
    "/filing-catalog/{component_id}/explain",
    response_model=FilingCatalogExplainResponseV1,
    summary="Field-level legal explain payload (Phase 6.6)",
)
def get_filing_catalog_explain(
    component_id: str,
    assessment_year: AssessmentYear = Query(default="2024_25"),
    db: Session = Depends(get_db),
) -> FilingCatalogExplainResponseV1:
    try:
        return explain_component(
            component_id, assessment_year=assessment_year, db=db
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown component_id: {component_id}",
        ) from exc
