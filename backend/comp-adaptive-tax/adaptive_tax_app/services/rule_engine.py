"""Pure-Python Adaptive Tax rule engine (Phase 3 — no GPT).

Locked legal order
------------------
1. Map inputs → income / deduction concept ids
2. Query KG for applicable income + deduction + LIMITED_BY caps
3. Sum assessable income
4. Apply deductions (QP → solar 2(g) → rent 2(c) → personal relief)
5. Subtract personal relief (residents only)
6. Apply progressive First Schedule slabs
7. Apply Act-backed tax credits (APIT / non-final WHT) → tax_payable

Phase 5.0b: every executable numeric step goes through the provenance gate
(:mod:`adaptive_tax_app.services.provenance`). Strict mode refuses unlinked tax math.
"""

from __future__ import annotations

import logging
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import (
    CalculateTaxRequestV1,
    CalculateTaxResponseV1,
    CalculationTraceStep,
    ComponentTraceItemV1,
    KnowledgeVersionsV1,
    QualifyingPaymentCategoryResultV1,
    QualifyingPaymentSummaryV1,
    RuleSourceRef,
    UnresolvedClaimV1,
)
from adaptive_tax_app.services import engine_handlers as handlers
from adaptive_tax_app.services.filing_catalog import knowledge_versions_from_catalog
from adaptive_tax_app.services.kg_client import (
    ApplicableConcepts,
    FileOntologyKgClient,
    KgClient,
    get_kg_client,
)
from adaptive_tax_app.services.param_store import (
    RateBand,
    TaxParamPack,
    load_tax_param_pack,
)
from adaptive_tax_app.services.provenance import (
    ProvenanceResolution,
    enrich_refs_from_ids,
    merge_rule_source_ids,
    provenance_complete_for_trace,
)
from adaptive_tax_app.services.qp_categories import (
    allocate_sec52_deduction,
    evaluate_qp_filing_rows,
    summarize_category_evals,
)
from adaptive_tax_app.services.request_normalize import normalize_request

logger = logging.getLogger(__name__)

# Locked order among claimed, graph-backed deductions (personal relief is pack-driven).
_DEDUCTION_ORDER = ("qualifying_payment", "solar_panel_relief", "rent_relief")

_INCOME_FIELD_TO_CONCEPT = {
    "employment_income": "employment_income",
    "business_income": "business_income",
    "investment_income": "investment_income",
    "other_income": "other_income",
}

_CLAIM_FIELD_TO_CONCEPT = {
    "qualifying_payments": "qualifying_payment",
    "solar_panel_relief": "solar_panel_relief",
    "rent_relief": "rent_relief",
}

_CONCEPT_TO_COMPONENT = {
    "solar_panel_relief": "relief_solar_panel",
    "rent_relief": "relief_rent",
}

_SOLAR_CAP = Decimal("600000")
_RENT_PCT = Decimal("0.25")


def _q1(value: Decimal) -> Decimal:
    """Round to whole LKR (HALF_UP) — used for tax slices and running totals."""
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _floor1(value: Decimal) -> Decimal:
    """Floor to whole LKR — used for percentage donation ceilings."""
    return value.quantize(Decimal("1"), rounding=ROUND_DOWN)


def _money(value: Decimal) -> str:
    return str(_q1(value))


def _clamp_to_running(allowed: Decimal, running: Decimal) -> Decimal:
    """Later reliefs cannot exceed remaining taxable (floor at zero)."""
    return _q1(min(max(Decimal("0"), allowed), max(Decimal("0"), running)))


def _band_width(band: RateBand) -> Decimal | None:
    """Cumulative lower/upper → Comp-B-style width.

    ``width = upper - max(lower - 1, 0)``; ``upper is None`` → remainder band.
    Band 1 (lower=0, upper=500_000) → width 500_000.
    """
    if band.upper is None:
        return None
    return Decimal(band.upper - max(band.lower - 1, 0))


def _step(
    *,
    step_id: str,
    description: str,
    formula: str,
    inputs: dict[str, Any],
    output: Decimal | str,
    concept_ids: list[str] | None = None,
    section_uids: list[str] | None = None,
    rule_source_ids: list[str] | None = None,
    provenance: str | None = None,
) -> CalculationTraceStep:
    merged_inputs = {k: str(v) for k, v in inputs.items()}
    if provenance:
        merged_inputs.setdefault("provenance", provenance)
    return CalculationTraceStep(
        step_id=step_id,
        description=description,
        formula=formula,
        inputs=merged_inputs,
        output=str(output) if not isinstance(output, Decimal) else _money(output),
        concept_ids=concept_ids or [],
        section_uids=section_uids or [],
        rule_source_ids=rule_source_ids or [],
        provenance=provenance,
    )


def _income_amounts(req: CalculateTaxRequestV1) -> dict[str, Decimal]:
    """Non-zero incomes → employment / business / investment / other heads."""
    out: dict[str, Decimal] = {}
    for field_name, concept_id in _INCOME_FIELD_TO_CONCEPT.items():
        val = _q1(getattr(req, field_name))
        if val > 0:
            out[concept_id] = val
    return out


def _claimed_amounts(req: CalculateTaxRequestV1) -> dict[str, Decimal]:
    """Non-zero claims → qualifying_payment / solar / rent (+ other_reliefs keys)."""
    amounts: dict[str, Decimal] = {}
    for field_name, concept_id in _CLAIM_FIELD_TO_CONCEPT.items():
        val = _q1(getattr(req, field_name))
        if val > 0:
            amounts[concept_id] = val
    for key, raw in req.other_reliefs.items():
        if raw > 0:
            amounts[str(key)] = _q1(raw)
    return amounts


def _cap_allowed(
    *,
    claimed: Decimal,
    cap_concept_id: str | None,
    pack: TaxParamPack,
    assessable: Decimal,
) -> tuple[Decimal, str, list[str], list[str]]:
    """Return ``(allowed, formula, section_uids, ontology_source_ids)``."""
    if not cap_concept_id:
        return claimed, "allowed = claimed (no LIMITED_BY cap)", [], []

    relief = pack.relief_for_concept(cap_concept_id)
    if relief is None:
        return claimed, f"allowed = claimed (missing param for {cap_concept_id})", [], []

    sections = [relief.section_uid] if relief.section_uid else []
    sources = [sid for sid in (relief.relief_id, relief.source_doc_id) if sid]
    if relief.rule_source_id:
        sources.insert(0, relief.rule_source_id)

    if relief.cap_amount is not None:
        allowed = min(claimed, _q1(relief.cap_amount))
        formula = f"allowed = min(claimed, sec52_cap={relief.cap_amount}) via {cap_concept_id}"
        if cap_concept_id != "qualifying_payment_cap":
            formula = f"allowed = min(claimed, {relief.cap_amount}) via {cap_concept_id}"
        return allowed, formula, sections, sources

    if relief.cap_pct_of_assessable is not None:
        ceiling = _floor1(assessable * relief.cap_pct_of_assessable)
        allowed = min(claimed, ceiling)
        formula = (
            f"allowed = min(claimed, floor(assessable * {relief.cap_pct_of_assessable})) "
            f"via {cap_concept_id}"
        )
        return allowed, formula, sections, sources

    return claimed, f"allowed = claimed (empty cap row {cap_concept_id})", sections, sources


def _qp_deduct_ontology(pack: TaxParamPack) -> tuple[list[str], list[str]]:
    """Section + provenance ids for Sec 52(1) qualifying-payment deduct (no aggregate cap)."""
    _ = pack
    return ["ird-ira-2017-base::sec::section_52"], []


def _component_id_for_claim(
    concept_id: str,
    *,
    request: CalculateTaxRequestV1,
    normalized: Any,
) -> str | None:
    mapped = _CONCEPT_TO_COMPONENT.get(concept_id)
    for row in getattr(normalized, "component_trace", []) or []:
        if row.component_id in {concept_id, mapped}:
            return row.component_id
    if concept_id in request.other_reliefs:
        return concept_id
    return mapped


def _collect_unresolved_claims(
    *,
    kg: KgClient,
    claimed: dict[str, Decimal],
    resolved_ids: set[str],
    request: CalculateTaxRequestV1,
    normalized: Any,
) -> list[UnresolvedClaimV1]:
    pending = [
        cid
        for cid in claimed
        if cid not in resolved_ids
        and claimed[cid] > 0
        and cid != "personal_relief"
    ]
    if not pending:
        return []
    classify = getattr(kg, "classify_unresolved_claims", None)
    reasons = (
        classify(pending)
        if callable(classify)
        else {cid: "concept_missing_in_kg" for cid in pending}
    )
    out: list[UnresolvedClaimV1] = []
    for cid in pending:
        reason = reasons.get(cid, "concept_missing_in_kg")
        out.append(
            UnresolvedClaimV1(
                concept_id=cid,
                component_id=_component_id_for_claim(
                    cid, request=request, normalized=normalized
                ),
                claimed_lkr=_money(claimed[cid]),
                reason=reason,  # type: ignore[arg-type]
            )
        )
    return out


