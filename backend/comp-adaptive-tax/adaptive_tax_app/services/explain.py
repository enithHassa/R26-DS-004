"""Orchestrate Phase 4 explain: load calc → gather evidence → narrate (or insufficient)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import CalculateTaxResponseV1
from adaptive_tax_app.schemas.explain import (
    DISCLAIMER,
    ExplainTaxRequestV1,
    ExplainTaxResponseV1,
)
from adaptive_tax_app.schemas.evidence import EvidenceBundle
from adaptive_tax_app.services.calc_store import CalcStoreError, load as load_calculation
from adaptive_tax_app.services.evidence import gather_evidence, has_insufficient_evidence
from adaptive_tax_app.services.gpt_explain import (
    ExplainGenerationError,
    generate_narrative,
)


class ExplainError(RuntimeError):
    """Raised when explain cannot proceed (missing calc, generation failure)."""


def _insufficient_response(
    *,
    calc_id: str,
    final_tax_lkr: str,
    sections_retrieved: list[str],
    evidence: EvidenceBundle | None = None,
) -> ExplainTaxResponseV1:
    return ExplainTaxResponseV1(
        summary="",
        sections_cited=[],
        steps_explained=[],
        final_tax_lkr=final_tax_lkr,
        disclaimer=DISCLAIMER,
        insufficient_evidence=True,
        sections_retrieved=list(sections_retrieved),
        calc_id=calc_id,
        evidence=evidence,
    )


def resolve_calculation(
    body: ExplainTaxRequestV1,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> tuple[CalculateTaxResponseV1, str]:
    """Return ``(calculation, calc_id)`` from store or inline payload."""
    cfg = settings or get_adaptive_tax_settings()

    if body.calculation is not None:
        calc_id = (body.calc_id or body.calculation.calc_id or "").strip()
        return body.calculation, calc_id

    calc_id = (body.calc_id or "").strip()
    try:
        stored = load_calculation(calc_id, settings=cfg)
    except CalcStoreError as exc:
        raise ExplainError(str(exc)) from exc
    if stored is None:
        raise ExplainError(f"calculation not found: {calc_id}")
    return stored.response, stored.calc_id


def explain_tax(
    body: ExplainTaxRequestV1,
    *,
    db: Session | None = None,
    chroma_index: Any | None = None,
    settings: AdaptiveTaxSettings | None = None,
    include_graph_modifies: bool = True,
) -> ExplainTaxResponseV1:
    """Full explain pipeline with empty-evidence short-circuit (never guess)."""
    cfg = settings or get_adaptive_tax_settings()
    calculation, calc_id = resolve_calculation(body, settings=cfg)

    evidence = gather_evidence(
        calculation,
        db=db,
        chroma_index=chroma_index,
        include_graph_modifies=include_graph_modifies,
    )

    if has_insufficient_evidence(evidence):
        return _insufficient_response(
            calc_id=calc_id,
            final_tax_lkr=calculation.final_tax_lkr,
            sections_retrieved=evidence.sections_retrieved,
            evidence=evidence,
        )

    try:
        narrated = generate_narrative(calculation, evidence, settings=cfg)
    except ExplainGenerationError as exc:
        raise ExplainError(str(exc)) from exc

    payload = narrated.payload
    return ExplainTaxResponseV1(
        summary=payload.summary,
        sections_cited=payload.sections_cited,
        steps_explained=payload.steps_explained,
        final_tax_lkr=calculation.final_tax_lkr,
        disclaimer=DISCLAIMER,
        insufficient_evidence=False,
        sections_retrieved=list(evidence.sections_retrieved),
        calc_id=calc_id,
        evidence=evidence,
    )
