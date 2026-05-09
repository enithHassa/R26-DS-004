"""Function 2 — rule-only strategy search (enumerated grid, passing strategies only)."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import (
    TaxOptBExplainRequestFlagsV1,
    TaxOptBExplanationBundleV1,
)
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBReliefClaimV1, TaxOptBStrategyProposalV1
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1

TaxOptBStrategySearchRankByV1 = Literal["total_tax", "effective_rate"]

SEARCH_GRID_VERSION = "mvp_max_caps_subset_v1"


class TaxOptBStrategyCandidateSpecV1(BaseModel):
    """Discrete search knobs for one grid point (not sent to Function 1 directly)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    grid_version: str = Field(
        default=SEARCH_GRID_VERSION,
        description="Grid definition; bump when enumeration logic changes.",
    )
    included_relief_codes: tuple[str, ...] = Field(
        description="Reliefs claimed at MVP max cap for this candidate (sorted).",
    )
    candidate_id: str = Field(
        min_length=1,
        max_length=96,
        description="Stable id for UI/API (e.g. cap_subset_42).",
    )
    label: str = Field(min_length=1, max_length=512)

    def to_strategy_proposal(self, amounts_by_code: dict[str, Decimal]) -> TaxOptBStrategyProposalV1:
        """Build evaluator input using precomputed max claim amounts (LKR) per relief_code."""
        claims: list[TaxOptBReliefClaimV1] = []
        for code in self.included_relief_codes:
            amt = amounts_by_code.get(code)
            if amt is None:
                continue
            claims.append(TaxOptBReliefClaimV1(relief_code=code, claimed_amount_annual=amt))
        return TaxOptBStrategyProposalV1(claims=claims)


class TaxOptBSearchStrategiesFromFinancialInputsRequestV1(
    TaxOptBFinancialInputsV1,
    TaxOptBExplainRequestFlagsV1,
):
    """Structured intake → gross profile; enumeration ignores form deductions (grid is cap subsets)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    top_k: int = Field(default=10, ge=1, le=64, description="Max passing strategies to return.")
    rank_by: TaxOptBStrategySearchRankByV1 = Field(
        default="total_tax",
        description="Primary sort: total_tax or effective_rate (tax / annual_gross_income).",
    )
    max_candidates: int = Field(
        default=500,
        ge=1,
        le=10_000,
        description="Abort if the grid exceeds this count (transparency guard).",
    )
    baseline_candidate_id: str | None = Field(
        default=None,
        description="Defaults to cap_subset_0 (no claims). Must match a generated candidate_id.",
    )
    include_result_detail: bool = Field(
        default=True,
        description="When false, rows omit full compliance/tax payload.",
    )


class TaxOptBSearchStrategiesMlRankRequestV1(TaxOptBSearchStrategiesFromFinancialInputsRequestV1):
    """Same search request as Function 2 plus ML bundle options (Function 3).

    Ranking reorders **only** strategies that already passed compliance + tax computation.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    feature_version: str | None = Field(
        default=None,
        description="If set, must match feature_version in best_model_summary.json or request fails.",
    )
    model_bundle_path: str | None = Field(
        default=None,
        max_length=2048,
        description="Optional directory override for artifacts (best_model_summary.json + joblib).",
    )
    max_ml_candidates: int = Field(
        default=10_000,
        ge=1,
        le=50_000,
        description="Reject with 422 when passing count exceeds this (latency / batch safety).",
    )


class TaxOptBAppliedReliefSummaryEntryV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    relief_code: str
    allowed: str | None = Field(default=None)
    cap: str | None = Field(default=None)
    claimed: str | None = Field(default=None)


