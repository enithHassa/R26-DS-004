"""Build deterministic legal reasoning graph from a persisted calculation."""

from __future__ import annotations

from adaptive_tax_app.schemas.calculate import (
    CalculateTaxResponseV1,
    CalculationTraceStep,
    ComponentTraceItemV1,
    RuleSourceRef,
    StoredCalculationV1,
)
from adaptive_tax_app.schemas.reasoning_graph import (
    ReasoningGraphEdgeV1,
    ReasoningGraphNodeV1,
    ReasoningGraphResponseV1,
)

# Viva display order (left-to-right pipeline per Phase 6.8 spec).
_DISPLAY_ORDER: tuple[str, ...] = (
    "salary",
    "employment",
    "assessable",
    "relief",
    "qualifying_payment",
    "taxable",
    "first_schedule",
    "credit",
    "payable",
)

_PIPELINE_EDGES: tuple[tuple[str, str, str], ...] = (
    ("salary", "employment", "included in employment"),
    ("employment", "assessable", "assessable head"),
    ("assessable", "relief", "resident relief"),
    ("relief", "qualifying_payment", "Sec 52 path"),
    ("qualifying_payment", "taxable", "after QP"),
    ("taxable", "first_schedule", "progressive rates"),
    ("first_schedule", "credit", "gross liability"),
    ("credit", "payable", "net payable"),
)


def _trace_by_id(trace: list[CalculationTraceStep]) -> dict[str, CalculationTraceStep]:
    return {s.step_id: s for s in trace}


def _find_step(
    trace: list[CalculationTraceStep],
    *candidates: str,
) -> CalculationTraceStep | None:
    by_id = _trace_by_id(trace)
    for cid in candidates:
        if cid in by_id:
            return by_id[cid]
    for step in trace:
        for cid in candidates:
            if cid in step.step_id:
                return step
    return None


def _refs_by_ids(
    refs: list[RuleSourceRef],
    ids: list[str],
) -> list[RuleSourceRef]:
    if not ids:
        return []
    wanted = set(ids)
    return [r for r in refs if r.id in wanted]


def _first_quote(refs: list[RuleSourceRef]) -> str | None:
    for ref in refs:
        if ref.source_quote:
            return ref.source_quote
    return None


def _merge_step_meta(
    steps: list[CalculationTraceStep],
) -> tuple[list[str], list[str], list[str], list[str]]:
    step_ids: list[str] = []
    section_uids: list[str] = []
    rule_source_ids: list[str] = []
    for step in steps:
        step_ids.append(step.step_id)
        section_uids.extend(step.section_uids)
        rule_source_ids.extend(step.rule_source_ids)
    return (
        step_ids,
        list(dict.fromkeys(section_uids)),
        list(dict.fromkeys(rule_source_ids)),
        [],
    )


def _node_from_steps(
    *,
    node_id: str,
    label: str,
    amount: str | None,
    steps: list[CalculationTraceStep],
    refs: list[RuleSourceRef],
    component_ids: list[str] | None = None,
    kg_node_ids: list[str] | None = None,
    legal_confidence: str | None = None,
    present: bool = True,
) -> ReasoningGraphNodeV1:
    step_ids, section_uids, rule_source_ids, _ = _merge_step_meta(steps)
    matched = _refs_by_ids(refs, rule_source_ids)
    quote = _first_quote(matched)
    section = matched[0].section if matched else None
    if not section and steps:
        for su in section_uids:
            if "::sec::section_" in su:
                section = su.split("::sec::section_")[-1].replace("_", " ")
                break
    kg_ids = list(dict.fromkeys(kg_node_ids or section_uids))
    return ReasoningGraphNodeV1(
        node_id=node_id,
        label=label,
        amount=amount,
        step_ids=step_ids,
        section_uids=section_uids,
        rule_source_ids=rule_source_ids,
        component_ids=component_ids or [],
        kg_node_ids=kg_ids,
        legal_confidence=legal_confidence,
        source_quote=quote,
        section=section,
        present=present,
    )


def _employment_components(
    component_trace: list[ComponentTraceItemV1],
) -> list[ComponentTraceItemV1]:
    return [
        row
        for row in component_trace
        if row.card_id == "employment" and row.included_in_assessable
    ]


