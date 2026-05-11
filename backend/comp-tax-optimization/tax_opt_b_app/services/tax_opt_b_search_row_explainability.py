"""Per-row deterministic explanations for Strategy Explorer (explainable rule-based DSS).

Builds structured summaries, rule trace, and metrics from existing compliance and
tax_computation outputs—no changes to the rule engine or slab implementation.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBRulePack, TaxOptBRuleSpec
from tax_opt_b_app.services.tax_opt_b_strategy_display_names import relief_label
from tax_opt_b_app.tax_opt_b_schemas_compliance_v1 import TaxOptBComplianceResultV1
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import (
    TaxOptBAppliedReliefSummaryEntryV1,
    TaxOptBRuleTraceEntryV1,
    TaxOptBSearchStrategyMetricsV1,
    TaxOptBSearchTaxBreakdownV1,
    TaxOptBStrategySearchRankByV1,
    TaxOptBTopRankExplanationV1,
)
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBTaxComputationV1


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _template(templates: dict[str, str], key: str, default: str) -> str:
    return (templates.get(key) or default).strip()


def _format_safe(template: str, **kwargs: object) -> str:
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template


def pack_template_dict(pack: TaxOptBRulePack) -> dict[str, str]:
    return dict(pack.search_explanation_templates)


def build_search_tax_breakdown(
    fin: TaxOptBFinancialInputsV1,
    tc: TaxOptBTaxComputationV1,
    baseline_tax: Decimal | None,
    row_tax: Decimal,
    gross: Decimal,
) -> TaxOptBSearchTaxBreakdownV1:
    pr = Decimal(tc.personal_relief_annual)
    ded = Decimal(tc.total_allowed_deductions)
    total_reliefs = pr + ded
    savings: str | None = None
    if baseline_tax is not None:
        s = baseline_tax - row_tax
        savings = str(_q1(s)) if s > 0 else "0"
    eff_pct: str | None = None
    if gross > 0:
        pct = (row_tax / gross * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        eff_pct = f"{pct}%"
    return TaxOptBSearchTaxBreakdownV1(
        employment_income_lkr=str(fin.annual_salary_income),
        business_income_lkr=str(fin.annual_business_income),
        investment_income_lkr=str(getattr(fin, "annual_investment_income", Decimal("0"))),
        other_income_lkr=str(fin.annual_other_income),
        gross_income_lkr=tc.annual_gross_income,
        assessable_income_lkr=tc.income_basis_before_personal_relief,
        personal_relief_lkr=tc.personal_relief_annual,
        total_statutory_deductions_lkr=tc.total_allowed_deductions,
        total_reliefs_lkr=str(_q1(total_reliefs)),
        taxable_income_lkr=tc.taxable_after_deductions,
        total_tax_lkr=tc.total_tax,
        effective_tax_rate=eff_pct,
        tax_savings_vs_baseline_lkr=savings,
    )


def build_search_metrics(
    tc: TaxOptBTaxComputationV1,
    gross: Decimal,
    row_tax: Decimal,
    baseline_tax: Decimal | None,
    effective_rate_str: str | None,
) -> TaxOptBSearchStrategyMetricsV1:
    ded = tc.total_allowed_deductions
    savings: str | None = None
    if baseline_tax is not None:
        s = baseline_tax - row_tax
        if s > 0:
            savings = str(_q1(s))
        else:
            savings = "0"
    return TaxOptBSearchStrategyMetricsV1(
        gross_income=tc.annual_gross_income,
        income_basis_before_personal_relief=tc.income_basis_before_personal_relief,
        personal_relief_annual=tc.personal_relief_annual,
        taxable_after_personal_relief=tc.taxable_after_personal_relief,
        total_statutory_deductions=ded,
        total_relief_amount=ded,
        taxable_income_before_slabs=tc.taxable_after_deductions,
        final_tax=tc.total_tax,
        effective_tax_rate=effective_rate_str,
        tax_savings_vs_baseline_lkr=savings,
    )


def build_rule_trace(
    compliance: TaxOptBComplianceResultV1,
    pack: TaxOptBRulePack,
) -> list[TaxOptBRuleTraceEntryV1]:
    cap_types = frozenset({"deduction_cap", "charitable_donation_cap", "retirement_contribution_cap"})
    by_relief: dict[str, TaxOptBRuleSpec] = {}
    for r in pack.rules:
        if r.rule_type in cap_types and r.relief_code:
            rc = r.relief_code.strip()
            if rc not in by_relief:
                by_relief[rc] = r

    out: list[TaxOptBRuleTraceEntryV1] = []
    for _key, val in compliance.applied_relief.items():
        if not isinstance(val, dict):
            continue
        rc = str(val.get("relief_code", _key)).strip()
        spec = by_relief.get(rc)
        if not spec:
            continue
        allowed = val.get("allowed", "")
        cap = val.get("cap", "")
        claimed = val.get("claimed", "")
        summary = (
            f"{spec.description.strip()} Allowed LKR {allowed} (claimed LKR {claimed}, cap LKR {cap})."
        )
        lbl = relief_label(rc, dict(pack.relief_display_names))
        desc = spec.description.strip()
        short = f"{lbl} applied" if lbl else (desc[:120] + ("…" if len(desc) > 120 else ""))
        out.append(
            TaxOptBRuleTraceEntryV1(
                rule_id=spec.rule_id,
                relief_code=rc,
                kind="applied_cap",
                outcome="passed",
                short_label=short[:512],
                category="relief_cap",
                summary=summary[:2000],
                reference=spec.reference[:2000] if spec.reference else "",
            ),
        )
    out.sort(key=lambda e: e.rule_id)
    out.append(
        TaxOptBRuleTraceEntryV1(
            rule_id="search:compliance_bundle",
            relief_code=None,
            kind="meta",
            outcome="passed",
            short_label="Compliance validation (no violations)",
            category="compliance_meta",
            summary="All evaluated cap rules passed for this strategy; violations empty.",
            reference="",
        ),
    )
    return out


def build_top_rank_explanation(
    *,
    rank_by: TaxOptBStrategySearchRankByV1,
    display_name: str,
    top_tc: TaxOptBTaxComputationV1,
    baseline_tc: TaxOptBTaxComputationV1 | None,
    applied_summary: list[TaxOptBAppliedReliefSummaryEntryV1],
    yaml_labels: dict[str, str],
) -> TaxOptBTopRankExplanationV1:
    if rank_by == "effective_rate":
        obj = "The search objective is to minimize effective tax rate (total tax divided by gross income)."
        obj_short = "minimize effective tax rate"
    else:
        obj = "The search objective is to minimize total annual tax (LKR)."
        obj_short = "minimize total tax"

    bullets: list[str] = [obj]
    bullets.append(
        "Among passing strategies in this ranked table (after top_k selection and the same deterministic "
        "sort used for the full search), this candidate is first under the selected objective; ties are "
        "broken by the cap_subset bitmask (lower mask wins).",
    )

    def _allowed_key(e: TaxOptBAppliedReliefSummaryEntryV1) -> Decimal:
        if not e.allowed or not str(e.allowed).strip():
            return Decimal("0")
        try:
            return Decimal(str(e.allowed).strip())
        except Exception:
            return Decimal("0")

    sorted_rel = sorted(applied_summary, key=_allowed_key, reverse=True)
    top_labels: list[str] = []
    for e in sorted_rel[:3]:
        if _allowed_key(e) <= 0:
            continue
        top_labels.append(relief_label(e.relief_code, yaml_labels))
    if top_labels:
        bullets.append(
            "Largest allowed statutory reliefs on this row (by allowed amount): "
            + ", ".join(top_labels)
            + ".",
        )
    else:
        bullets.append("No statutory relief caps materially reduced taxable income on this row.")

    top_taxable = top_tc.taxable_after_deductions
    if baseline_tc is not None:
        base_taxable = baseline_tc.taxable_after_deductions
        bullets.append(
            f"Taxable income before slab bands is LKR {top_taxable} for this strategy vs LKR {base_taxable} "
            f"for the baseline, shaping the final tax outcome.",
        )
    else:
        bullets.append(
            f"Taxable income before slab bands is LKR {top_taxable} for this strategy.",
        )

    bullets.append(
        "Compliance: passed all evaluated cap rules for this strategy (violations empty).",
    )

    headline = (
        f"Rank #1 «{display_name}» is the legal optimum in this response under {obj_short}, "
        "with a transparent rule trace and deterministic enumeration."
    )
    return TaxOptBTopRankExplanationV1(headline=headline, bullets=bullets)


def build_row_explainability(
    *,
    display_name: str,
    rank: int,
    included_relief_codes: tuple[str, ...],
    grid_reliefs: tuple[str, ...],
    compliance: TaxOptBComplianceResultV1,
    tc: TaxOptBTaxComputationV1,
    pack: TaxOptBRulePack,
    applied_summary: list[TaxOptBAppliedReliefSummaryEntryV1],
    baseline_tax: Decimal | None,
    row_tax: Decimal,
    gross: Decimal,
    yaml_labels: dict[str, str],
) -> tuple[str | None, list[str], list[str]]:
    """Return (optimization_summary, rule_summary bullets, detailed_explanations)."""
    tmpl = pack_template_dict(pack)
    assessment_year = pack.assessment_year

    rule_summary: list[str] = []
    detailed: list[str] = []

    passed_t = _template(
        tmpl,
        "passed_compliance",
        "Strategy passed all compliance checks for assessment year {assessment_year}.",
    )
    rule_summary.append(_format_safe(passed_t, assessment_year=assessment_year))

    included_set = frozenset(included_relief_codes)
    omitted = [c for c in grid_reliefs if c not in included_set]
    if omitted:
        o_labels = ", ".join(relief_label(c, yaml_labels) for c in sorted(omitted))
        ot = _template(
            tmpl,
            "omitted_reliefs",
            "Reliefs not claimed in this strategy: {relief_list}.",
        )
        rule_summary.append(_format_safe(ot, relief_list=o_labels))
        detailed.append(
            f"This candidate does not claim: {o_labels}. The search grid only evaluates "
            "subsets of statutory reliefs at MVP maximum amounts.",
        )

    if applied_summary:
        parts: list[str] = []
        for e in applied_summary:
            lbl = relief_label(e.relief_code, yaml_labels)
            cap_s = (e.cap or "").strip()
            allowed_s = (e.allowed or "").strip()
            claimed_s = (e.claimed or "").strip()
            parts.append(f"{lbl} (allowed LKR {allowed_s or '0'})")
            if cap_s and allowed_s and cap_s == allowed_s:
                rule_summary.append(f"{lbl} applied at the statutory ceiling (LKR {cap_s}).")
            elif cap_s and claimed_s:
                ct = _template(
                    tmpl,
                    "capped_relief",
                    "{relief_label}: claimed LKR {claimed}, cap LKR {cap}, allowed LKR {allowed}.",
                )
                rule_summary.append(
                    _format_safe(
                        ct,
                        relief_label=lbl,
                        claimed=claimed_s,
                        cap=cap_s,
                        allowed=allowed_s,
                    ),
                )
            else:
                rule_summary.append(f"{lbl}: allowed LKR {allowed_s or '0'}.")
        detailed.append("Applied statutory reliefs: " + "; ".join(parts) + ".")

    detailed.append(
        f"Personal relief LKR {tc.personal_relief_annual} applied before deductions. "
        f"Taxable income after deductions (before slab bands): LKR {tc.taxable_after_deductions}. "
        f"Total tax LKR {tc.total_tax}.",
    )

    if baseline_tax is not None:
        savings = baseline_tax - row_tax
        if savings > 0 and gross > 0:
            pct = (savings / baseline_tax * Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            ) if baseline_tax > 0 else Decimal("0")
            st = _template(
                tmpl,
                "savings_vs_baseline",
                "Tax saving vs baseline: LKR {savings} ({pct}% of baseline tax).",
            )
            detailed.append(_format_safe(st, savings=str(_q1(savings)), pct=str(pct)))
        elif savings <= 0:
            detailed.append(
                "This strategy does not reduce tax below the selected baseline for this profile.",
            )

    slab_n = len(tc.slab_slices)
    if slab_n:
        detailed.append(
            f"Tax computed across {slab_n} progressive slab band(s) per the active rules pack.",
        )

    opt_one = _template(
        tmpl,
        "row_summary",
        "Rank {rank}: {display_name} — final tax LKR {final_tax}.",
    )
    optimization_summary = _format_safe(
        opt_one,
        rank=rank,
        display_name=display_name,
        final_tax=tc.total_tax,
    )

    return optimization_summary, rule_summary, detailed


def comparison_summary_text(
    *,
    baseline_name: str,
    best_name: str,
    baseline_tax: Decimal,
    best_tax: Decimal,
) -> str:
    """Single narrative for response.comparison_summary."""
    if baseline_tax <= 0:
        return (
            f"Baseline «{baseline_name}» has LKR {baseline_tax} tax; best returned strategy "
            f"«{best_name}» has LKR {best_tax}. Both use the same deterministic rules pack."
        )
    savings = baseline_tax - best_tax
    pct = (savings / baseline_tax * Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    if savings > 0:
        return (
            f"Compared to baseline «{baseline_name}» (LKR {baseline_tax} tax), "
            f"«{best_name}» reduces annual tax by LKR {_q1(savings)} "
            f"({pct}% relative reduction)."
        )
    return (
        f"Baseline «{baseline_name}» (LKR {baseline_tax} tax) is equal to or lower tax than "
        f"«{best_name}» (LKR {best_tax}) among returned strategies."
    )


__all__ = [
    "build_row_explainability",
    "build_rule_trace",
    "build_search_metrics",
    "build_search_tax_breakdown",
    "build_top_rank_explanation",
    "comparison_summary_text",
    "pack_template_dict",
]
