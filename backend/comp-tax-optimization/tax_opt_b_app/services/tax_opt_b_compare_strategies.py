"""FR6 — compare multiple strategy proposals for one profile (ranking + baseline deltas)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBRulePack
from tax_opt_b_app.services.tax_opt_b_tax_computation import (
    RESEARCH_DISCLAIMER,
    run_compliance_and_compute_tax,
)
from tax_opt_b_app.tax_opt_b_schemas_compare_v1 import (
    TaxOptBCompareStrategiesResponseV1,
    TaxOptBCompareStrategyResultRowV1,
)
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _passing_sort_key(
    row: tuple[int, str, str | None, TaxOptBComputeTaxResponseV1],
) -> tuple[Decimal, int]:
    idx, _vid, _lab, out = row
    assert out.tax_computation is not None
    return Decimal(out.tax_computation.total_tax), idx


def compare_strategies(
    profile: TaxOptBProfileV1,
    variants: list[tuple[str, str | None, TaxOptBStrategyProposalV1]],
    pack: TaxOptBRulePack,
    *,
    baseline_variant_id: str | None = None,
    rules_version_label: str | None = None,
    include_result_detail: bool = True,
) -> TaxOptBCompareStrategiesResponseV1:
    """Run compliance + tax for each variant; rank passing rows by ascending total_tax.

    ``variants`` is ``(variant_id, label | None, strategy)`` in request order.

    Callers should validate variant count, ids, and baseline id (see compare request models).
    """
    indexed_results: list[
        tuple[int, str, str | None, TaxOptBComputeTaxResponseV1]
    ] = []
    for idx, (variant_id, label, strategy) in enumerate(variants):
        out = run_compliance_and_compute_tax(
            profile,
            strategy,
            pack,
            rules_version_label=rules_version_label,
        )
        indexed_results.append((idx, variant_id, label, out))

    passing: list[tuple[int, str, str | None, TaxOptBComputeTaxResponseV1]] = []
    failing: list[tuple[int, str, str | None, TaxOptBComputeTaxResponseV1]] = []
    for row in indexed_results:
        _i, _vid, _lab, out = row
        if out.compliance.passed and out.tax_computation is not None:
            passing.append(row)
        else:
            failing.append(row)

    passing.sort(key=_passing_sort_key)

    ordered = passing + failing

    baseline_tax: Decimal | None = None
    if baseline_variant_id is not None:
        for _i, vid, _lab, out in passing:
            if vid == baseline_variant_id and out.tax_computation is not None:
                baseline_tax = Decimal(out.tax_computation.total_tax)
                break
        # baseline requested but failed or missing → baseline_tax stays None

    rows_out: list[TaxOptBCompareStrategyResultRowV1] = []
    rank_counter = 0
    for _i, variant_id, label, out in ordered:
        passed = out.compliance.passed and out.tax_computation is not None
        total_tax_str: str | None = None
        delta_str: str | None = None
        violations = [v.rule_id for v in out.compliance.violations]
        rank: int | None = None

        if passed and out.tax_computation is not None:
            rank_counter += 1
            rank = rank_counter
            total_tax_str = out.tax_computation.total_tax
            if baseline_tax is not None:
                delta_str = str(_q1(Decimal(out.tax_computation.total_tax) - baseline_tax))

        rows_out.append(
            TaxOptBCompareStrategyResultRowV1(
                variant_id=variant_id,
                label=label,
                rank=rank,
                passed=passed,
                total_tax=total_tax_str,
                delta_total_tax_vs_baseline=delta_str,
                violation_rule_ids=violations,
                result=out if include_result_detail else None,
            ),
        )

    return TaxOptBCompareStrategiesResponseV1(
        profile=profile,
        baseline_variant_id=baseline_variant_id,
        rows=rows_out,
        research_disclaimer=RESEARCH_DISCLAIMER,
        rules_version_label=rules_version_label,
    )


__all__ = ["compare_strategies"]
