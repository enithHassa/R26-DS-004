"""Pure-Python Adaptive Tax rule engine (Phase 3 — no GPT).

Locked legal order
------------------
1. Map inputs → income / deduction concept ids
2. Query KG for applicable income + deduction + LIMITED_BY caps
3. Sum assessable income
4. Apply deductions (QP → donation → other graph-backed claims)
5. Subtract personal relief (residents only)
6. Apply progressive First Schedule slabs
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxRequestV1,
    CalculateTaxResponseV1,
    CalculationTraceStep,
    RuleSourceRef,
)
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

# MVP fixed order among claimed, graph-backed deductions.
_DEDUCTION_ORDER = ("qualifying_payment", "donation")

_INCOME_FIELD_TO_CONCEPT = {
    "employment_income": "employment_income",
    "business_income": "business_income",
    "investment_income": "investment_income",
}

_CLAIM_FIELD_TO_CONCEPT = {
    "qualifying_payments": "qualifying_payment",
    "donations": "donation",
}


def _is_neo4j_unavailable(exc: BaseException) -> bool:
    """True when Bolt/Neo4j is down (or auth/connect failed hard)."""
    name = type(exc).__name__
    if name in {"ServiceUnavailable", "Neo4jError", "ClientError", "AuthError"}:
        return True
    msg = str(exc).lower()
    return any(
        needle in msg
        for needle in (
            "couldn't connect",
            "connection refused",
            "failed to establish connection",
            "actively refused",
        )
    )


def _q1(value: Decimal) -> Decimal:
    """Round to whole LKR (HALF_UP) — used for tax slices and running totals."""
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _floor1(value: Decimal) -> Decimal:
    """Floor to whole LKR — used for percentage donation ceilings."""
    return value.quantize(Decimal("1"), rounding=ROUND_DOWN)


def _money(value: Decimal) -> str:
    return str(_q1(value))


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
) -> CalculationTraceStep:
    return CalculationTraceStep(
        step_id=step_id,
        description=description,
        formula=formula,
        inputs={k: str(v) for k, v in inputs.items()},
        output=str(output) if not isinstance(output, Decimal) else _money(output),
        concept_ids=concept_ids or [],
        section_uids=section_uids or [],
        rule_source_ids=rule_source_ids or [],
    )


def _income_amounts(req: CalculateTaxRequestV1) -> dict[str, Decimal]:
    """Non-zero incomes → employment_income / business_income / investment_income."""
    out: dict[str, Decimal] = {}
    for field_name, concept_id in _INCOME_FIELD_TO_CONCEPT.items():
        val = _q1(getattr(req, field_name))
        if val > 0:
            out[concept_id] = val
    return out


def _claimed_amounts(req: CalculateTaxRequestV1) -> dict[str, Decimal]:
    """Non-zero claims → qualifying_payment / donation (+ other_reliefs keys)."""
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
    """Return ``(allowed, formula, section_uids, rule_source_ids)``."""
    if not cap_concept_id:
        return claimed, "allowed = claimed (no LIMITED_BY cap)", [], []

    relief = pack.relief_for_concept(cap_concept_id)
    if relief is None:
        return claimed, f"allowed = claimed (missing param for {cap_concept_id})", [], []

    sections = [relief.section_uid] if relief.section_uid else []
    sources = [sid for sid in (relief.relief_id, relief.source_doc_id) if sid]

    # Section 52 aggregate (and other absolute caps).
    if relief.cap_amount is not None:
        allowed = min(claimed, _q1(relief.cap_amount))
        formula = f"allowed = min(claimed, sec52_cap={relief.cap_amount}) via {cap_concept_id}"
        if cap_concept_id != "qualifying_payment_cap":
            formula = f"allowed = min(claimed, {relief.cap_amount}) via {cap_concept_id}"
        return allowed, formula, sections, sources

    # Donation % of assessable (floor).
    if relief.cap_pct_of_assessable is not None:
        ceiling = _floor1(assessable * relief.cap_pct_of_assessable)
        allowed = min(claimed, ceiling)
        formula = (
            f"allowed = min(claimed, floor(assessable * {relief.cap_pct_of_assessable})) "
            f"via {cap_concept_id}"
        )
        return allowed, formula, sections, sources

    return claimed, f"allowed = claimed (empty cap row {cap_concept_id})", sections, sources


def _allocate_slabs(
    taxable: Decimal,
    bands: tuple[RateBand, ...],
) -> tuple[Decimal, list[CalculationTraceStep], list[str], list[RuleSourceRef]]:
    remaining = _q1(taxable)
    total_tax = Decimal("0")
    steps: list[CalculationTraceStep] = []
    rules: list[str] = []
    refs: list[RuleSourceRef] = []

    if remaining <= 0:
        return Decimal("0"), steps, rules, refs

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
        refs.append(
            RuleSourceRef(
                id=band.rate_band_id,
                kind="rate_band",
                concept_id="taxable_income",
            )
        )
        if band.source_doc_id:
            refs.append(
                RuleSourceRef(
                    id=band.source_doc_id,
                    kind="source_doc",
                    concept_id="first_schedule_rates",
                )
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
                section_uids=["ird-ira-2017-base::sec::first_schedule"],
                rule_source_ids=[
                    sid for sid in (band.rate_band_id, band.source_doc_id) if sid
                ],
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
) -> CalculateTaxResponseV1:
    """Run the Phase 3 tax pipeline and emit an ordered calculation trace."""
    pack = pack or load_tax_param_pack(
        assessment_year=request.assessment_year,
        param_set=request.param_set,
    )
    kg = kg or get_kg_client()

    # --- 1. Map inputs → concept ids -----------------------------------------
    income_amounts = _income_amounts(request)
    claimed = _claimed_amounts(request)

    # --- 2. Query KG ---------------------------------------------------------
    try:
        applicable: ApplicableConcepts = kg.resolve_applicable_concepts(
            income_types=list(income_amounts.keys()),
            claimed_deductions=list(claimed.keys()),
        )
    except Exception as exc:
        # Neo4j Desktop down / bolt refused while .env still has NEO4J_PASSWORD
        # (auto mode). Fall back to file ontology for offline calculator use.
        if isinstance(kg, FileOntologyKgClient):
            raise
        if not _is_neo4j_unavailable(exc):
            raise
        kg = FileOntologyKgClient()
        applicable = kg.resolve_applicable_concepts(
            income_types=list(income_amounts.keys()),
            claimed_deductions=list(claimed.keys()),
        )
    # Live Neo4j without reloaded Phase 3 CONTRIBUTES_TO edges returns no incomes
    # → assessable 0 / tax 0. Fall back to the seeded file ontology in that case.
    if income_amounts and not applicable.income_concept_ids and not isinstance(
        kg, FileOntologyKgClient
    ):
        kg = FileOntologyKgClient()
        applicable = kg.resolve_applicable_concepts(
            income_types=list(income_amounts.keys()),
            claimed_deductions=list(claimed.keys()),
        )

    # --- 3. Sum assessable income --------------------------------------------
    assessable = Decimal("0")
    income_inputs: dict[str, Any] = {}
    income_concepts: list[str] = []
    income_sections: list[str] = []
    for cid in applicable.income_concept_ids:
        amt = income_amounts.get(cid, Decimal("0"))
        assessable += amt
        income_inputs[cid] = _money(amt)
        income_concepts.append(cid)
        income_sections.extend(applicable.income_section_uids.get(cid, ()))
    assessable = _q1(assessable)

    trace: list[CalculationTraceStep] = []
    rules_applied: list[str] = ["sum_assessable"]
    rule_source_refs: list[RuleSourceRef] = [
        RuleSourceRef(
            id="ird-ira-2017-base",
            kind="source_doc",
            concept_id="assessable_income",
        )
    ]
    trace.append(
        _step(
            step_id="sum_assessable",
            description="Sum assessable income from KG-applicable income heads",
            formula="assessable = employment + business + investment (applicable heads)",
            inputs=income_inputs,
            output=assessable,
            concept_ids=["assessable_income", *income_concepts],
            section_uids=list(dict.fromkeys(income_sections)),
            rule_source_ids=["ird-ira-2017-base"],
        )
    )

    # --- 4. Apply deductions (QP → donation → other) -------------------------
    running = assessable
    ded_by_id = {d.concept_id: d for d in applicable.deductions}
    ordered_claims = [c for c in _DEDUCTION_ORDER if c in claimed and c in ded_by_id]
    ordered_claims.extend(c for c in claimed if c not in ordered_claims and c in ded_by_id)

    for concept_id in ordered_claims:
        link = ded_by_id[concept_id]
        claimed_amt = claimed[concept_id]
        allowed, formula, sections, sources = _cap_allowed(
            claimed=claimed_amt,
            cap_concept_id=link.cap_concept_id,
            pack=pack,
            assessable=assessable,
        )
        sections = list(dict.fromkeys([*link.section_uids, *sections]))
        before = running
        running = _q1(max(Decimal("0"), running - allowed))

        if link.cap_concept_id:
            rules_applied.append(f"cap_{link.cap_concept_id}")
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
                rule_source_ids=sources,
            )
        )
        for sid in sources:
            kind = (
                "relief"
                if sid.endswith("_cap") or sid == "personal_relief" or sid.startswith("sec52")
                else "source_doc"
            )
            rule_source_refs.append(
                RuleSourceRef(
                    id=sid,
                    kind=kind,
                    section_uid=sections[0] if sections else None,
                    concept_id=concept_id,
                )
            )

    after_deductions = running

    # --- 5. Personal relief (residents only) ---------------------------------
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
    taxable = _q1(max(Decimal("0"), after_deductions - personal_amount))
    pr_sections = [personal.section_uid] if personal and personal.section_uid else []
    pr_sources = (
        [sid for sid in (personal.relief_id, personal.source_doc_id) if sid] if personal else []
    )
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
            rule_source_ids=pr_sources,
        )
    )
    for sid in pr_sources:
        rule_source_refs.append(
            RuleSourceRef(
                id=sid,
                kind="relief",
                section_uid=pr_sections[0] if pr_sections else None,
                concept_id="personal_relief",
            )
        )

    # --- 6. Progressive slabs ------------------------------------------------
    total_tax, slab_steps, slab_rules, slab_refs = _allocate_slabs(taxable, pack.rate_bands)
    trace.extend(slab_steps)
    rules_applied.extend(slab_rules)
    rule_source_refs.extend(slab_refs)

    rules_applied.append("final_tax")
    trace.append(
        _step(
            step_id="final_tax",
            description="Total income tax liability",
            formula="final_tax = sum(slab tax slices)",
            inputs={"taxable_income": _money(taxable)},
            output=total_tax,
            concept_ids=["income_tax_liability"],
            section_uids=["ird-ira-2017-base::sec::first_schedule"],
            rule_source_ids=["ird-ira-2017-base"],
        )
    )

    return CalculateTaxResponseV1(
        final_tax_lkr=_money(total_tax),
        calculation_trace=trace,
        rules_applied=rules_applied,
        rule_source_refs=_dedupe_refs(rule_source_refs),
    )


def default_file_kg() -> FileOntologyKgClient:
    """Convenience for unit tests that must stay offline."""
    return FileOntologyKgClient()
