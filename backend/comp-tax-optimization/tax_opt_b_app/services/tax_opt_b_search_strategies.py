"""Function 2 — enumerated max-cap subset search (rule-only, passing strategies)."""

from __future__ import annotations

import hashlib
from decimal import ROUND_HALF_UP, Decimal

from tax_opt_b_app.services.tax_opt_b_financial_strategy_presets import (
    profile_from_financial_inputs,
    relief_max_claim_amounts_by_code,
)
from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBRulePack
from tax_opt_b_app.services.tax_opt_b_search_row_explainability import (
    build_row_explainability,
    build_rule_trace,
    build_search_metrics,
    build_search_tax_breakdown,
    build_top_rank_explanation,
    comparison_summary_text,
)
from tax_opt_b_app.services.tax_opt_b_strategy_display_names import display_name_for_subset
from tax_opt_b_app.services.tax_opt_b_tax_computation import RESEARCH_DISCLAIMER, run_compliance_and_compute_tax
from tax_opt_b_app.tax_opt_b_schemas_compliance_v1 import TaxOptBComplianceResultV1
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import (
    SEARCH_GRID_VERSION,
    TaxOptBAppliedReliefSummaryEntryV1,
    TaxOptBSearchOptimizationMetaV1,
    TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
    TaxOptBSearchStrategiesResponseV1,
    TaxOptBSearchStrategyRowV1,
    TaxOptBSearchTraceabilityV1,
    TaxOptBStrategyCandidateSpecV1,
    TaxOptBStrategySearchRankByV1,
)
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _employment_type_str(profile: TaxOptBProfileV1) -> str:
    et = profile.employment_type
    return et.value if hasattr(et, "value") else str(et)