def build_reasoning_graph(record: StoredCalculationV1) -> ReasoningGraphResponseV1:
    """Derive viva pipeline graph from calculation trace + component trace + refs."""
    resp: CalculateTaxResponseV1 = record.response
    trace = resp.calculation_trace
    refs = resp.rule_source_refs
    component_trace = resp.component_trace or []

    emp_steps = [
        s
        for s in trace
        if s.step_id in {"aggregate_employment_components", "exclude_employment_exempt_lines"}
        or "employment" in s.step_id
    ]
    assessable_step = _find_step(trace, "sum_assessable")
    qp_steps = [
        s
        for s in trace
        if "qualifying" in s.step_id or s.step_id.startswith("qp_category:")
    ]
    relief_step = _find_step(trace, "apply_personal_relief")
    final_tax_step = _find_step(trace, "final_tax")
    credit_step = _find_step(trace, "apply_tax_credit")

    emp_components = _employment_components(component_trace)
    salary_amount: str | None = None
    salary_ids: list[str] = []
    salary_confidence: str | None = None
    if emp_components:
        salary_ids = [r.component_id for r in emp_components]
        total = sum(int(str(r.amount).split(".")[0] or "0") for r in emp_components)
        salary_amount = str(total)
        confidences = [r.legal_confidence for r in emp_components if r.legal_confidence]
        salary_confidence = confidences[0] if confidences else None

    employment_amount = None
    if resp.head_subtotals:
        employment_amount = resp.head_subtotals.get("employment_include")

    assessable_amount = assessable_step.output if assessable_step else None

    qp_amount = None
    for s in reversed(qp_steps):
        if s.step_id == "deduct_qualifying_payment":
            qp_amount = s.output
            break

    taxable_amount = None
    if relief_step and relief_step.inputs:
        taxable_amount = relief_step.inputs.get("taxable_before_relief") or relief_step.inputs.get(
            "taxable_income"
        )
    if not taxable_amount and qp_steps:
        deduct = _find_step(trace, "deduct_qualifying_payment")
        if deduct and deduct.inputs:
            taxable_amount = deduct.inputs.get("running_after") or deduct.inputs.get("taxable")

    relief_amount = relief_step.output if relief_step else None
    gross_tax = resp.final_tax_lkr
    credit_amount = resp.tax_credits_applied_lkr or None
    payable_amount = resp.tax_payable_lkr or resp.final_tax_lkr

    salary_refs = []
    for row in emp_components:
        salary_refs.extend(_refs_by_ids(refs, row.rule_source_ids))

    nodes: dict[str, ReasoningGraphNodeV1] = {
        "salary": _node_from_steps(
            node_id="salary",
            label="Salary / employment lines",
            amount=salary_amount,
            steps=emp_steps[:1] if emp_steps else [],
            refs=salary_refs or refs,
            component_ids=salary_ids,
            legal_confidence=salary_confidence,
            present=bool(emp_components or emp_steps),
        ),
        "employment": _node_from_steps(
            node_id="employment",
            label="Employment income",
            amount=employment_amount,
            steps=emp_steps,
            refs=refs,
            present=bool(employment_amount or emp_steps),
        ),
        "assessable": _node_from_steps(
            node_id="assessable",
            label="Assessable income",
            amount=assessable_amount,
            steps=[assessable_step] if assessable_step else [],
            refs=refs,
            present=assessable_step is not None,
        ),
        "qualifying_payment": _node_from_steps(
            node_id="qualifying_payment",
            label="Qualifying payment",
            amount=qp_amount,
            steps=qp_steps,
            refs=refs,
            present=bool(qp_steps),
        ),
        "taxable": _node_from_steps(
            node_id="taxable",
            label="Taxable income",
            amount=taxable_amount,
            steps=[s for s in trace if "deduct" in s.step_id or s.step_id == "apply_personal_relief"][:3],
            refs=refs,
            present=taxable_amount is not None,
        ),
        "relief": _node_from_steps(
            node_id="relief",
            label="Personal relief",
            amount=relief_amount,
            steps=[relief_step] if relief_step else [],
            refs=refs,
            present=relief_step is not None,
        ),
        "first_schedule": _node_from_steps(
            node_id="first_schedule",
            label="First Schedule",
            amount=gross_tax,
            steps=[final_tax_step] if final_tax_step else [],
            refs=refs,
            present=final_tax_step is not None,
        ),
        "credit": _node_from_steps(
            node_id="credit",
            label="Tax credits",
            amount=credit_amount,
            steps=[credit_step] if credit_step else [],
            refs=refs,
            present=credit_step is not None,
        ),
        "payable": _node_from_steps(
            node_id="payable",
            label="Tax payable",
            amount=payable_amount,
            steps=[credit_step or final_tax_step] if (credit_step or final_tax_step) else [],
            refs=refs,
            present=True,
        ),
    }

    edges = [
        ReasoningGraphEdgeV1(from_node=a, to_node=b, label=label)
        for a, b, label in _PIPELINE_EDGES
        if nodes[a].present and nodes[b].present
    ]

    return ReasoningGraphResponseV1(
        calc_id=record.calc_id,
        assessment_year=record.request.assessment_year,
        nodes=[nodes[nid] for nid in _DISPLAY_ORDER],
        edges=edges,
        display_order=list(_DISPLAY_ORDER),
    )