class TaxOptBSearchTaxBreakdownV1(BaseModel):
    """Dissertation-oriented income and tax path (from financial inputs + tax computation; additive to metrics)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    employment_income_lkr: str = Field(description="From financial_inputs.annual_salary_income (LKR, string decimal).")
    business_income_lkr: str = Field(description="From financial_inputs.annual_business_income.")
    other_income_lkr: str = Field(description="From financial_inputs.annual_other_income.")
    gross_income_lkr: str = Field(description="Echo annual gross (same as tax_computation.annual_gross_income / profile).")
    assessable_income_lkr: str = Field(
        description="Income basis before personal relief (tax_computation.income_basis_before_personal_relief).",
    )
    personal_relief_lkr: str
    total_statutory_deductions_lkr: str = Field(
        description="Sum of allowed statutory deductions (tax_computation.total_allowed_deductions).",
    )
    total_reliefs_lkr: str = Field(
        description=(
            "MVP: personal_relief_annual + total_allowed_deductions (single UI line for “total reliefs”; "
            "not double-counted with separate personal/statutory rows)."
        ),
    )
    taxable_income_lkr: str = Field(
        description="Taxable income before slab bands (tax_computation.taxable_after_deductions).",
    )
    total_tax_lkr: str
    effective_tax_rate: str | None = Field(
        default=None,
        description="Percent string e.g. '12.34%' when gross > 0; else null.",
    )
    tax_savings_vs_baseline_lkr: str | None = Field(
        default=None,
        description="max(baseline_tax - row_tax, 0) stringified; null if baseline unknown.",
    )


class TaxOptBSearchStrategyMetricsV1(BaseModel):
    """Tax breakdown for Strategy Explorer (values mirror ``TaxOptBTaxComputationV1``; no extra math)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    gross_income: str = Field(description="Same as tax_computation.annual_gross_income.")
    income_basis_before_personal_relief: str
    personal_relief_annual: str
    taxable_after_personal_relief: str
    total_statutory_deductions: str = Field(
        description="Total allowed statutory deductions (tax_computation.total_allowed_deductions).",
    )
    total_relief_amount: str = Field(
        description="Alias for total_statutory_deductions (dissertation wording).",
    )
    taxable_income_before_slabs: str = Field(
        description="Taxable income before progressive slabs (tax_computation.taxable_after_deductions).",
    )
    final_tax: str
    effective_tax_rate: str | None = Field(
        default=None,
        description="final_tax / gross_income when gross > 0; else null.",
    )
    tax_savings_vs_baseline_lkr: str | None = Field(
        default=None,
        description="max(baseline_tax - final_tax, 0) in LKR; null if baseline unknown.",
    )


TaxOptBRuleTraceKindV1 = Literal["applied_cap", "meta"]


TaxOptBRuleTraceOutcomeV1 = Literal["passed", "failed"]
TaxOptBRuleTraceCategoryV1 = Literal["relief_cap", "compliance_meta"]


class TaxOptBRuleTraceEntryV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    rule_id: str
    relief_code: str | None = None
    kind: TaxOptBRuleTraceKindV1 = "applied_cap"
    outcome: TaxOptBRuleTraceOutcomeV1 = Field(
        default="passed",
        description="Search rows: always passed; reserved for compare/reuse.",
    )
    short_label: str = Field(
        default="",
        max_length=512,
        description="Compact label for UI (e.g. relief applied).",
    )
    category: TaxOptBRuleTraceCategoryV1 | None = Field(
        default=None,
        description="Optional grouping for visualization.",
    )
    summary: str = Field(max_length=2_000)
    reference: str = Field(default="", max_length=2_000)


class TaxOptBSearchStrategyRowV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    candidate_id: str
    label: str = Field(description="Legacy debug label (machine-oriented); prefer display_name for UI.")
    display_name: str = Field(description="Human-readable strategy name for research UI.")
    rank: int = Field(ge=1, description="1-based among returned passing rows after top_k slice.")
    total_tax: str
    effective_rate: str | None = Field(
        default=None,
        description="Decimal string ratio tax/gross when gross > 0; null when gross is 0.",
    )
    delta_total_tax_vs_baseline: str | None = Field(
        default=None,
        description="LKR vs baseline when baseline passed; else null.",
    )
    metrics: TaxOptBSearchStrategyMetricsV1 | None = Field(
        default=None,
        description="Structured tax breakdown; null when include_result_detail was false.",
    )
    breakdown: TaxOptBSearchTaxBreakdownV1 | None = Field(
        default=None,
        description="Income source + assessable/taxable path; null when include_result_detail was false.",
    )
    optimization_summary: str | None = Field(
        default=None,
        description="One-line deterministic explanation of this strategy outcome.",
    )
    rule_summary: list[str] = Field(
        default_factory=list,
        description="Short bullet strings for table expanders.",
    )
    detailed_explanations: list[str] = Field(
        default_factory=list,
        description="Longer multi-sentence explanations (deterministic templates).",
    )
    rule_trace: list[TaxOptBRuleTraceEntryV1] = Field(default_factory=list)
    applied_relief_summary: list[TaxOptBAppliedReliefSummaryEntryV1] = Field(default_factory=list)
    included_relief_codes: list[str] = Field(default_factory=list)
    result: TaxOptBComputeTaxResponseV1 | None = None
    rule_only_rank: int | None = Field(
        default=None,
        ge=1,
        description="1-based rank under rule-only sort among all passing strategies (Function 3).",
    )
    ml_score: str | None = Field(
        default=None,
        description="Regressor output used for ML-assisted ordering (string for JSON decimal safety).",
    )
    ml_assist_rank: int | None = Field(
        default=None,
        ge=1,
        description="1-based rank after ML-assisted ordering within returned rows (matches rank in ML mode).",
    )
    deterministic_rank: int | None = Field(
        default=None,
        ge=1,
        description="Echo of rule_only_rank for permutation-safe auditing (Function 3).",
    )