def search_space_id(profile: TaxOptBProfileV1, ordered_relief_codes: tuple[str, ...]) -> str:
    payload = "|".join(
        [
            SEARCH_GRID_VERSION,
            profile.tax_year,
            _employment_type_str(profile),
            str(profile.dependents),
            str(profile.annual_gross_income),
            str(profile.estimated_annual_taxable_income or ""),
            ",".join(ordered_relief_codes),
        ],
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _candidate_label(included: tuple[str, ...]) -> str:
    if not included:
        return "No statutory claims (grid)"
    return "MVP max cap: " + ", ".join(included)


def enumerate_candidate_specs(
    profile: TaxOptBProfileV1,
    pack: TaxOptBRulePack,
    *,
    max_candidates: int,
) -> list[TaxOptBStrategyCandidateSpecV1]:
    amounts = relief_max_claim_amounts_by_code(profile, pack)
    ordered = tuple(sorted(amounts.keys()))
    n = len(ordered)
    total = 1 << n
    if total > max_candidates:
        raise ValueError(
            f"Grid size {total} exceeds max_candidates={max_candidates} "
            f"({n} reliefs with MVP caps).",
        )
    specs: list[TaxOptBStrategyCandidateSpecV1] = []
    for mask in range(total):
        included_list = [ordered[i] for i in range(n) if (mask >> i) & 1]
        included = tuple(included_list)
        cid = f"cap_subset_{mask}"
        specs.append(
            TaxOptBStrategyCandidateSpecV1(
                grid_version=SEARCH_GRID_VERSION,
                included_relief_codes=included,
                candidate_id=cid,
                label=_candidate_label(included),
            ),
        )
    return specs


def _applied_relief_summary(compliance: TaxOptBComplianceResultV1) -> list[TaxOptBAppliedReliefSummaryEntryV1]:
    out: list[TaxOptBAppliedReliefSummaryEntryV1] = []
    for key, val in compliance.applied_relief.items():
        if isinstance(val, dict):
            rc = str(val.get("relief_code", key))
            out.append(
                TaxOptBAppliedReliefSummaryEntryV1(
                    relief_code=rc,
                    allowed=str(val["allowed"]) if val.get("allowed") is not None else None,
                    cap=str(val["cap"]) if val.get("cap") is not None else None,
                    claimed=str(val["claimed"]) if val.get("claimed") is not None else None,
                ),
            )
        else:
            out.append(TaxOptBAppliedReliefSummaryEntryV1(relief_code=str(key)))
    out.sort(key=lambda e: e.relief_code)
    return out


def _effective_rate_str(tax: Decimal, gross: Decimal) -> str | None:
    if gross <= 0:
        return None
    rate = (tax / gross).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return str(rate)


def _candidate_mask(candidate_id: str) -> int:
    return int(candidate_id.rsplit("_", 1)[-1], 10)


def _sort_tuple(
    rank_by: TaxOptBStrategySearchRankByV1,
    *,
    total_tax: Decimal,
    gross: Decimal,
    candidate_id: str,
) -> tuple[Decimal, Decimal, int] | tuple[Decimal, int]:
    tie = _candidate_mask(candidate_id)
    if rank_by == "effective_rate" and gross > 0:
        eff = total_tax / gross
        return (eff, total_tax, tie)
    return (total_tax, tie)


def search_strategies_from_financial_inputs(
    body: TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
    pack: TaxOptBRulePack,
    *,
    rules_version_label: str | None = None,
) -> TaxOptBSearchStrategiesResponseV1:
    keys = set(TaxOptBFinancialInputsV1.model_fields.keys())
    fin = TaxOptBFinancialInputsV1.model_validate(body.model_dump(include=keys))
    profile = profile_from_financial_inputs(fin)
    amounts = relief_max_claim_amounts_by_code(profile, pack)
    ordered = tuple(sorted(amounts.keys()))
    space_id = search_space_id(profile, ordered)
    yaml_labels = dict(pack.relief_display_names)

    specs = enumerate_candidate_specs(
        profile,
        pack,
        max_candidates=body.max_candidates,
    )
    baseline_id = body.baseline_candidate_id or "cap_subset_0"
    grid_ids = {s.candidate_id for s in specs}
    if baseline_id not in grid_ids:
        raise ValueError(f"baseline_candidate_id {baseline_id!r} is not in the search grid")

    passing: list[
        tuple[
            TaxOptBStrategyCandidateSpecV1,
            TaxOptBComputeTaxResponseV1,
            Decimal,
        ]
    ] = []
    for spec in specs:
        strategy = spec.to_strategy_proposal(amounts)
        out = run_compliance_and_compute_tax(
            profile,
            strategy,
            pack,
            rules_version_label=rules_version_label,
        )
        if not out.compliance.passed or out.tax_computation is None:
            continue
        tax = Decimal(out.tax_computation.total_tax)
        passing.append((spec, out, tax))

    gross = profile.annual_gross_income
    passing.sort(
        key=lambda row: _sort_tuple(
            body.rank_by,
            total_tax=row[2],
            gross=gross,
            candidate_id=row[0].candidate_id,
        ),
    )

    baseline_tax: Decimal | None = None
    baseline_row: tuple[TaxOptBStrategyCandidateSpecV1, TaxOptBComputeTaxResponseV1, Decimal] | None = None
    for spec, out, tax in passing:
        if spec.candidate_id == baseline_id:
            baseline_tax = tax
            baseline_row = (spec, out, tax)
            break

    top = list(passing[: body.top_k])
    top_ids = {t[0].candidate_id for t in top}
    if (
        baseline_row is not None
        and baseline_id not in top_ids
        and len(top) == body.top_k
        and body.top_k >= 1
    ):
        top = top[:-1] + [baseline_row]
    top.sort(
        key=lambda row: _sort_tuple(
            body.rank_by,
            total_tax=row[2],
            gross=gross,
            candidate_id=row[0].candidate_id,
        ),
    )
    rows_out: list[TaxOptBSearchStrategyRowV1] = []
    for rank_idx, (spec, out, tax) in enumerate(top, start=1):
        delta_str: str | None = None
        if baseline_tax is not None:
            delta_str = str(_q1(tax - baseline_tax))
        eff_s = _effective_rate_str(tax, gross)
        detail = out if body.include_result_detail else None
        tc = out.tax_computation
        assert tc is not None
        applied = _applied_relief_summary(out.compliance)
        disp = display_name_for_subset(spec.included_relief_codes, ordered, yaml_labels)
        metrics = (
            build_search_metrics(tc, gross, tax, baseline_tax, eff_s)
            if body.include_result_detail
            else None
        )
        breakdown = (
            build_search_tax_breakdown(fin, tc, baseline_tax, tax, gross)
            if body.include_result_detail
            else None
        )
        opt_sum, rule_sum, detail_ex = build_row_explainability(
            display_name=disp,
            rank=rank_idx,
            included_relief_codes=spec.included_relief_codes,
            grid_reliefs=ordered,
            compliance=out.compliance,
            tc=tc,
            pack=pack,
            applied_summary=applied,
            baseline_tax=baseline_tax,
            row_tax=tax,
            gross=gross,
            yaml_labels=yaml_labels,
        )
        trace = build_rule_trace(out.compliance, pack)
        rows_out.append(
            TaxOptBSearchStrategyRowV1(
                candidate_id=spec.candidate_id,
                label=spec.label,
                display_name=disp,
                rank=rank_idx,
                total_tax=str(tax),
                effective_rate=eff_s,
                delta_total_tax_vs_baseline=delta_str,
                metrics=metrics,
                breakdown=breakdown,
                optimization_summary=opt_sum,
                rule_summary=rule_sum,
                detailed_explanations=detail_ex,
                rule_trace=trace,
                applied_relief_summary=applied,
                included_relief_codes=list(spec.included_relief_codes),
                result=detail,
            ),
        )

    best_id = rows_out[0].candidate_id if rows_out else None

    comparison_summary: str | None = None
    if rows_out and baseline_row is not None and baseline_tax is not None:
        bspec, _bout, _bt = baseline_row
        baseline_name = display_name_for_subset(bspec.included_relief_codes, ordered, yaml_labels)
        comparison_summary = comparison_summary_text(
            baseline_name=baseline_name,
            best_name=rows_out[0].display_name,
            baseline_tax=baseline_tax,
            best_tax=Decimal(rows_out[0].total_tax),
        )

    traceability = TaxOptBSearchTraceabilityV1(
        grid_version=SEARCH_GRID_VERSION,
        search_space_id=space_id,
        rules_version_label=rules_version_label,
        ruleset_assessment_year=pack.assessment_year,
    )

    n_specs = len(specs)
    n_pass = len(passing)
    optimization_meta = TaxOptBSearchOptimizationMetaV1(
        strategies_evaluated=n_specs,
        legal_strategies_count=n_pass,
        rejected_strategies_count=n_specs - n_pass,
        optimization_mode="deterministic_grid_enumeration",
        search_space_description="MVP max-cap subsets (2^n)",
        optimization_objective=(
            "minimize_effective_tax_rate" if body.rank_by == "effective_rate" else "minimize_total_tax"
        ),
        reproducibility_id=space_id,
    )

    top_rank_explanation = None
    if rows_out and rows_out[0].rank == 1:
        _spec_first, tout_first, _tax_first = top[0]
        top_tc = tout_first.tax_computation
        assert top_tc is not None
        baseline_tc = None
        if baseline_row is not None:
            _bspec, bout, _btax = baseline_row
            baseline_tc = bout.tax_computation
        top_rank_explanation = build_top_rank_explanation(
            rank_by=body.rank_by,
            display_name=rows_out[0].display_name,
            top_tc=top_tc,
            baseline_tc=baseline_tc,
            applied_summary=rows_out[0].applied_relief_summary,
            yaml_labels=yaml_labels,
        )

    return TaxOptBSearchStrategiesResponseV1(
        profile=profile,
        grid_version=SEARCH_GRID_VERSION,
        search_space_id=space_id,
        candidates_evaluated=len(specs),
        passing_count=len(passing),
        baseline_candidate_id=baseline_id,
        best_candidate_id=best_id,
        comparison_summary=comparison_summary,
        traceability=traceability,
        optimization_meta=optimization_meta,
        top_rank_explanation=top_rank_explanation,
        rows=rows_out,
        research_disclaimer=RESEARCH_DISCLAIMER,
        rules_version_label=rules_version_label,
        explanations=None,
    )


__all__ = [
    "enumerate_candidate_specs",
    "search_space_id",
    "search_strategies_from_financial_inputs",
]