def _append_unresolved_trace(
    *,
    unresolved_claims: list[UnresolvedClaimV1],
    trace: list[CalculationTraceStep],
    rules_applied: list[str],
) -> None:
    """Keep unresolved claims visible on the calculation trace (not deducted)."""
    for claim in unresolved_claims:
        step_id = f"unresolved_{claim.concept_id}"
        rules_applied.append(step_id)
        reason = claim.reason
        trace.append(
            _step(
                step_id=step_id,
                description=(
                    f"Claimed {claim.concept_id} was not deducted "
                    f"({reason.replace('_', ' ')})"
                ),
                formula="allowed = 0 (unresolved; not deducted)",
                inputs={
                    "claimed": claim.claimed_lkr,
                    "reason": reason,
                    "concept_id": claim.concept_id,
                },
                output=Decimal("0"),
                concept_ids=[claim.concept_id],
                section_uids=[],
                rule_source_ids=[],
                provenance="missing",
            )
        )


def _solar_cap_amount(pack: TaxParamPack) -> Decimal:
    relief = pack.relief_for_concept("solar_panel_relief")
    if relief is not None and relief.cap_amount is not None:
        return _q1(relief.cap_amount)
    return _SOLAR_CAP


def _apply_solar_panel_relief(
    *,
    claimed_amt: Decimal,
    link: Any,
    pack: TaxParamPack,
    running: Decimal,
    year: str,
    resident_status: str,
    cfg: AdaptiveTaxSettings,
    trace: list[CalculationTraceStep],
    rules_applied: list[str],
    rule_source_refs: list[RuleSourceRef],
) -> Decimal:
    """Fifth Schedule 2(g) — resident only, min(claimed, pack cap 600,000)."""
    cap_amt = _solar_cap_amount(pack)
    cap_gate = handlers.gate(
        handlers.HANDLER_CAP_SOLAR,
        year,
        settings=cfg,
        extra_keys=[
            "solar_panel_relief",
            f"bootstrap:solar_panel_relief_{year}",
            "bootstrap:solar_panel_relief",
        ],
    )
    ded_gate = handlers.gate(
        handlers.HANDLER_DEDUCT_SOLAR,
        year,
        settings=cfg,
        extra_keys=[
            "solar_panel_relief",
            f"bootstrap:deduct_solar_panel_relief_{year}",
        ],
    )
    if resident_status != "resident":
        allowed = Decimal("0")
        formula = "allowed = 0 (non-resident; Fifth Sch 2(g) is resident-only)"
    else:
        allowed = min(claimed_amt, cap_amt)
        formula = f"allowed = min(claimed, {cap_amt})"

    cap_ids, cap_secs, cap_tag = _apply_gate(cap_gate.resolution, [])
    sections = list(dict.fromkeys([*link.section_uids, *cap_secs]))
    rules_applied.append("cap_solar_panel_relief")
    trace.append(
        _step(
            step_id="cap_solar_panel_relief",
            description="Apply Fifth Schedule 2(g) solar panel relief cap",
            formula=formula,
            inputs={
                "claimed": _money(claimed_amt),
                "cap": _money(cap_amt),
                "resident_status": resident_status,
                "allowed": _money(allowed),
            },
            output=allowed,
            concept_ids=["solar_panel_relief"],
            section_uids=sections,
            rule_source_ids=cap_ids,
            provenance=cap_tag,
        )
    )
    rule_source_refs.extend(enrich_refs_from_ids(cap_ids, year, settings=cfg))

    ded_ids, ded_secs, ded_tag = _apply_gate(ded_gate.resolution, [])
    tags = [cap_tag, ded_tag]
    combined = (
        "missing"
        if "missing" in tags
        else ("legacy_seed" if "legacy_seed" in tags else "approved")
    )
    before = running
    allowed = _clamp_to_running(allowed, before)
    running = _q1(max(Decimal("0"), before - allowed))
    rules_applied.append("deduct_solar_panel_relief")
    trace.append(
        _step(
            step_id="deduct_solar_panel_relief",
            description="Deduct Fifth Schedule 2(g) solar panel relief",
            formula="after = max(0, before - min(statutory_allowed, before))",
            inputs={
                "claimed": _money(claimed_amt),
                "allowed": _money(allowed),
                "before": _money(before),
                "after": _money(running),
            },
            output=running,
            concept_ids=["solar_panel_relief", "taxable_income"],
            section_uids=list(dict.fromkeys([*sections, *ded_secs])),
            rule_source_ids=ded_ids,
            provenance=combined,
        )
    )
    rule_source_refs.extend(enrich_refs_from_ids(ded_ids, year, settings=cfg))
    return running


def _apply_rent_relief(
    *,
    claimed_amt: Decimal,
    link: Any,
    running: Decimal,
    year: str,
    inv_rents: Decimal,
    cfg: AdaptiveTaxSettings,
    trace: list[CalculationTraceStep],
    rules_applied: list[str],
    rule_source_refs: list[RuleSourceRef],
) -> Decimal:
    """Fifth Schedule 2(c) — min(claimed, floor(0.25 × included inv_rents)).

    Decision 1b: the 25% base is the Sec 7(2) ``inv_rents`` include line, not
    post-Sec 7(3)(a) net investment income. FWH is a head-level exclusion and
    is not allocated to rents.
    """
    ceiling = _floor1(inv_rents * _RENT_PCT)
    allowed = min(claimed_amt, ceiling)
    cap_gate = handlers.gate(
        handlers.HANDLER_CAP_RENT,
        year,
        settings=cfg,
        extra_keys=[
            "rent_relief",
            f"bootstrap:rent_relief_{year}",
            "bootstrap:rent_relief",
        ],
    )
    ded_gate = handlers.gate(
        handlers.HANDLER_DEDUCT_RENT,
        year,
        settings=cfg,
        extra_keys=["rent_relief", f"bootstrap:deduct_rent_relief_{year}"],
    )
    cap_ids, cap_secs, cap_tag = _apply_gate(cap_gate.resolution, [])
    sections = list(dict.fromkeys([*link.section_uids, *cap_secs]))
    rules_applied.append("cap_rent_relief")
    trace.append(
        _step(
            step_id="cap_rent_relief",
            description=(
                "Apply Fifth Schedule 2(c) rent relief cap (25% of included "
                "inv_rents; not reduced by investment_final_withholding)"
            ),
            formula=f"allowed = min(claimed, floor(0.25 × inv_rents)={ceiling})",
            inputs={
                "claimed": _money(claimed_amt),
                "inv_rents": _money(inv_rents),
                "ceiling": _money(ceiling),
                "allowed": _money(allowed),
            },
            output=allowed,
            concept_ids=["rent_relief"],
            section_uids=sections,
            rule_source_ids=cap_ids,
            provenance=cap_tag,
        )
    )
    rule_source_refs.extend(enrich_refs_from_ids(cap_ids, year, settings=cfg))

    ded_ids, ded_secs, ded_tag = _apply_gate(ded_gate.resolution, [])
    tags = [cap_tag, ded_tag]
    combined = (
        "missing"
        if "missing" in tags
        else ("legacy_seed" if "legacy_seed" in tags else "approved")
    )
    before = running
    allowed = _clamp_to_running(allowed, before)
    running = _q1(max(Decimal("0"), before - allowed))
    rules_applied.append("deduct_rent_relief")
    trace.append(
        _step(
            step_id="deduct_rent_relief",
            description="Deduct Fifth Schedule 2(c) rent relief",
            formula="after = max(0, before - min(statutory_allowed, before))",
            inputs={
                "claimed": _money(claimed_amt),
                "allowed": _money(allowed),
                "before": _money(before),
                "after": _money(running),
            },
            output=running,
            concept_ids=["rent_relief", "taxable_income"],
            section_uids=list(dict.fromkeys([*sections, *ded_secs])),
            rule_source_ids=ded_ids,
            provenance=combined,
        )
    )
    rule_source_refs.extend(enrich_refs_from_ids(ded_ids, year, settings=cfg))
    return running


