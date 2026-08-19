"""Load and query the Phase 6 filing component catalog."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.filing_catalog import (
    FilingCatalogCardOut,
    FilingCatalogComponent,
    FilingCatalogDocument,
    FilingCatalogExplainResponseV1,
    FilingCatalogFieldOut,
    FilingCatalogResponseV1,
)
from backend.shared.config.settings import PROJECT_ROOT

AssessmentYear = Literal["2024_25", "2025_26"]

_DEFAULT_CATALOG = (
    PROJECT_ROOT / "models" / "adaptive-tax" / "fixtures" / "filing_component_catalog_v1.json"
)


def catalog_path(settings: AdaptiveTaxSettings | None = None) -> Path:
    cfg = settings or get_adaptive_tax_settings()
    return cfg.filing_catalog_path


@lru_cache(maxsize=4)
def _load_cached(path_str: str, mtime_ns: int) -> FilingCatalogDocument:
    del mtime_ns  # cache key only
    raw = json.loads(Path(path_str).read_text(encoding="utf-8"))
    return FilingCatalogDocument.model_validate(raw)


def load_filing_catalog(
    settings: AdaptiveTaxSettings | None = None,
) -> FilingCatalogDocument:
    """Load catalog from disk (mtime-busted cache)."""
    path = catalog_path(settings)
    if not path.is_file():
        raise FileNotFoundError(f"Filing component catalog not found: {path}")
    stat = path.stat()
    return _load_cached(str(path.resolve()), stat.st_mtime_ns)


def clear_filing_catalog_cache() -> None:
    _load_cached.cache_clear()


def component_by_id(
    component_id: str,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> FilingCatalogComponent | None:
    doc = load_filing_catalog(settings=settings)
    for row in doc.components:
        if row.component_id == component_id:
            return row
    return None


def _active_for_ya(row: FilingCatalogComponent, year: AssessmentYear) -> bool:
    if row.status in {"pending_unsupported", "inactive"}:
        return False
    if row.status != "approved":
        return False
    if year in row.ya_inactive:
        return False
    if row.ya_effective and year not in row.ya_effective:
        return False
    if row.engine_support == "unsupported":
        return False
    if row.legal_confidence in {"pending", "low"}:
        # Visible in explain metadata later; hide from calculator until approved high/medium.
        return row.legal_confidence == "medium" and row.status == "approved"
    return True


def is_component_active_for_year(
    row: FilingCatalogComponent,
    year: AssessmentYear,
) -> bool:
    """Public YA gate used by normalize + catalog list."""
    return _active_for_ya(row, year)


_SOURCE_LABELS: dict[str, str] = {
    "ird-ira-2017-base": "Inland Revenue Act No. 24 of 2017",
    "ird-amend-2021-10": "IR Act No. 10 of 2021",
    "ird-amend-2022-45": "IR Act No. 45 of 2022",
    "ird-amend-2025-02": "IR Act No. 02 of 2025",
    "ird-amend-2026-11": "IR Act No. 11 of 2026",
    "ird-consolidated-2025": "Inland Revenue Act (consolidated 2025)",
}


def source_doc_label(source_doc_id: str | None) -> str | None:
    if not source_doc_id:
        return None
    return _SOURCE_LABELS.get(source_doc_id, source_doc_id)


_FILM_HINT = frozenset(
    {"qp_film_production", "qp_cinema_construction", "qp_cinema_upgrading"}
)


def _sec52_4_status_text(
    row: FilingCatalogComponent,
    assessment_year: AssessmentYear,
) -> str:
    if row.component_id in _FILM_HINT:
        return "Schedule 1(f) carry-forward (separate from Sec 52(4))"
    if assessment_year != "2025_26":
        return "Not applicable for this assessment year"
    if row.sec52_4_carry_forward:
        return "Eligible under Sec 52(4)"
    return "Not eligible under Sec 52(4)"


def get_filing_catalog_for_year(
    assessment_year: AssessmentYear,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> FilingCatalogResponseV1:
    doc = load_filing_catalog(settings=settings)
    card_meta = {c.card_id: c for c in doc.cards}
    grouped: dict[str, list[FilingCatalogComponent]] = {}
    for row in doc.components:
        if not _active_for_ya(row, assessment_year):
            continue
        # Retired standalone Donations card — 1(a) lives on Qualifying Payments.
        if row.card_id == "donations":
            continue
        grouped.setdefault(row.card_id, []).append(row)

    cards_out: list[FilingCatalogCardOut] = []
    for card_id, rows in grouped.items():
        meta = card_meta.get(card_id)
        rows_sorted = sorted(rows, key=lambda r: (r.sort_order, r.component_id))
        cards_out.append(
            FilingCatalogCardOut(
                card_id=card_id,
                display_name=meta.display_name if meta else card_id.replace("_", " ").title(),
                sort_order=meta.sort_order if meta else 0,
                section=meta.section if meta else None,
                section_uid=meta.section_uid if meta else None,
                fields=[
                    FilingCatalogFieldOut(
                        component_id=r.component_id,
                        display_name=r.display_name,
                        sort_order=r.sort_order,
                        input_kind=r.input_kind,
                        default_treatment=r.default_treatment,
                        user_overridable=r.user_overridable,
                        section=r.section,
                        paragraph=r.paragraph,
                        legal_confidence=r.legal_confidence,
                        confidence_basis=r.confidence_basis,
                        confidence_reason=r.confidence_reason,
                        reason_short=r.reason_short,
                        source_doc_id=r.source_doc_id,
                        engine_support=r.engine_support,
                        status=r.status,
                        ui_group=r.ui_group,
                        effective_from=r.effective_from,
                        effective_to=r.effective_to,
                        applicable_assessment_years=list(r.ya_effective),
                        rule_source_id=r.rule_source_id,
                        engine_handler=r.engine_handler,
                        sec52_4_carry_forward=r.sec52_4_carry_forward,
                        statutory_scope=r.statutory_scope,
                    )
                    for r in rows_sorted
                ],
            )
        )
    cards_out.sort(key=lambda c: (c.sort_order, c.card_id))
    return FilingCatalogResponseV1(
        catalog_version=doc.catalog_version,
        act_version=doc.act_version,
        act_version_label=doc.act_version_label,
        extraction_version=doc.extraction_version,
        knowledge_graph_version=doc.knowledge_graph_version,
        assessment_year=assessment_year,
        cards=cards_out,
    )


def explain_component(
    component_id: str,
    *,
    assessment_year: AssessmentYear = "2024_25",
    settings: AdaptiveTaxSettings | None = None,
    db: Any | None = None,
) -> FilingCatalogExplainResponseV1:
    from adaptive_tax_app.services.evidence import gather_field_evidence

    doc = load_filing_catalog(settings=settings)
    row = component_by_id(component_id, settings=settings)
    if row is None:
        raise KeyError(component_id)
    source_label = source_doc_label(row.source_doc_id)
    if row.component_id == "qp_government_fund" and assessment_year == "2025_26":
        source_label = "IR Act No. 11 of 2026, Section 5 (Sec 52(4)); Fifth Schedule 1(b)(v)"
    elif row.sec52_4_carry_forward and assessment_year == "2025_26":
        source_label = (
            f"{source_label or 'Act'}; Sec 52(4) via IR Act No. 11 of 2026, Section 5"
        )

    kg_nodes: list[dict[str, str]] = []
    if row.concept_id:
        kg_nodes.append({"node_type": "Concept", "node_id": row.concept_id})
    if row.section_uid:
        kg_nodes.append({"node_type": "Section", "node_id": row.section_uid})

    evidence = gather_field_evidence(
        section_uid=row.section_uid,
        rule_source_id=row.rule_source_id,
        db=db,
    )
    evidence_chunks = [
        {
            "chunk_id": ch.chunk_id,
            "text": ch.text,
            "section_ref": ch.section_ref,
            "source_doc_id": ch.source_doc_id,
            "page": ch.page,
            "score": ch.score,
        }
        for ch in evidence.chunks
    ]

    return FilingCatalogExplainResponseV1(
        component_id=row.component_id,
        display_name=row.display_name,
        treatment=row.default_treatment,
        section=row.section,
        paragraph=row.paragraph,
        section_uid=row.section_uid,
        concept_id=row.concept_id,
        reason_short=row.reason_short,
        source_quote=row.source_quote,
        source_doc_id=row.source_doc_id,
        rule_source_id=row.rule_source_id,
        engine_handler=row.engine_handler,
        legal_confidence=row.legal_confidence,
        confidence_basis=row.confidence_basis,
        confidence_reason=row.confidence_reason,
        act_version_label=doc.act_version_label,
        assessment_year=assessment_year,
        applicable_assessment_years=list(row.ya_effective),
        sec52_4_status=_sec52_4_status_text(row, assessment_year),
        source_label=source_label,
        statutory_scope=row.statutory_scope,
        sec52_4_carry_forward=row.sec52_4_carry_forward,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        kg_nodes=kg_nodes,
        evidence_chunks=evidence_chunks,
        evidence_warnings=list(evidence.warnings),
    )


def knowledge_versions_from_catalog(
    *,
    assessment_year: AssessmentYear,
    param_set: str,
    settings: AdaptiveTaxSettings | None = None,
) -> dict[str, str]:
    """Stamp block for CalculateTaxResponseV1.knowledge_versions."""
    doc = load_filing_catalog(settings=settings)
    pack_label = (
        f"{assessment_year}.current"
        if param_set == "current"
        else f"{assessment_year}.pre_amend_2025"
    )
    return {
        "act_version": doc.act_version or "ird-ira-2017-base",
        "act_version_label": doc.act_version_label or "IR Act No. 24 of 2017",
        "catalog_version": doc.catalog_version,
        "rule_pack_version": pack_label,
        "knowledge_graph_version": doc.knowledge_graph_version or "file-ontology",
        "extraction_version": doc.extraction_version or "bootstrap",
    }


def list_unsupported_components(
    settings: AdaptiveTaxSettings | None = None,
) -> list[FilingCatalogComponent]:
    """Catalog rows awaiting engine wiring (Phase 6.8 UI queue source)."""
    doc = load_filing_catalog(settings=settings)
    return [
        row
        for row in doc.components
        if row.engine_support == "unsupported" or row.status == "pending_unsupported"
    ]
