"""GET /api/v1/relief-interview/* — Phase 3 catalog read for Relief Interview UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.shared.config.settings import PROJECT_ROOT

router = APIRouter(prefix="/relief-interview", tags=["relief-interview"])

APPROVED_DIR = PROJECT_ROOT / "models" / "adaptive-tax" / "relief-interview" / "approved"
RATES_DIR = PROJECT_ROOT / "models" / "adaptive-tax" / "relief-interview" / "rates"
SUPPORTED_YAS = (
    "2018_19",
    "2019_20",
    "2020_21",
    "2021_22",
    "2022_23",
    "2023_24",
    "2024_25",
    "2025_26",
)


def _load_year(ya: str) -> dict[str, Any]:
    if ya not in SUPPORTED_YAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported assessment_year {ya!r}",
        )
    path = APPROVED_DIR / f"{ya}.json"
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved catalog missing for {ya}",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid JSON in {path.name}",
        ) from exc


def _load_rates(ya: str) -> dict[str, Any]:
    if ya not in SUPPORTED_YAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported assessment_year {ya!r}",
        )
    path = RATES_DIR / f"{ya}.json"
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rates catalog missing for {ya}",
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid JSON in {path.name}",
        ) from exc


@router.get(
    "/approved/{assessment_year}",
    summary="Approved relief catalog for one assessment year (may be empty until Phase 5)",
)
def get_approved_year(assessment_year: str) -> dict[str, Any]:
    data = _load_year(assessment_year)
    entries = data.get("entries")
    if not isinstance(entries, list):
        entries = []
    return {
        "spec_version": data.get("spec_version", "1.0.0"),
        "assessment_year": assessment_year,
        "phase1_empty_skeleton": bool(data.get("phase1_empty_skeleton")),
        "notes": data.get("notes"),
        "entries": entries,
        "entry_count": len(entries),
        "catalog_path": str(
            Path("models/adaptive-tax/relief-interview/approved") / f"{assessment_year}.json"
        ),
    }


@router.get(
    "/rates/{assessment_year}",
    summary="Promoted rates catalog for one YA (bands + special_formulas provenance)",
)
def get_rates_year(assessment_year: str) -> dict[str, Any]:
    data = _load_rates(assessment_year)
    formulas = data.get("special_formulas")
    if not isinstance(formulas, list):
        formulas = []
    surcharges = data.get("surcharges")
    if not isinstance(surcharges, list):
        surcharges = []
    bands = data.get("bands")
    if not isinstance(bands, list):
        bands = []
    return {
        "spec_version": data.get("spec_version", "1.0.0"),
        "assessment_year": assessment_year,
        "currency": data.get("currency", "LKR"),
        "needs_manual_verification": bool(data.get("needs_manual_verification", True)),
        "bands": bands,
        "surcharges": surcharges,
        "special_formulas": formulas,
        "notes": data.get("notes"),
        "catalog_path": str(
            Path("models/adaptive-tax/relief-interview/rates") / f"{assessment_year}.json"
        ),
    }


@router.get(
    "/approved",
    summary="Approved relief catalogs for all supported assessment years",
)
def get_approved_all() -> dict[str, Any]:
    years: list[dict[str, Any]] = []
    for ya in SUPPORTED_YAS:
        path = APPROVED_DIR / f"{ya}.json"
        if not path.is_file():
            years.append(
                {
                    "assessment_year": ya,
                    "entries": [],
                    "entry_count": 0,
                    "missing": True,
                }
            )
            continue
        data = _load_year(ya)
        entries = data.get("entries") if isinstance(data.get("entries"), list) else []
        years.append(
            {
                "assessment_year": ya,
                "phase1_empty_skeleton": bool(data.get("phase1_empty_skeleton")),
                "entries": entries,
                "entry_count": len(entries),
                "missing": False,
            }
        )
    return {"assessment_years": list(SUPPORTED_YAS), "years": years}