def _apply_qualifying_payment(
    *,
    request: CalculateTaxRequestV1,
    claimed_amt: Decimal,
    link: Any,
    pack: TaxParamPack,
    assessable: Decimal,
    running: Decimal,
    year: str,
    cfg: AdaptiveTaxSettings,
    trace: list[CalculationTraceStep],
    rules_applied: list[str],
    rule_source_refs: list[RuleSourceRef],
) -> tuple[Decimal, str | None, Decimal, Decimal]:
    """Sec 52 QP path: optional carry-forward in, then deduct per Fifth Sch para 1 limits.

    Per-category caps are applied upstream (``evaluate_qp_filing_rows``); there is
    no fictional aggregate 1.2M/1.8M pool.

    Returns (running, carry_forward_out_wire, allowed, bf_applied).
    Sec 52(4) CF *out* is filled by the caller via category allocation.
    """
    cap_sections, cap_ontology = _qp_deduct_ontology(pack)
    brought_forward = _q1(request.qualifying_payment_brought_forward)
    effective_claim = claimed_amt
    carry_forward_out: Decimal | None = None

    ded_gate = handlers.gate(
        handlers.HANDLER_DEDUCT_QP,
        year,
        settings=cfg,
        extra_keys=[
            "qualifying_payment",
            f"bootstrap:sec52_deduct_qp_{year}",
        ],
    )

    if brought_forward > 0 and year == "2025_26":
        cf_gate = handlers.gate(
            handlers.HANDLER_CARRY_FORWARD_QP,
            year,
            settings=cfg,
            extra_keys=[
                "sec52_carry_forward",
                f"bootstrap:sec52_carry_forward_{year}",
            ],
            executable=True,
        )
        if cf_gate.resolution.ok:
            effective_claim = _q1(claimed_amt + brought_forward)
            cf_ids, cf_secs, cf_tag = _apply_gate(cf_gate.resolution, [])
            cf_secs = list(
                dict.fromkeys(
                    [
                        *cf_secs,
                        "ird-ira-2017-base::sec::section_52",
                        *link.section_uids,
                    ]
                )
            )
            rules_applied.append("apply_qualifying_payment_brought_forward")
            trace.append(
                _step(
                    step_id="apply_qualifying_payment_brought_forward",
                    description=(
                        "Add qualifying payments brought forward under Sec 52(4)"
                    ),
                    formula="effective_claim = current_qualifying_payments + brought_forward",
                    inputs={
                        "current_qualifying_payments": _money(claimed_amt),
                        "brought_forward": _money(brought_forward),
                        "effective_claim": _money(effective_claim),
                    },
                    output=effective_claim,
                    concept_ids=[
                        "qualifying_payment",
                        "qualifying_payment_carry_forward",
                    ],
                    section_uids=cf_secs,
                    rule_source_ids=cf_ids,
                    provenance=cf_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(cf_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Sec 52(4) brought_forward=%s ignored; provenance missing (mode=%s)",
                brought_forward,
                cf_gate.resolution.mode,
            )

    allowed = effective_claim
    ded_sections = list(
        dict.fromkeys([*link.section_uids, *cap_sections])
    )

    ded_ids, ded_prov_secs, ded_tag = _apply_gate(ded_gate.resolution, cap_ontology)
    ded_sections = list(dict.fromkeys([*ded_sections, *ded_prov_secs]))
    ded_tag_combined = ded_tag

    before = running
    allowed = _clamp_to_running(allowed, before)
    running = _q1(max(Decimal("0"), before - allowed))
    rules_applied.append("deduct_qualifying_payment")
    trace.append(
        _step(
            step_id="deduct_qualifying_payment",
            description="Apply qualifying payment deduction",
            formula="after = max(0, before - min(allowed, before))",
            inputs={
                "claimed": _money(claimed_amt),
                "allowed": _money(allowed),
                "before": _money(before),
                "after": _money(running),
            },
            output=running,
            concept_ids=["qualifying_payment", "taxable_income"],
            section_uids=ded_sections,
            rule_source_ids=ded_ids,
            provenance=ded_tag_combined,
        )
    )
    rule_source_refs.extend(enrich_refs_from_ids(ded_ids, year, settings=cfg))

    # Sec 52(4) CF out is computed from per-category undeducted 1(b)(i)/(v) after
    # allocate_sec52_deduction — never from unused absolute-cap headroom.
    out_wire = _money(carry_forward_out) if carry_forward_out is not None else None
    bf_applied = (
        brought_forward
        if brought_forward > 0 and effective_claim > claimed_amt
        else Decimal("0")
    )
    return running, out_wire, allowed, bf_applied


def _apply_gate(
    resolution: ProvenanceResolution,
    ontology_ids: list[str],
) -> tuple[list[str], list[str], str]:
    """Merge provenance + ontology ids; return (ids, section_uids, tag)."""
    if resolution.mode == "legacy" and not resolution.ok:
        logger.warning(
            "provenance legacy_seed for handler=%s (missing Act-backed rule_source)",
            resolution.handler_id,
        )
    ids = merge_rule_source_ids(resolution.rule_source_ids, ontology_ids)
    sections = list(resolution.section_uids)
    return ids, sections, resolution.provenance_tag


def _allocate_slabs(
    taxable: Decimal,
    bands: tuple[RateBand, ...],
    *,
    assessment_year: str,
    settings: AdaptiveTaxSettings | None,
) -> tuple[Decimal, list[CalculationTraceStep], list[str], list[RuleSourceRef]]:
    remaining = _q1(taxable)
    total_tax = Decimal("0")
    steps: list[CalculationTraceStep] = []
    rules: list[str] = []
    refs: list[RuleSourceRef] = []

    if remaining <= 0:
        return Decimal("0"), steps, rules, refs

    slab_gate = handlers.gate(
        handlers.HANDLER_SLAB_BAND,
        assessment_year,
        settings=settings,
        extra_keys=[
            "first_schedule_rates",
            f"bootstrap:first_schedule_rates_{assessment_year}",
            f"first_schedule_rates_{assessment_year}",
        ],
    )
    slab_ids, slab_sections, slab_tag = _apply_gate(
        slab_gate.resolution,
        [],
    )

    for band in sorted(bands, key=lambda b: b.band_index):
        if remaining <= 0:
            break
        width = _band_width(band)
        chunk = remaining if width is None else min(remaining, width)
        tax_slice = _q1(chunk * band.rate)
        total_tax += tax_slice
        remaining = _q1(remaining - chunk)

        rule_id = f"slab_band_{band.band_index}"
        rules.append(rule_id)
        ontology = [sid for sid in (band.rate_band_id, band.source_doc_id) if sid]
        if band.rule_source_id:
            ontology.insert(0, band.rule_source_id)
        ids = merge_rule_source_ids(slab_ids, ontology)
        sections = list(
            dict.fromkeys(
                [
                    *slab_sections,
                    "ird-ira-2017-base::sec::first_schedule",
                ]
            )
        )
        refs.extend(
            enrich_refs_from_ids(ids, assessment_year, settings=settings)
        )
        steps.append(
            _step(
                step_id=rule_id,
                description=band.band_label,
                formula=f"tax_slice = min(remaining, width) * {band.rate}",
                inputs={
                    "taxable_in_slice": _money(chunk),
                    "width": "null" if width is None else _money(width),
                    "rate": str(band.rate),
                },
                output=tax_slice,
                concept_ids=[
                    "taxable_income",
                    "first_schedule_rates",
                    "income_tax_liability",
                ],
                section_uids=sections,
                rule_source_ids=ids,
                provenance=slab_tag,
            )
        )
        if width is None:
            break

    return _q1(total_tax), steps, rules, refs


def _dedupe_refs(refs: list[RuleSourceRef]) -> list[RuleSourceRef]:
    seen: set[str] = set()
    out: list[RuleSourceRef] = []
    for ref in refs:
        if ref.id in seen:
            continue
        seen.add(ref.id)
        out.append(ref)
    return out


def calculate(
    request: CalculateTaxRequestV1,
    *,
    kg: KgClient | None = None,
    pack: TaxParamPack | None = None,
    settings: AdaptiveTaxSettings | None = None,
) -> CalculateTaxResponseV1:
    """Run the tax pipeline and emit an ordered calculation trace with provenance."""
    cfg = settings or get_adaptive_tax_settings()
    normalized = normalize_request(request, settings=cfg)
    request = normalized.request
    pack = pack or load_tax_param_pack(
        assessment_year=request.assessment_year,
        param_set=request.param_set,
        settings=cfg,
    )
    kg = kg or get_kg_client()
    year = request.assessment_year

    income_amounts = _income_amounts(request)
    claimed = _claimed_amounts(request)
    if _q1(request.qualifying_payment_brought_forward) > 0 and (
        "qualifying_payment" not in claimed
    ):
        claimed["qualifying_payment"] = Decimal("0")

    applicable: ApplicableConcepts = kg.resolve_applicable_concepts(
        income_types=list(income_amounts.keys()),
        claimed_deductions=list(claimed.keys()),
    )

    trace: list[CalculationTraceStep] = []
    rules_applied: list[str] = []
    rule_source_refs: list[RuleSourceRef] = []

    # --- 2a. Phase 6.1–6.2 — Sec 5 / Sec 7 component aggregation -------------
    if normalized.used_filing_lines and "employment_include" in normalized.head_subtotals:
        include_amt = _q1(
            normalized.head_subtotals.get("employment_include", Decimal("0"))
        )
        exempt_amt = _q1(
            normalized.head_subtotals.get("employment_exempt", Decimal("0"))
        )
        emp_rows = [
            row for row in normalized.component_trace if row.card_id == "employment"
        ]
        agg_gate = handlers.gate(
            handlers.HANDLER_AGGREGATE_EMPLOYMENT,
            year,
            settings=cfg,
            extra_keys=["aggregate_employment_components", "employment_income"],
            executable=True,
        )
        if agg_gate.resolution.ok:
            line_ids = [
                sid
                for row in emp_rows
                if row.included_in_assessable
                for sid in row.rule_source_ids
            ]
            agg_ids, agg_secs, agg_tag = _apply_gate(
                agg_gate.resolution,
                [
                    "bootstrap:aggregate_employment_components",
                    "ird-ira-2017-base",
                    *line_ids,
                ],
            )
            agg_secs = list(
                dict.fromkeys(
                    [*agg_secs, "ird-ira-2017-base::sec::section_5"]
                )
            )
            rules_applied.append("aggregate_employment_components")
            include_inputs = {
                row.component_id: _money(row.amount)
                for row in emp_rows
                if row.included_in_assessable
            }
            include_inputs["employment_include"] = _money(include_amt)
            trace.append(
                _step(
                    step_id="aggregate_employment_components",
                    description=(
                        "Aggregate employment filing lines into gross employment "
                        "income (Sec 5(2))"
                    ),
                    formula="employment_include = sum(include treatment lines)",
                    inputs=include_inputs,
                    output=include_amt,
                    concept_ids=["employment_income"],
                    section_uids=agg_secs,
                    rule_source_ids=agg_ids,
                    provenance=agg_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(agg_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Employment filing_lines present but aggregate provenance missing "
                "(mode=%s); scalars already set by normalizer",
                agg_gate.resolution.mode,
            )

        if exempt_amt > 0:
            exempt_gate = handlers.gate(
                handlers.HANDLER_EXCLUDE_EMPLOYMENT_EXEMPT,
                year,
                settings=cfg,
                extra_keys=[
                    "exclude_employment_exempt_lines",
                    "emp_medical_benefits",
                ],
                executable=True,
            )
            if exempt_gate.resolution.ok:
                exempt_line_ids = [
                    sid
                    for row in emp_rows
                    if row.treatment_applied == "exempt"
                    for sid in row.rule_source_ids
                ]
                ex_ids, ex_secs, ex_tag = _apply_gate(
                    exempt_gate.resolution,
                    [
                        "bootstrap:exclude_employment_exempt_lines",
                        "ird-ira-2017-base",
                        *exempt_line_ids,
                    ],
                )
                ex_secs = list(
                    dict.fromkeys(
                        [*ex_secs, "ird-ira-2017-base::sec::section_5"]
                    )
                )
                rules_applied.append("exclude_employment_exempt_lines")
                exempt_inputs = {
                    row.component_id: _money(row.amount)
                    for row in emp_rows
                    if row.treatment_applied == "exempt"
                }
                exempt_inputs["employment_exempt"] = _money(exempt_amt)
                trace.append(
                    _step(
                        step_id="exclude_employment_exempt_lines",
                        description=(
                            "Exclude Sec 5(3) exempt employment lines "
                            "(e.g. equal-terms medical) from assessable employment"
                        ),
                        formula=(
                            "exempt lines are omitted from employment_include "
                            "(not added to assessable)"
                        ),
                        inputs=exempt_inputs,
                        output=exempt_amt,
                        concept_ids=["employment_income"],
                        section_uids=ex_secs,
                        rule_source_ids=ex_ids,
                        provenance=ex_tag,
                    )
                )
                rule_source_refs.extend(
                    enrich_refs_from_ids(ex_ids, year, settings=cfg)
                )

    if normalized.used_filing_lines and "investment_include" in normalized.head_subtotals:
        inv_include = _q1(
            normalized.head_subtotals.get("investment_include", Decimal("0"))
        )
        inv_rows = [
            row for row in normalized.component_trace if row.card_id == "investment"
        ]
        inv_agg_gate = handlers.gate(
            handlers.HANDLER_AGGREGATE_INVESTMENT,
            year,
            settings=cfg,
            extra_keys=["aggregate_investment_components", "investment_income"],
            executable=True,
        )
        if inv_agg_gate.resolution.ok:
            inv_line_ids = [
                sid
                for row in inv_rows
                if row.included_in_assessable
                for sid in row.rule_source_ids
            ]
            inv_ids, inv_secs, inv_tag = _apply_gate(
                inv_agg_gate.resolution,
                [
                    "bootstrap:aggregate_investment_components",
                    "ird-ira-2017-base",
                    *inv_line_ids,
                ],
            )
            inv_secs = list(
                dict.fromkeys(
                    [*inv_secs, "ird-ira-2017-base::sec::section_7"]
                )
            )
            rules_applied.append("aggregate_investment_components")
            inv_inputs = {
                row.component_id: _money(row.amount)
                for row in inv_rows
                if row.included_in_assessable
            }
            inv_inputs["investment_include"] = _money(inv_include)
            trace.append(
                _step(
                    step_id="aggregate_investment_components",
                    description=(
                        "Aggregate investment filing lines into gross investment "
                        "income (Sec 7(2))"
                    ),
                    formula="investment_include = sum(include treatment lines)",
                    inputs=inv_inputs,
                    output=inv_include,
                    concept_ids=["investment_income"],
                    section_uids=inv_secs,
                    rule_source_ids=inv_ids,
                    provenance=inv_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(inv_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Investment filing_lines present but aggregate provenance missing "
                "(mode=%s); scalars already set by normalizer",
                inv_agg_gate.resolution.mode,
            )

    if (
        normalized.used_filing_lines
        and "qualifying_payments_claimed" in normalized.head_subtotals
    ):
        qp_claimed = _q1(
            normalized.head_subtotals.get("qualifying_payments_claimed", Decimal("0"))
        )
        qp_rows = [
            row
            for row in normalized.component_trace
            if row.card_id == "qualifying_payments"
            and row.component_id not in {"qp_brought_forward", "qp_unclassified_review"}
            and row.treatment_applied == "deduct"
        ]
        qp_agg_gate = handlers.gate(
            handlers.HANDLER_AGGREGATE_QP,
            year,
            settings=cfg,
            extra_keys=[
                "aggregate_qualifying_payment_components",
                "qualifying_payment",
            ],
            executable=True,
        )
        if qp_agg_gate.resolution.ok:
            qp_line_ids = [
                sid for row in qp_rows for sid in row.rule_source_ids
            ]
            qp_ids, qp_secs, qp_tag = _apply_gate(
                qp_agg_gate.resolution,
                [
                    "bootstrap:aggregate_qualifying_payment_components",
                    "ird-ira-2017-base",
                    *qp_line_ids,
                ],
            )
            qp_secs = list(
                dict.fromkeys(
                    [*qp_secs, "ird-ira-2017-base::sec::section_52"]
                )
            )
            rules_applied.append("aggregate_qualifying_payment_components")
            qp_inputs = {
                row.component_id: _money(row.amount) for row in qp_rows
            }
            qp_inputs["qualifying_payments_claimed"] = _money(qp_claimed)
            trace.append(
                _step(
                    step_id="aggregate_qualifying_payment_components",
                    description=(
                        "Aggregate qualifying-payment filing lines under Sec 52 / "
                        "Fifth Schedule (before YA absolute cap)"
                    ),
                    formula=(
                        "qualifying_payments_claimed = sum(typed deduct lines); "
                        "category rules run after assessable income is known"
                    ),
                    inputs=qp_inputs,
                    output=qp_claimed,
                    concept_ids=["qualifying_payment"],
                    section_uids=qp_secs,
                    rule_source_ids=qp_ids,
                    provenance=qp_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(qp_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "QP filing_lines present but aggregate provenance missing "
                "(mode=%s); scalars already set by normalizer",
                qp_agg_gate.resolution.mode,
            )

    # --- 2b. Sec 5(3)(a) employment exclusions (optional, Act-gated) ----------
    # Apply only when claimed > 0 AND approved Act quote resolves. Unknown
    # other_reliefs concepts remain ignored (KG filter below).
    claimed_fwh = _q1(request.employment_final_withholding)
    if claimed_fwh > 0 and "employment_income" in income_amounts:
        excl_gate = handlers.gate(
            handlers.HANDLER_EXCLUDE_FINAL_WHT,
            year,
            settings=cfg,
            extra_keys=["employment_final_withholding", "exclude_if_final_wht"],
            executable=True,
        )
        if excl_gate.resolution.ok:
            gross = income_amounts["employment_income"]
            excluded = min(claimed_fwh, gross)
            net = _q1(max(Decimal("0"), gross - excluded))
            income_amounts["employment_income"] = net
            if net <= 0:
                del income_amounts["employment_income"]
            excl_ids, excl_secs, excl_tag = _apply_gate(
                excl_gate.resolution,
                ["employment_final_withholding", "ird-ira-2017-base"],
            )
            excl_secs = list(
                dict.fromkeys(
                    [
                        *excl_secs,
                        "ird-ira-2017-base::sec::section_5",
                        *applicable.income_section_uids.get("employment_income", ()),
                    ]
                )
            )
            rules_applied.append("exclude_employment_final_withholding")
            trace.append(
                _step(
                    step_id="exclude_employment_final_withholding",
                    description=(
                        "Exclude exempt amounts / final withholding payments from "
                        "employment (Sec 5(3)(a))"
                    ),
                    formula="net_employment = max(0, gross - min(claimed_fwh, gross))",
                    inputs={
                        "gross_employment": _money(gross),
                        "claimed_final_withholding": _money(claimed_fwh),
                        "excluded": _money(excluded),
                        "net_employment": _money(net),
                    },
                    output=net,
                    concept_ids=[
                        "employment_income",
                        "employment_final_withholding",
                    ],
                    section_uids=excl_secs,
                    rule_source_ids=excl_ids,
                    provenance=excl_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(excl_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Sec 5(3)(a) exclusion claimed but provenance missing; "
                "ignoring employment_final_withholding=%s (mode=%s)",
                claimed_fwh,
                excl_gate.resolution.mode,
            )

    # --- 2b2. Phase 6.4 — Sec 6/11/16 business component aggregation ---------
    if normalized.used_filing_lines and (
        "business_gross" in normalized.head_subtotals
        or "business_net" in normalized.head_subtotals
    ):
        biz_rows = [
            row for row in normalized.component_trace if row.card_id == "business"
        ]
        if biz_rows:
            biz_agg_gate = handlers.gate(
                handlers.HANDLER_AGGREGATE_BUSINESS,
                year,
                settings=cfg,
                extra_keys=[
                    "aggregate_business_components",
                    "business_income",
                    "business_gross",
                ],
                executable=True,
            )
            if biz_agg_gate.resolution.ok:
                line_ids = [
                    sid for row in biz_rows for sid in row.rule_source_ids
                ]
                biz_agg_ids, biz_agg_secs, biz_agg_tag = _apply_gate(
                    biz_agg_gate.resolution,
                    [
                        "bootstrap:aggregate_business_components",
                        "ird-ira-2017-base",
                        *line_ids,
                    ],
                )
                biz_agg_secs = list(
                    dict.fromkeys(
                        [
                            *biz_agg_secs,
                            "ird-ira-2017-base::sec::section_6",
                            "ird-ira-2017-base::sec::section_11",
                            "ird-ira-2017-base::sec::section_16",
                        ]
                    )
                )
                rules_applied.append("aggregate_business_components")
                biz_inputs = {
                    row.component_id: _money(row.amount) for row in biz_rows
                }
                biz_inputs["business_net"] = _money(
                    normalized.head_subtotals.get("business_net", Decimal("0"))
                )
                biz_inputs["business_gross"] = _money(
                    normalized.head_subtotals.get("business_gross", Decimal("0"))
                )
                biz_inputs["business_deductions"] = _money(
                    normalized.head_subtotals.get("business_deductions", Decimal("0"))
                )
                biz_inputs["business_capital_allowances"] = _money(
                    normalized.head_subtotals.get(
                        "business_capital_allowances", Decimal("0")
                    )
                )
                out_amt = normalized.head_subtotals.get(
                    "business_gross", Decimal("0")
                )
                if out_amt <= 0:
                    out_amt = normalized.head_subtotals.get(
                        "business_net", Decimal("0")
                    )
                trace.append(
                    _step(
                        step_id="aggregate_business_components",
                        description=(
                            "Aggregate business filing lines into Sec 6 net or "
                            "gross/deduction/CA inputs"
                        ),
                        formula=(
                            "if gross>0: net = max(0, gross − Sec11 − Sec16); "
                            "else use net profits"
                        ),
                        inputs=biz_inputs,
                        output=_q1(out_amt),
                        concept_ids=["business_income", "business_gross"],
                        section_uids=biz_agg_secs,
                        rule_source_ids=biz_agg_ids,
                        provenance=biz_agg_tag,
                    )
                )
                rule_source_refs.extend(
                    enrich_refs_from_ids(biz_agg_ids, year, settings=cfg)
                )
            else:
                logger.warning(
                    "Business filing_lines present but aggregate provenance missing "
                    "(mode=%s); scalars already set by normalizer",
                    biz_agg_gate.resolution.mode,
                )

    # --- 2c. Sec 6 gross → net business path (optional, Act-gated) -----------
    claimed_gross = _q1(request.business_gross)
    claimed_biz_ded = _q1(request.business_deductions)
    claimed_ca = _q1(request.capital_allowances)
    if claimed_gross > 0:
        net_gate = handlers.gate(
            handlers.HANDLER_COMPUTE_BUSINESS_NET,
            year,
            settings=cfg,
            extra_keys=["business_gross", "compute_business_net"],
            executable=True,
        )
        if net_gate.resolution.ok:
            income_amounts.pop("business_income", None)
            allowed_ded = Decimal("0")
            biz_net_ids, biz_net_secs, biz_net_tag = _apply_gate(
                net_gate.resolution,
                ["business_gross", "ird-ira-2017-base"],
            )
            if claimed_biz_ded > 0:
                ded_gate = handlers.gate(
                    handlers.HANDLER_DEDUCT_BUSINESS_EXPENSES,
                    year,
                    settings=cfg,
                    extra_keys=["business_deductions", "deduct_business_expenses"],
                    executable=True,
                )
                if ded_gate.resolution.ok:
                    allowed_ded = min(claimed_biz_ded, claimed_gross)
                    ded_ids, ded_secs, ded_tag = _apply_gate(
                        ded_gate.resolution,
                        ["business_deductions"],
                    )
                    biz_net_ids = merge_rule_source_ids(biz_net_ids, ded_ids)
                    biz_net_secs = list(dict.fromkeys([*biz_net_secs, *ded_secs]))
                    biz_net_tag = ded_tag or biz_net_tag
                else:
                    logger.warning(
                        "Sec 11 deductions claimed but provenance missing; "
                        "ignoring business_deductions=%s (mode=%s)",
                        claimed_biz_ded,
                        ded_gate.resolution.mode,
                    )
            allowed_ca = Decimal("0")
            if claimed_ca > 0:
                ca_gate = handlers.gate(
                    handlers.HANDLER_DEDUCT_CAPITAL_ALLOWANCES,
                    year,
                    settings=cfg,
                    extra_keys=["capital_allowances", "deduct_capital_allowances"],
                    executable=True,
                )
                if ca_gate.resolution.ok:
                    remaining_after_ded = claimed_gross - allowed_ded
                    allowed_ca = min(claimed_ca, max(Decimal("0"), remaining_after_ded))
                    ca_ids, ca_secs, ca_tag = _apply_gate(
                        ca_gate.resolution,
                        ["capital_allowances"],
                    )
                    biz_net_ids = merge_rule_source_ids(biz_net_ids, ca_ids)
                    biz_net_secs = list(dict.fromkeys([*biz_net_secs, *ca_secs]))
                    biz_net_tag = ca_tag or biz_net_tag
                else:
                    logger.warning(
                        "Sec 16 capital allowances claimed but provenance missing; "
                        "ignoring capital_allowances=%s (mode=%s)",
                        claimed_ca,
                        ca_gate.resolution.mode,
                    )
            net_business = _q1(
                max(Decimal("0"), claimed_gross - allowed_ded - allowed_ca)
            )
            if net_business > 0:
                income_amounts["business_income"] = net_business
            biz_net_secs = list(
                dict.fromkeys(
                    [
                        *biz_net_secs,
                        "ird-ira-2017-base::sec::section_6",
                        *applicable.income_section_uids.get("business_income", ()),
                    ]
                )
            )
            if allowed_ded > 0:
                biz_net_secs.append("ird-ira-2017-base::sec::section_11")
            if allowed_ca > 0:
                biz_net_secs.append("ird-ira-2017-base::sec::section_16")
            biz_net_secs = list(dict.fromkeys(biz_net_secs))
            rules_applied.append("compute_business_net")
            trace.append(
                _step(
                    step_id="compute_business_net",
                    description=(
                        "Compute net business profits from gross minus allowable "
                        "expenses and capital allowances (Sec 6 / 11 / 16)"
                    ),
                    formula=(
                        "net_business = max(0, gross - allowed_deductions - allowed_ca)"
                    ),
                    inputs={
                        "business_gross": _money(claimed_gross),
                        "business_deductions_claimed": _money(claimed_biz_ded),
                        "capital_allowances_claimed": _money(claimed_ca),
                        "allowed_deductions": _money(allowed_ded),
                        "allowed_capital_allowances": _money(allowed_ca),
                        "net_business": _money(net_business),
                    },
                    output=net_business,
                    concept_ids=[
                        "business_income",
                        "business_gross",
                        "business_deductions",
                        "capital_allowances",
                    ],
                    section_uids=biz_net_secs,
                    rule_source_ids=biz_net_ids,
                    provenance=biz_net_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(biz_net_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Business gross path claimed but provenance missing; "
                "ignoring business_gross=%s (mode=%s)",
                claimed_gross,
                net_gate.resolution.mode,
            )

    # --- 2d. Sec 7(3)(a) investment exclusions (optional, Act-gated) ---------
    claimed_inv_fwh = _q1(request.investment_final_withholding)
    if claimed_inv_fwh > 0 and "investment_income" in income_amounts:
        inv_excl_gate = handlers.gate(
            handlers.HANDLER_EXCLUDE_INVESTMENT_FINAL_WHT,
            year,
            settings=cfg,
            extra_keys=[
                "investment_final_withholding",
                "exclude_investment_final_wht",
            ],
            executable=True,
        )
        if inv_excl_gate.resolution.ok:
            gross = income_amounts["investment_income"]
            excluded = min(claimed_inv_fwh, gross)
            net = _q1(max(Decimal("0"), gross - excluded))
            income_amounts["investment_income"] = net
            if net <= 0:
                del income_amounts["investment_income"]
            excl_ids, excl_secs, excl_tag = _apply_gate(
                inv_excl_gate.resolution,
                ["investment_final_withholding", "ird-ira-2017-base"],
            )
            excl_secs = list(
                dict.fromkeys(
                    [
                        *excl_secs,
                        "ird-ira-2017-base::sec::section_7",
                        *applicable.income_section_uids.get("investment_income", ()),
                    ]
                )
            )
            rules_applied.append("exclude_investment_final_withholding")
            trace.append(
                _step(
                    step_id="exclude_investment_final_withholding",
                    description=(
                        "Exclude exempt amounts / final withholding payments from "
                        "investment (Sec 7(3)(a))"
                    ),
                    formula="net_investment = max(0, gross - min(claimed_fwh, gross))",
                    inputs={
                        "gross_investment": _money(gross),
                        "claimed_final_withholding": _money(claimed_inv_fwh),
                        "excluded": _money(excluded),
                        "net_investment": _money(net),
                    },
                    output=net,
                    concept_ids=[
                        "investment_income",
                        "investment_final_withholding",
                    ],
                    section_uids=excl_secs,
                    rule_source_ids=excl_ids,
                    provenance=excl_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(excl_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Sec 7(3)(a) exclusion claimed but provenance missing; "
                "ignoring investment_final_withholding=%s (mode=%s) — "
                "summing investment_income as entered",
                claimed_inv_fwh,
                inv_excl_gate.resolution.mode,
            )

    # --- 2e. Phase 6.5 — Sec 8 other-income component aggregation ------------
    if normalized.used_filing_lines and "other_include" in normalized.head_subtotals:
        oth_include = _q1(
            normalized.head_subtotals.get("other_include", Decimal("0"))
        )
        oth_rows = [
            row for row in normalized.component_trace if row.card_id == "other_income"
        ]
        oth_agg_gate = handlers.gate(
            handlers.HANDLER_AGGREGATE_OTHER,
            year,
            settings=cfg,
            extra_keys=["aggregate_other_income_components", "other_income"],
            executable=True,
        )
        if oth_agg_gate.resolution.ok:
            oth_line_ids = [
                sid
                for row in oth_rows
                if row.included_in_assessable
                for sid in row.rule_source_ids
            ]
            oth_ids, oth_secs, oth_tag = _apply_gate(
                oth_agg_gate.resolution,
                [
                    "bootstrap:aggregate_other_income_components",
                    "ird-ira-2017-base",
                    *oth_line_ids,
                ],
            )
            oth_secs = list(
                dict.fromkeys(
                    [*oth_secs, "ird-ira-2017-base::sec::section_8"]
                )
            )
            rules_applied.append("aggregate_other_income_components")
            oth_inputs: dict[str, str] = {}
            custom_idx = 0
            for row in oth_rows:
                if not row.included_in_assessable:
                    continue
                if row.component_id == "oth_custom":
                    key = f"oth_custom[{custom_idx}]:{row.display_name}"
                    custom_idx += 1
                else:
                    key = row.component_id
                oth_inputs[key] = _money(row.amount)
            oth_inputs["other_include"] = _money(oth_include)
            trace.append(
                _step(
                    step_id="aggregate_other_income_components",
                    description=(
                        "Aggregate Sec 8 residual / custom other-income filing "
                        "lines into other_income"
                    ),
                    formula="other_include = sum(include treatment lines)",
                    inputs=oth_inputs,
                    output=oth_include,
                    concept_ids=["other_income"],
                    section_uids=oth_secs,
                    rule_source_ids=oth_ids,
                    provenance=oth_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(oth_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Other-income filing_lines present but aggregate provenance missing "
                "(mode=%s); scalars already set by normalizer",
                oth_agg_gate.resolution.mode,
            )

    # --- 2f. Sec 8(2)(a) other-income exclusions (optional, Act-gated) -------
    claimed_oth_fwh = _q1(request.other_final_withholding)
    if claimed_oth_fwh > 0 and "other_income" in income_amounts:
        oth_excl_gate = handlers.gate(
            handlers.HANDLER_EXCLUDE_OTHER_FINAL_WHT,
            year,
            settings=cfg,
            extra_keys=[
                "other_final_withholding",
                "exclude_other_final_wht",
            ],
            executable=True,
        )
        if oth_excl_gate.resolution.ok:
            gross = income_amounts["other_income"]
            excluded = min(claimed_oth_fwh, gross)
            net = _q1(max(Decimal("0"), gross - excluded))
            income_amounts["other_income"] = net
            if net <= 0:
                del income_amounts["other_income"]
            excl_ids, excl_secs, excl_tag = _apply_gate(
                oth_excl_gate.resolution,
                ["other_final_withholding", "ird-ira-2017-base"],
            )
            excl_secs = list(
                dict.fromkeys(
                    [
                        *excl_secs,
                        "ird-ira-2017-base::sec::section_8",
                        *applicable.income_section_uids.get("other_income", ()),
                    ]
                )
            )
            rules_applied.append("exclude_other_final_withholding")
            trace.append(
                _step(
                    step_id="exclude_other_final_withholding",
                    description=(
                        "Exclude exempt amounts / final withholding payments from "
                        "other income (Sec 8(2)(a))"
                    ),
                    formula="net_other = max(0, gross - min(claimed_fwh, gross))",
                    inputs={
                        "gross_other": _money(gross),
                        "claimed_final_withholding": _money(claimed_oth_fwh),
                        "excluded": _money(excluded),
                        "net_other": _money(net),
                    },
                    output=net,
                    concept_ids=["other_income", "other_final_withholding"],
                    section_uids=excl_secs,
                    rule_source_ids=excl_ids,
                    provenance=excl_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(excl_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Sec 8(2)(a) exclusion claimed but provenance missing; "
                "ignoring other_final_withholding=%s (mode=%s) — "
                "summing other_income as entered",
                claimed_oth_fwh,
                oth_excl_gate.resolution.mode,
            )

    # Re-resolve incomes if a head dropped to zero after exclusions.
    if not income_amounts and applicable.income_concept_ids:
        applicable = kg.resolve_applicable_concepts(
            income_types=[],
            claimed_deductions=list(claimed.keys()),
        )
    elif income_amounts:
        applicable = kg.resolve_applicable_concepts(
            income_types=list(income_amounts.keys()),
            claimed_deductions=list(claimed.keys()),
        )

    unresolved_claims = _collect_unresolved_claims(
        kg=kg,
        claimed=claimed,
        resolved_ids={d.concept_id for d in applicable.deductions},
        request=request,
        normalized=normalized,
    )
    _append_unresolved_trace(
        unresolved_claims=unresolved_claims,
        trace=trace,
        rules_applied=rules_applied,
    )

    # --- 3. Sum assessable (provenance-gated) --------------------------------
    sum_gate = handlers.gate(
        handlers.HANDLER_SUM_ASSESSABLE,
        year,
        settings=cfg,
        extra_keys=["ird-ira-2017-base", *income_amounts.keys()],
    )
    sum_ids, sum_prov_sections, sum_tag = _apply_gate(
        sum_gate.resolution,
        ["ird-ira-2017-base"],
    )

    assessable = Decimal("0")
    income_inputs: dict[str, Any] = {}
    income_concepts: list[str] = []
    income_sections: list[str] = list(sum_prov_sections)
    for cid in applicable.income_concept_ids:
        # Per-head gate — employment contribution carries Sec 5 provenance.
        head_gate = handlers.gate(
            handlers.income_handler_id(cid),
            year,
            settings=cfg,
            extra_keys=[cid],
            executable=True,
        )
        amt = income_amounts.get(cid, Decimal("0"))
        assessable += amt
        income_inputs[cid] = _money(amt)
        income_concepts.append(cid)
        income_sections.extend(applicable.income_section_uids.get(cid, ()))
        income_sections.extend(head_gate.resolution.section_uids)
        if head_gate.resolution.ok:
            sum_ids = merge_rule_source_ids(
                sum_ids, head_gate.resolution.rule_source_ids
            )
    assessable = _q1(assessable)

    rules_applied.append("sum_assessable")
    rule_source_refs.extend(enrich_refs_from_ids(sum_ids, year, settings=cfg))
    trace.append(
        _step(
            step_id="sum_assessable",
            description="Sum assessable income from KG-applicable income heads",
            formula=(
                "assessable = net_employment + net_business_profits + investment "
                "+ other_income (applicable heads; unknown concepts ignored)"
            ),
            inputs=income_inputs,
            output=assessable,
            concept_ids=["assessable_income", *income_concepts],
            section_uids=list(dict.fromkeys(income_sections)),
            rule_source_ids=sum_ids,
            provenance=sum_tag,
        )
    )

    # --- 4. Deductions -------------------------------------------------------
    running = assessable
    ded_by_id = {d.concept_id: d for d in applicable.deductions}
    ordered_claims = [c for c in _DEDUCTION_ORDER if c in claimed and c in ded_by_id]
    ordered_claims.extend(c for c in claimed if c not in ordered_claims and c in ded_by_id)

    qp_carry_forward_out: str | None = None
    qp_category_results: list[QualifyingPaymentCategoryResultV1] = []
    qp_summary: QualifyingPaymentSummaryV1 | None = None

    for concept_id in ordered_claims:
        link = ded_by_id[concept_id]
        claimed_amt = claimed[concept_id]

        if concept_id == "qualifying_payment":
            qp_rows = [
                {
                    "component_id": row.component_id,
                    "display_name": row.display_name,
                    "amount": row.amount,
                    "section": row.section,
                    "paragraph": row.paragraph,
                    "legal_confidence": row.legal_confidence,
                    "rule_source_ids": list(row.rule_source_ids),
                }
                for row in normalized.component_trace
                if row.card_id == "qualifying_payments"
            ]
            totals = {
                "total_claimed": claimed_amt,
                "total_allowable_before_sec52": claimed_amt,
                "total_needs_review": Decimal("0"),
            }
            evals: list = []
            if qp_rows:
                evals = evaluate_qp_filing_rows(
                    qp_rows,
                    assessable=assessable,
                    assessment_year=year,
                )
                totals = summarize_category_evals(evals)
                claimed_amt = totals["total_allowable_before_sec52"]
                rules_applied.append("evaluate_qualifying_payment_categories")

            running, _ignored_cf, final_allowed, bf_applied = _apply_qualifying_payment(
                request=request,
                claimed_amt=claimed_amt,
                link=link,
                pack=pack,
                assessable=assessable,
                running=running,
                year=year,
                cfg=cfg,
                trace=trace,
                rules_applied=rules_applied,
                rule_source_refs=rule_source_refs,
            )

            # Current-year share of the Sec 52 deduction (BF applied first).
            allowed_for_categories = _q1(
                max(Decimal("0"), final_allowed - bf_applied)
            )
            cf_out_dec: Decimal | None = None
            cf_not_elig = Decimal("0")
            if evals:
                evals, cf_out_dec, cf_not_elig = allocate_sec52_deduction(
                    evals,
                    allowed_for_categories=allowed_for_categories,
                    assessment_year=year,
                )
                if year != "2025_26":
                    cf_out_dec = None
                else:
                    # Stamp CF provenance step when Sec 52(4) path is in force.
                    cf_out_gate = handlers.gate(
                        handlers.HANDLER_CARRY_FORWARD_QP,
                        year,
                        settings=cfg,
                        extra_keys=[
                            "sec52_carry_forward",
                            f"bootstrap:sec52_carry_forward_{year}",
                        ],
                        executable=True,
                    )
                    if cf_out_gate.resolution.ok:
                        cf_doc_ids = [
                            r.source_doc_id
                            for r in cf_out_gate.resolution.records
                            if r.source_doc_id
                        ]
                        out_ids, out_secs, out_tag = _apply_gate(
                            cf_out_gate.resolution, cf_doc_ids
                        )
                        out_secs = list(
                            dict.fromkeys(
                                [
                                    *out_secs,
                                    "ird-ira-2017-base::sec::section_52",
                                    *link.section_uids,
                                ]
                            )
                        )
                        rules_applied.append("carry_forward_qualifying_payment_out")
                        trace.append(
                            _step(
                                step_id="carry_forward_qualifying_payment_out",
                                description=(
                                    "Sec 52(4) carry-forward = sum of undeducted "
                                    "amounts for Fifth Sch 1(b)(i) and 1(b)(v) only"
                                ),
                                formula=(
                                    "carry_forward_out = sum(carry_forward_amount) "
                                    "where sec52_4_eligible"
                                ),
                                inputs={
                                    "allowed_for_categories": _money(
                                        allowed_for_categories
                                    ),
                                    "carry_forward_out": _money(cf_out_dec),
                                    "carry_forward_not_eligible": _money(cf_not_elig),
                                    "assessment_year": year,
                                },
                                output=cf_out_dec,
                                concept_ids=[
                                    "qualifying_payment_carry_forward",
                                    "qualifying_payment",
                                ],
                                section_uids=out_secs,
                                rule_source_ids=out_ids,
                                provenance=out_tag,
                            )
                        )
                        rule_source_refs.extend(
                            enrich_refs_from_ids(out_ids, year, settings=cfg)
                        )
                    else:
                        cf_out_dec = None

                qp_category_results.clear()
                for ev in evals:
                    if ev.claimed <= 0 and ev.component_id != "qp_unclassified_review":
                        continue
                    qp_category_results.append(
                        QualifyingPaymentCategoryResultV1.model_validate(ev.as_dict())
                    )
                    trace.append(
                        _step(
                            step_id=f"qp_category:{ev.component_id}",
                            description=(
                                f"Evaluate {ev.display_name} under {ev.legal_reference}"
                            ),
                            formula=ev.formula,
                            inputs={
                                "assessment_year": year,
                                "claimed_amount": _money(ev.claimed),
                                "allowable_amount": _money(ev.allowable),
                                "deducted_this_year": _money(ev.deducted_this_year),
                                "undeducted_amount": _money(ev.undeducted_amount),
                                "sec52_4_eligible": (
                                    "true" if ev.sec52_4_eligible else "false"
                                ),
                                "carry_forward_amount": _money(
                                    ev.carry_forward_amount
                                ),
                                "status": ev.status,
                                "assessable": _money(assessable),
                            },
                            output=ev.allowable,
                            concept_ids=["qualifying_payment"],
                            section_uids=["ird-ira-2017-base::sec::section_52"],
                            rule_source_ids=list(ev.rule_source_ids),
                            provenance="approved",
                        )
                    )

            qp_carry_forward_out = (
                _money(cf_out_dec) if cf_out_dec is not None else None
            )

            qp_summary = QualifyingPaymentSummaryV1(
                total_claimed=str(_q1(totals["total_claimed"])),
                total_allowable_before_sec52=str(
                    _q1(totals["total_allowable_before_sec52"])
                ),
                section_52_cap=None,
                final_allowable_deduction=str(_q1(final_allowed)),
                unused_after_sec52=None,
                carry_forward_out=qp_carry_forward_out,
                carry_forward_not_eligible=(
                    str(_q1(cf_not_elig)) if evals else None
                ),
                sec52_4_applicable=(year == "2025_26"),
                total_needs_review=str(_q1(totals["total_needs_review"])),
            )
            continue

        if concept_id == "solar_panel_relief":
            running = _apply_solar_panel_relief(
                claimed_amt=claimed_amt,
                link=link,
                pack=pack,
                running=running,
                year=year,
                resident_status=request.resident_status,
                cfg=cfg,
                trace=trace,
                rules_applied=rules_applied,
                rule_source_refs=rule_source_refs,
            )
            continue

        if concept_id == "rent_relief":
            inv_rents = _q1(
                normalized.head_subtotals.get("inv_rents", Decimal("0"))
            )
            running = _apply_rent_relief(
                claimed_amt=claimed_amt,
                link=link,
                running=running,
                year=year,
                inv_rents=inv_rents,
                cfg=cfg,
                trace=trace,
                rules_applied=rules_applied,
                rule_source_refs=rule_source_refs,
            )
            continue

        if link.cap_concept_id:
            cap_hid = handlers.cap_handler_id(link.cap_concept_id)
            cap_gate = handlers.gate(
                cap_hid,
                year,
                settings=cfg,
                extra_keys=[link.cap_concept_id, f"cap_{link.cap_concept_id}"],
            )
            rules_applied.append(f"cap_{link.cap_concept_id}")
        else:
            cap_gate = None

        deduct_hid = handlers.deduct_handler_id(concept_id)
        ded_gate = handlers.gate(
            deduct_hid,
            year,
            settings=cfg,
            extra_keys=[concept_id],
        )

        allowed, formula, sections, ontology_sources = _cap_allowed(
            claimed=claimed_amt,
            cap_concept_id=link.cap_concept_id,
            pack=pack,
            assessable=assessable,
        )
        prov_ids: list[str] = []
        prov_sections: list[str] = []
        tags: list[str] = []
        if cap_gate is not None:
            ids, secs, tag = _apply_gate(cap_gate.resolution, ontology_sources)
            prov_ids = merge_rule_source_ids(prov_ids, ids)
            prov_sections.extend(secs)
            tags.append(tag)
        ids, secs, tag = _apply_gate(ded_gate.resolution, ontology_sources)
        prov_ids = merge_rule_source_ids(prov_ids, ids)
        prov_sections.extend(secs)
        tags.append(tag)
        tag = (
            "missing"
            if "missing" in tags
            else ("legacy_seed" if "legacy_seed" in tags else "approved")
        )

        sections = list(dict.fromkeys([*link.section_uids, *sections, *prov_sections]))
        before = running
        allowed = _clamp_to_running(allowed, before)
        running = _q1(max(Decimal("0"), before - allowed))

        step_id = f"deduct_{concept_id}"
        rules_applied.append(step_id)
        trace.append(
            _step(
                step_id=step_id,
                description=f"Apply deduction {concept_id}",
                formula=formula,
                inputs={
                    "claimed": _money(claimed_amt),
                    "allowed": _money(allowed),
                    "before": _money(before),
                    "after": _money(running),
                },
                output=running,
                concept_ids=[concept_id, "taxable_income"]
                + ([link.cap_concept_id] if link.cap_concept_id else []),
                section_uids=sections,
                rule_source_ids=prov_ids,
                provenance=tag,
            )
        )
        rule_source_refs.extend(
            enrich_refs_from_ids(prov_ids, year, settings=cfg)
        )

    after_deductions = running

    # --- 5. Personal relief (Fifth Sch 2(a); after QP → solar → rent) -------
    pr_gate = handlers.gate(
        handlers.HANDLER_PERSONAL_RELIEF,
        year,
        settings=cfg,
        extra_keys=[
            "personal_relief",
            f"bootstrap:personal_relief_{year}",
        ],
    )
    personal = pack.relief_for_concept("personal_relief")
    personal_amount = (
        _q1(personal.cap_amount)
        if (
            request.resident_status == "resident"
            and personal is not None
            and personal.cap_amount is not None
        )
        else Decimal("0")
    )
    # Strict mode already gated; if missing in strict, require_provenance raised.
    taxable = _q1(max(Decimal("0"), after_deductions - personal_amount))
    pr_sections = [personal.section_uid] if personal and personal.section_uid else []
    pr_ontology = (
        [sid for sid in (personal.relief_id, personal.source_doc_id) if sid]
        if personal
        else []
    )
    if personal and personal.rule_source_id:
        pr_ontology.insert(0, personal.rule_source_id)
    pr_ids, pr_prov_secs, pr_tag = _apply_gate(pr_gate.resolution, pr_ontology)
    pr_sections = list(dict.fromkeys([*pr_sections, *pr_prov_secs]))
    rules_applied.append("apply_personal_relief")
    trace.append(
        _step(
            step_id="apply_personal_relief",
            description="Subtract personal relief (residents only; non_resident → 0)",
            formula="taxable = max(0, after_deductions - personal_relief)",
            inputs={
                "after_deductions": _money(after_deductions),
                "personal_relief": _money(personal_amount),
                "resident_status": request.resident_status,
            },
            output=taxable,
            concept_ids=["personal_relief", "taxable_income"],
            section_uids=pr_sections,
            rule_source_ids=pr_ids,
            provenance=pr_tag,
        )
    )
    rule_source_refs.extend(enrich_refs_from_ids(pr_ids, year, settings=cfg))

    # --- 6. Progressive slabs ------------------------------------------------
    total_tax, slab_steps, slab_rules, slab_refs = _allocate_slabs(
        taxable,
        pack.rate_bands,
        assessment_year=year,
        settings=cfg,
    )
    trace.extend(slab_steps)
    rules_applied.extend(slab_rules)
    rule_source_refs.extend(slab_refs)

    final_gate = handlers.gate(
        handlers.HANDLER_FINAL_TAX,
        year,
        settings=cfg,
        extra_keys=["ird-ira-2017-base", "first_schedule_rates"],
    )
    final_ids, final_secs, final_tag = _apply_gate(
        final_gate.resolution,
        ["ird-ira-2017-base"],
    )
    rules_applied.append("final_tax")
    trace.append(
        _step(
            step_id="final_tax",
            description="Gross income tax liability (before credits)",
            formula="final_tax = sum(slab tax slices)",
            inputs={"taxable_income": _money(taxable)},
            output=total_tax,
            concept_ids=["income_tax_liability"],
            section_uids=list(
                dict.fromkeys(
                    [*final_secs, "ird-ira-2017-base::sec::first_schedule"]
                )
            ),
            rule_source_ids=final_ids,
            provenance=final_tag,
        )
    )
    rule_source_refs.extend(enrich_refs_from_ids(final_ids, year, settings=cfg))

    # --- 7. Tax credits (APIT / non-final WHT) → tax payable -----------------
    claimed_credit = _q1(request.apit_already_paid)
    credits_applied = Decimal("0")
    tax_payable = total_tax
    if claimed_credit > 0:
        credit_gate = handlers.gate(
            handlers.HANDLER_TAX_CREDIT,
            year,
            settings=cfg,
            extra_keys=["tax_credit", "apit_already_paid"],
            executable=True,
        )
        if credit_gate.resolution.ok:
            credits_applied = min(claimed_credit, total_tax)
            tax_payable = _q1(max(Decimal("0"), total_tax - credits_applied))
            credit_ids, credit_secs, credit_tag = _apply_gate(
                credit_gate.resolution,
                ["tax_credit", "apit_already_paid", "ird-ira-2017-base"],
            )
            credit_secs = list(
                dict.fromkeys(
                    [
                        *credit_secs,
                        "ird-ira-2017-base::sec::section_89",
                        "ird-ira-2017-base::sec::section_2",
                    ]
                )
            )
            rules_applied.append("apply_tax_credit")
            trace.append(
                _step(
                    step_id="apply_tax_credit",
                    description=(
                        "Credit APIT / non-final withholding already paid "
                        "(Sec 89; Sec 2(3) tax credits)"
                    ),
                    formula=(
                        "tax_payable = max(0, final_tax − min(apit_already_paid, final_tax))"
                    ),
                    inputs={
                        "final_tax": _money(total_tax),
                        "apit_already_paid": _money(claimed_credit),
                        "credits_applied": _money(credits_applied),
                    },
                    output=tax_payable,
                    concept_ids=["tax_credit", "apit_already_paid", "tax_payable"],
                    section_uids=credit_secs,
                    rule_source_ids=credit_ids,
                    provenance=credit_tag,
                )
            )
            rule_source_refs.extend(
                enrich_refs_from_ids(credit_ids, year, settings=cfg)
            )
        else:
            logger.warning(
                "Tax credit claimed but provenance missing; "
                "ignoring apit_already_paid=%s (mode=%s) — "
                "tax_payable equals gross final_tax",
                claimed_credit,
                credit_gate.resolution.mode,
            )

    complete = provenance_complete_for_trace(trace)
    try:
        versions = KnowledgeVersionsV1.model_validate(
            knowledge_versions_from_catalog(
                assessment_year=request.assessment_year,
                param_set=request.param_set,
                settings=cfg,
            )
        )
    except FileNotFoundError:
        versions = KnowledgeVersionsV1(
            act_version="ird-ira-2017-base",
            act_version_label="IR Act No. 24 of 2017",
            catalog_version="missing",
            rule_pack_version=f"{request.assessment_year}.{request.param_set}",
            knowledge_graph_version="file-ontology",
            extraction_version="bootstrap",
        )

    component_trace = [
        ComponentTraceItemV1.model_validate(row.as_dict())
        for row in normalized.component_trace
    ]
    head_subtotals = {k: str(_q1(v)) for k, v in normalized.head_subtotals.items()}

    return CalculateTaxResponseV1(
        final_tax_lkr=_money(total_tax),
        tax_payable_lkr=_money(tax_payable),
        tax_credits_applied_lkr=_money(credits_applied),
        calculation_trace=trace,
        rules_applied=rules_applied,
        rule_source_refs=_dedupe_refs(rule_source_refs),
        provenance_complete=complete,
        qualifying_payment_carry_forward_out=qp_carry_forward_out,
        qualifying_payment_categories=qp_category_results,
        qualifying_payment_summary=qp_summary,
        knowledge_versions=versions,
        head_subtotals=head_subtotals,
        component_trace=component_trace,
        normalize_warnings=list(normalized.warnings),
        unresolved_claims=unresolved_claims,
    )


def default_file_kg() -> FileOntologyKgClient:
    """Convenience for unit tests that must stay offline."""
    return FileOntologyKgClient()
