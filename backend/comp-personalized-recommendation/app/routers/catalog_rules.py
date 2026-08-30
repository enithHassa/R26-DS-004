"""Opt-in admin endpoints: sync Adaptive Tax catalog JSON into recommendation preview."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.catalog_rules_service import (
    catalog_rules_status,
    clear_synced_catalog,
    diff_catalog_vs_default,
    extract_catalog_preview_metadata,
    get_synced_snapshot,
    metadata_to_dict,
    sync_catalog_rules,
)

router = APIRouter()


class CatalogSyncRequest(BaseModel):
    assessment_year: str = Field(..., min_length=7, max_length=7, pattern=r"^\d{4}_\d{2}$")


class RulesFieldDiffItem(BaseModel):
    field: str
    default_value: str
    catalog_value: str
    act_reference: str | None = None
    section_ref: str | None = None


class CatalogActReferenceItem(BaseModel):
    label: str
    act_name: str
    section_ref: str | None = None
    source_doc_id: str | None = None
    effective_from: str | None = None
    quote_excerpt: str | None = None


class CatalogPreviewMetadataItem(BaseModel):
    assessment_year: str
    assessment_period: str
    promoted_at: str | None = None
    promotion_source: str | None = None
    promotion_run: str | None = None
    carried_forward_from: str | None = None
    watcher_source_doc_id: str | None = None
    catalog_notes: str | None = None
    default_rules_version: str
    default_rules_label: str
    relief_entries_count: int
    rate_bands_count: int
    mapped_fields: list[str]
    fallback_fields: list[str]
    legal_references: list[CatalogActReferenceItem]


class CatalogSyncResponse(BaseModel):
    assessment_year: str
    synced_at: str
    promoted_at: str | None
    personal_relief_act: str | None
    mapped_fields: list[str]
    fallback_fields: list[str]
    metadata: CatalogPreviewMetadataItem
    diffs: list[RulesFieldDiffItem]


class CatalogStatusResponse(BaseModel):
    default_rules_version: str
    default_rules_path: str
    catalog_source: str
    catalog_approved_dir: str
    available_assessment_years: list[str]
    synced_years: list[dict]


class CatalogPreviewResponse(BaseModel):
    assessment_year: str
    already_synced: bool
    metadata: CatalogPreviewMetadataItem
    diffs: list[RulesFieldDiffItem]


def _diff_items(assessment_year: str) -> list[RulesFieldDiffItem]:
    return [
        RulesFieldDiffItem(
            field=d.field,
            default_value=d.default_value,
            catalog_value=d.catalog_value,
            act_reference=d.act_reference,
            section_ref=d.section_ref,
        )
        for d in diff_catalog_vs_default(assessment_year)
    ]


def _metadata_item(assessment_year: str) -> CatalogPreviewMetadataItem:
    return CatalogPreviewMetadataItem(**metadata_to_dict(extract_catalog_preview_metadata(assessment_year)))


@router.get("/status", response_model=CatalogStatusResponse)
def get_catalog_rules_status() -> CatalogStatusResponse:
    """List catalog years on disk and which years are loaded in the opt-in cache."""
    return CatalogStatusResponse(**catalog_rules_status())


@router.get("/preview", response_model=CatalogPreviewResponse)
def preview_catalog_rules(
    assessment_year: str = Query(..., pattern=r"^\d{4}_\d{2}$"),
) -> CatalogPreviewResponse:
    """Preview rule diffs without changing the default recommendation pipeline."""
    try:
        metadata = _metadata_item(assessment_year)
        diffs = _diff_items(assessment_year)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return CatalogPreviewResponse(
        assessment_year=assessment_year,
        metadata=metadata,
        diffs=diffs,
        already_synced=get_synced_snapshot(assessment_year) is not None,
    )


@router.post("/sync", response_model=CatalogSyncResponse)
def sync_catalog_rules_endpoint(payload: CatalogSyncRequest) -> CatalogSyncResponse:
    """Load catalog JSON for a year into the in-memory opt-in cache."""
    try:
        snapshot = sync_catalog_rules(payload.assessment_year)
        metadata = _metadata_item(payload.assessment_year)
        diffs = _diff_items(payload.assessment_year)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return CatalogSyncResponse(
        assessment_year=snapshot.assessment_year,
        synced_at=snapshot.synced_at,
        promoted_at=snapshot.promoted_at,
        personal_relief_act=snapshot.personal_relief_act,
        mapped_fields=snapshot.mapped_fields,
        fallback_fields=snapshot.fallback_fields,
        metadata=metadata,
        diffs=diffs,
    )


@router.post("/clear")
def clear_catalog_rules_cache() -> dict[str, Literal["cleared"]]:
    """Drop all opt-in catalog rules from memory; default YAML path unchanged."""
    clear_synced_catalog()
    return {"status": "cleared"}
