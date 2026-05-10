"""Orchestration entrypoints for FR5 explanation bundles."""

from __future__ import annotations

from tax_opt_b_app.services.tax_opt_b_explanation_provider import ExplanationDetail
from tax_opt_b_app.services.tax_opt_b_template_explanation_provider import (
    TemplateExplanationProviderV1,
    get_template_explanation_provider,
)
from tax_opt_b_app.tax_opt_b_schemas_compare_v1 import TaxOptBCompareStrategiesResponseV1
from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import (
    TaxOptBExplanationBulletKindV1,
    TaxOptBExplanationBulletV1,
    TaxOptBExplanationBundleV1,
    TaxOptBExplanationDetailLevelV1,
    TaxOptBExplanationSectionV1,
)
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import TaxOptBSearchStrategiesResponseV1
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1


def build_compute_explanations(
    resp: TaxOptBComputeTaxResponseV1,
    *,
    detail: ExplanationDetail = "summary",
    provider: TemplateExplanationProviderV1 | None = None,
) -> TaxOptBExplanationBundleV1:
    p = provider or get_template_explanation_provider()
    return p.explain_compute_response(resp, detail=detail)


def build_compare_explanations(
    resp: TaxOptBCompareStrategiesResponseV1,
    *,
    detail: ExplanationDetail = "summary",
    provider: TemplateExplanationProviderV1 | None = None,
) -> TaxOptBExplanationBundleV1:
    p = provider or get_template_explanation_provider()
    return p.explain_compare_response(resp, detail=detail)


def build_search_explanations(
    resp: TaxOptBSearchStrategiesResponseV1,
    *,
    detail: ExplanationDetail = "summary",
) -> TaxOptBExplanationBundleV1:
    """Short template narrative for strategy search (enumerated grid)."""
    lines = [
        f"Explainable rule-based search ({resp.grid_version}): evaluated {resp.candidates_evaluated} "
        f"candidates; {resp.passing_count} passed compliance filtering.",
        f"Internal baseline id: {resp.baseline_candidate_id}.",
    ]
    if resp.comparison_summary:
        lines.append(resp.comparison_summary)
    if resp.rows:
        best = resp.rows[0]
        lines.append(
            f"Best in this response: «{best.display_name}» ({best.candidate_id}) — "
            f"total tax LKR {best.total_tax}"
            + (f" (effective rate {best.effective_rate})" if best.effective_rate else "")
            + ".",
        )
        if best.metrics and best.metrics.tax_savings_vs_baseline_lkr is not None:
            lines.append(
                f"Tax saving vs baseline (LKR): {best.metrics.tax_savings_vs_baseline_lkr}.",
            )
    else:
        lines.append("No strategy in the grid passed compliance for this profile.")

    summary = " ".join(lines)
    tier = (
        TaxOptBExplanationDetailLevelV1.DETAILED
        if detail == "detailed"
        else TaxOptBExplanationDetailLevelV1.SUMMARY
    )
    bullets = [
        TaxOptBExplanationBulletV1(
            kind=TaxOptBExplanationBulletKindV1.SUMMARY,
            text=summary,
            source_refs=["search:grid", f"search_space:{resp.search_space_id}"],
        ),
    ]
    if detail == "detailed" and resp.rows:
        for row in resp.rows[:12]:
            bullets.append(
                TaxOptBExplanationBulletV1(
                    kind=TaxOptBExplanationBulletKindV1.COMPARISON,
                    text=(
                        f"Rank {row.rank}: «{row.display_name}» ({row.candidate_id}) — LKR {row.total_tax}"
                        + (
                            f"; Δ vs baseline {row.delta_total_tax_vs_baseline}"
                            if row.delta_total_tax_vs_baseline
                            else ""
                        )
                    ),
                    source_refs=[f"search:{row.candidate_id}"],
                ),
            )

    return TaxOptBExplanationBundleV1(
        summary=summary,
        sections=[
            TaxOptBExplanationSectionV1(
                title="Strategy search (rule-only)",
                bullets=bullets,
            ),
        ],
        detail_level=tier,
        provenance={"engine": "template_search_v1", "deterministic": True},
        rules_version_label=resp.rules_version_label,
        ruleset_assessment_year=resp.profile.tax_year,
    )


__all__ = ["build_compare_explanations", "build_compute_explanations", "build_search_explanations"]