class TaxOptBSearchMlMetaV1(BaseModel):
    """Provenance for ML-assisted ranking (rules remain authoritative for tax legality)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    model_id: str = Field(description="Identifier from training run / artifact manifest.")
    feature_version: str
    training_timestamp: str = Field(description="ISO-8601 timestamp from training manifest.")
    artifact_sha256: str | None = Field(
        default=None,
        description="Optional checksum of the estimator joblib on disk at load time.",
    )
    artifact_path_used: str = Field(
        description="Resolved filesystem path to the loaded estimator artifact.",
    )
    synthetic_training_data_disclaimer: str
    compliance_assertion: str = Field(
        description="Fixed research disclosure that ML did not bypass compliance.",
    )
    inference_latency_ms: float = Field(ge=0.0)


class TaxOptBSearchTraceabilityV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    grid_version: str
    search_space_id: str
    rules_version_label: str | None = None
    ruleset_assessment_year: str | None = None


class TaxOptBSearchOptimizationMetaV1(BaseModel):
    """Transparent optimization metadata for dissertation / audit UI."""

    model_config = ConfigDict(str_strip_whitespace=True)

    strategies_evaluated: int = Field(ge=0)
    legal_strategies_count: int = Field(ge=0)
    rejected_strategies_count: int = Field(ge=0)
    optimization_mode: str = Field(
        description="e.g. deterministic_grid_enumeration; aligns with active grid semantics.",
    )
    search_space_description: str
    optimization_objective: str = Field(
        description="minimize_total_tax or minimize_effective_tax_rate from rank_by.",
    )
    reproducibility_id: str = Field(description="Echo of search_space_id.")


class TaxOptBTopRankExplanationV1(BaseModel):
    """Deterministic “why rank #1” narrative (response-level; not duplicated per row)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    headline: str
    bullets: list[str] = Field(default_factory=list)


class TaxOptBSearchStrategiesResponseV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    profile: TaxOptBProfileV1
    grid_version: str
    search_space_id: str = Field(description="Short hash for reproducibility (profile + grid version + relief order).")
    candidates_evaluated: int
    passing_count: int
    baseline_candidate_id: str
    best_candidate_id: str | None = Field(
        default=None,
        description="First row after ranking among returned rows; null if no passing strategies.",
    )
    comparison_summary: str | None = Field(
        default=None,
        description="Deterministic baseline vs best narrative for dissertation demos.",
    )
    traceability: TaxOptBSearchTraceabilityV1 | None = None
    optimization_meta: TaxOptBSearchOptimizationMetaV1 | None = Field(
        default=None,
        description="Counts and objective metadata for transparency.",
    )
    top_rank_explanation: TaxOptBTopRankExplanationV1 | None = Field(
        default=None,
        description="Present when at least one passing row and rank 1 exists in this response.",
    )
    rows: list[TaxOptBSearchStrategyRowV1]
    research_disclaimer: str
    rules_version_label: str | None = None
    explanations: TaxOptBExplanationBundleV1 | None = None
    ml_meta: TaxOptBSearchMlMetaV1 | None = Field(
        default=None,
        description="Present for Function 3 ML-assisted responses only.",
    )


__all__ = [
    "SEARCH_GRID_VERSION",
    "TaxOptBAppliedReliefSummaryEntryV1",
    "TaxOptBRuleTraceCategoryV1",
    "TaxOptBRuleTraceEntryV1",
    "TaxOptBRuleTraceKindV1",
    "TaxOptBRuleTraceOutcomeV1",
    "TaxOptBSearchOptimizationMetaV1",
    "TaxOptBSearchStrategiesFromFinancialInputsRequestV1",
    "TaxOptBSearchStrategiesMlRankRequestV1",
    "TaxOptBSearchStrategiesResponseV1",
    "TaxOptBSearchMlMetaV1",
    "TaxOptBSearchStrategyMetricsV1",
    "TaxOptBSearchStrategyRowV1",
    "TaxOptBSearchTaxBreakdownV1",
    "TaxOptBSearchTraceabilityV1",
    "TaxOptBStrategyCandidateSpecV1",
    "TaxOptBStrategySearchRankByV1",
    "TaxOptBTopRankExplanationV1",
]
