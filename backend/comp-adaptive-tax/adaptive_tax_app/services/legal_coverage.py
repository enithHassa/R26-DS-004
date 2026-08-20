"""Phase 6.8 — legal coverage dashboard (checklist + catalog section grain)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.extracted_rule import KNOWN_ENGINE_HANDLERS
from adaptive_tax_app.schemas.filing_catalog import FilingCatalogComponent
from adaptive_tax_app.schemas.legal_coverage import (
    AreaCoverageSummary,
    ChecklistAreaSummary,
    CoverageComponentRow,
    LegalCoverageResponseV1,
    SectionCoverageRow,
)
from adaptive_tax_app.services.filing_catalog import load_filing_catalog
from backend.shared.config.settings import PROJECT_ROOT

_DEFAULT_CHECKLIST = (
    PROJECT_ROOT / "models" / "adaptive-tax" / "harvest" / "coverage_checklist_v1.json"
)

# Section-grain keys for viva dashboard (Sec 5/6/7/52 + schedules).
_SECTION_GRAIN: tuple[dict[str, str | None], ...] = (
    {
        "section_key": "5",
        "label": "Section 5 — Employment",
        "catalog_section": "5",
        "coverage_area": "employment_income",
    },
    {
        "section_key": "6",
        "label": "Section 6 — Business",
        "catalog_section": "6",
        "coverage_area": "business_income",
    },
    {
        "section_key": "7",
        "label": "Section 7 — Investment",
        "catalog_section": "7",
        "coverage_area": "investment_income",
    },
    {
        "section_key": "8",
        "label": "Section 8 — Other income",
        "catalog_section": "8",
        "coverage_area": "other_income",
    },
    {
        "section_key": "52",
        "label": "Section 52 — Qualifying payments & donations",
        "catalog_section": "52",
        "coverage_area": None,
    },
    {
        "section_key": "89",
        "label": "Section 89 — Tax credits",
        "catalog_section": "89",
        "coverage_area": "tax_credits",
    },
    {
        "section_key": "first_schedule",
        "label": "First Schedule — Progressive rates",
        "catalog_section": None,
        "coverage_area": "first_schedule_rates",
    },
    {
        "section_key": "third_schedule",
        "label": "Third Schedule — Personal relief",
        "catalog_section": None,
        "coverage_area": "personal_relief",
    },
)


def _load_checklist(path: Path | None = None) -> dict[str, Any]:
    checklist_path = path or _DEFAULT_CHECKLIST
    if not checklist_path.is_file():
        raise FileNotFoundError(f"Coverage checklist not found: {checklist_path}")
    return json.loads(checklist_path.read_text(encoding="utf-8"))


def _is_checklist_area_covered(area: dict[str, Any]) -> bool:
    return bool(
        area.get("harvested")
        and area.get("approved")
        and area.get("engine_wired")
        and area.get("provenance_complete")
    )


def _score_checklist_areas(
    checklist: dict[str, Any],
    *,
    include_optional: bool = False,
) -> AreaCoverageSummary:
    areas = list(checklist.get("areas") or [])
    if not include_optional:
        areas = [a for a in areas if not a.get("optional")]

    covered_areas = [a for a in areas if _is_checklist_area_covered(a)]
    planned = len(areas)
    covered = len(covered_areas)
    ratio = (covered / planned) if planned else 0.0

    return AreaCoverageSummary(
        n_planned=planned,
        n_covered=covered,
        coverage=round(ratio, 4),
        coverage_pct=round(ratio * 100.0, 2),
        covered_area_ids=[str(a.get("area_id")) for a in covered_areas],
        pending_area_ids=[str(a.get("area_id")) for a in areas if not _is_checklist_area_covered(a)],
        areas=[
            ChecklistAreaSummary(
                area_id=str(a.get("area_id") or ""),
                meaning=str(a.get("meaning") or ""),
                covered=_is_checklist_area_covered(a),
                harvested=bool(a.get("harvested")),
                approved=bool(a.get("approved")),
                engine_wired=bool(a.get("engine_wired")),
                provenance_complete=bool(a.get("provenance_complete")),
                optional=bool(a.get("optional")),
            )
            for a in areas
        ],
    )


def _handler_wired(handler: str | None) -> bool:
    if not handler:
        return False
    if handler in KNOWN_ENGINE_HANDLERS:
        return True
    return any(
        handler.startswith(prefix)
        for prefix in ("sum_assessable:", "cap_absolute:", "deduct_")
    )


def _provenance_complete(row: FilingCatalogComponent) -> bool:
    return bool(
        row.source_quote
        and row.section
        and row.source_doc_id
        and row.rule_source_id
    )


def _component_covered(row: FilingCatalogComponent) -> bool:
    return (
        row.status == "approved"
        and row.engine_support == "supported"
        and _handler_wired(row.engine_handler)
        and _provenance_complete(row)
    )


def _component_row(row: FilingCatalogComponent) -> CoverageComponentRow:
    approved = row.status == "approved"
    engine_wired = row.engine_support == "supported" and _handler_wired(row.engine_handler)
    prov = _provenance_complete(row)
    return CoverageComponentRow(
        component_id=row.component_id,
        display_name=row.display_name,
        section=row.section,
        status=row.status,
        engine_support=row.engine_support,
        approved=approved,
        engine_wired=engine_wired,
        provenance_complete=prov,
        covered=_component_covered(row),
    )


def _checklist_area_by_id(checklist: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(a.get("area_id")): a for a in checklist.get("areas") or []}


def build_legal_coverage(
    *,
    include_optional: bool = False,
    checklist_path: Path | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> LegalCoverageResponseV1:
    """Combine Phase 5 checklist score with catalog section-grain coverage."""
    checklist = _load_checklist(checklist_path)
    doc = load_filing_catalog(settings=settings)
    area_by_id = _checklist_area_by_id(checklist)
    area_summary = _score_checklist_areas(checklist, include_optional=include_optional)

    sections: list[SectionCoverageRow] = []
    for grain in _SECTION_GRAIN:
        catalog_section = grain["catalog_section"]
        coverage_area = grain["coverage_area"]
        checklist_area = area_by_id.get(coverage_area or "") if coverage_area else None

        if catalog_section:
            rows = [
                row
                for row in doc.components
                if (row.section or "").strip() == catalog_section
                and row.status != "inactive"
            ]
            component_rows = [_component_row(r) for r in rows]
            n_planned = len(component_rows)
            n_covered = sum(1 for c in component_rows if c.covered)
        else:
            # Schedule rows without catalog components — use checklist area as 1/1 proxy.
            component_rows = []
            if checklist_area and not checklist_area.get("optional"):
                n_planned = 1
                n_covered = 1 if _is_checklist_area_covered(checklist_area) else 0
            else:
                n_planned = 0
                n_covered = 0

        ratio = (n_covered / n_planned) if n_planned else 0.0
        sections.append(
            SectionCoverageRow(
                section_key=str(grain["section_key"]),
                label=str(grain["label"]),
                n_planned=n_planned,
                n_covered=n_covered,
                coverage=round(ratio, 4),
                coverage_pct=round(ratio * 100.0, 2),
                checklist_area_id=coverage_area,
                checklist_covered=(
                    _is_checklist_area_covered(checklist_area)
                    if checklist_area
                    else None
                ),
                components=component_rows,
            )
        )

    return LegalCoverageResponseV1(
        catalog_version=doc.catalog_version,
        act_version_label=doc.act_version_label or "",
        assessment_years=list(doc.assessment_years),
        area_summary=area_summary,
        sections=sections,
    )
