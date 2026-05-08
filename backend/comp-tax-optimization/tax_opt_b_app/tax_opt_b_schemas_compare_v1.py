"""FR6 — compare multiple strategies (profile or structured financial intake)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import (
    TaxOptBExplainRequestFlagsV1,
    TaxOptBExplanationBundleV1,
)
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import TaxOptBComputeTaxResponseV1

MAPPED_INTAKE_VARIANT_ID = "from_intake"


class TaxOptBStrategyVariantV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    variant_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Stable identifier for this strategy row (API + UI).",
    )
    label: str | None = Field(default=None, max_length=256)
    strategy: TaxOptBStrategyProposalV1


class TaxOptBCompareStrategiesRequestV1(TaxOptBExplainRequestFlagsV1):
    model_config = ConfigDict(str_strip_whitespace=True)

    profile: TaxOptBProfileV1
    variants: list[TaxOptBStrategyVariantV1] = Field(
        min_length=1,
        max_length=12,
        description="At most 12 scenarios per request to limit compute cost.",
    )
    baseline_variant_id: str | None = Field(
        default=None,
        description="When set, must equal one of ``variants[].variant_id``; used for tax deltas.",
    )
    include_result_detail: bool = Field(
        default=True,
        description=(
            "When false, each row omits ``result`` (full compliance/tax payload) "
            "to reduce response size; summary fields remain."
        ),
    )

    @model_validator(mode="after")
    def _unique_variant_ids_and_baseline(self) -> TaxOptBCompareStrategiesRequestV1:
        ids = [v.variant_id for v in self.variants]
        if len(ids) != len(set(ids)):
            raise ValueError("variants must have unique variant_id values")
        if self.baseline_variant_id is not None and self.baseline_variant_id not in set(ids):
            raise ValueError("baseline_variant_id must match a variant_id in variants")
        return self


class TaxOptBCompareStrategyResultRowV1(BaseModel):
    """One strategy outcome in compare-strategies response (FR6)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    variant_id: str
    label: str | None = None
    rank: int | None = Field(
        default=None,
        description="1-based rank among passing strategies (lowest tax first); null if compliance failed.",
    )
    passed: bool
    total_tax: str | None = Field(
        default=None,
        description="String LKR total when passed; null when failed.",
    )
    delta_total_tax_vs_baseline: str | None = Field(
        default=None,
        description=(
            "LKR difference vs baseline total_tax when baseline passed and this row passed; "
            "otherwise null (including when baseline failed or baseline_variant_id omitted)."
        ),
    )
    violation_rule_ids: list[str] = Field(
        default_factory=list,
        description="rule_id values from compliance violations when failed.",
    )
    result: TaxOptBComputeTaxResponseV1 | None = Field(
        default=None,
        description="Full compliance + tax when include_result_detail was true; otherwise null.",
    )


class TaxOptBCompareStrategiesResponseV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    profile: TaxOptBProfileV1
    baseline_variant_id: str | None = None
    rows: list[TaxOptBCompareStrategyResultRowV1]
    research_disclaimer: str
    rules_version_label: str | None = None
    explanations: TaxOptBExplanationBundleV1 | None = Field(
        default=None,
        description=(
            "Optional FR5 template narrative: baseline, lowest-tax variant, deltas in words, plus disclaimer."
        ),
    )


class TaxOptBCompareFromFinancialInputsRequestV1(TaxOptBFinancialInputsV1, TaxOptBExplainRequestFlagsV1):
    """Structured intake (income + deductions on the body) plus explicit strategy variants to compare."""

    model_config = ConfigDict(str_strip_whitespace=True)

    strategy_variants: list[TaxOptBStrategyVariantV1] = Field(
        default_factory=list,
        description="Explicit scenarios; total count with optional mapped row must be 1..12.",
    )
    include_mapped_strategy: bool = Field(
        default=False,
        description=(
            f"When true, prepends variant {MAPPED_INTAKE_VARIANT_ID!r} using the strategy "
            "derived from this body's deductions/investments (same as single compute-tax-from-financial-inputs)."
        ),
    )
    baseline_variant_id: str | None = Field(
        default=None,
        description="Must match a variant_id after expansion (including from_intake when enabled).",
    )
    include_result_detail: bool = Field(
        default=True,
        description="When false, rows omit full ``result`` payload.",
    )

    @model_validator(mode="after")
    def _capacity_ids_baseline(self) -> TaxOptBCompareFromFinancialInputsRequestV1:
        extra = 1 if self.include_mapped_strategy else 0
        n = len(self.strategy_variants) + extra
        if n < 1:
            raise ValueError(
                "Provide at least one strategy_variant or set include_mapped_strategy to true",
            )
        if n > 12:
            raise ValueError(
                "At most 12 strategy variants total including the mapped intake row when enabled",
            )
        ids = [v.variant_id for v in self.strategy_variants]
        if len(ids) != len(set(ids)):
            raise ValueError("strategy_variants must have unique variant_id values")
        if self.include_mapped_strategy and MAPPED_INTAKE_VARIANT_ID in set(ids):
            raise ValueError(
                f"variant_id {MAPPED_INTAKE_VARIANT_ID!r} is reserved when include_mapped_strategy is true",
            )
        all_ids = set(ids)
        if self.include_mapped_strategy:
            all_ids.add(MAPPED_INTAKE_VARIANT_ID)
        if self.baseline_variant_id is not None and self.baseline_variant_id not in all_ids:
            raise ValueError(
                "baseline_variant_id must match a variant_id in strategy_variants "
                f"or {MAPPED_INTAKE_VARIANT_ID!r} when include_mapped_strategy is true",
            )
        return self


class TaxOptBComparePresetsFromFinancialInputsRequestV1(TaxOptBFinancialInputsV1, TaxOptBExplainRequestFlagsV1):
    """Compare MVP strategy presets (user form, no claims, max caps) in one call."""

    model_config = ConfigDict(str_strip_whitespace=True)

    presets: list[Literal["user_proposed", "no_claims", "max_caps_mvp"]] = Field(
        default_factory=lambda: ["user_proposed", "no_claims", "max_caps_mvp"],
        min_length=1,
        max_length=3,
        description="Deterministic preset ids to run; each maps to the same gross profile.",
    )
    baseline_variant_id: str | None = Field(
        default=None,
        description=(
            "Must be one of ``presets``. When omitted, defaults to ``no_claims`` if listed, "
            "else ``user_proposed`` if listed."
        ),
    )
    include_result_detail: bool = Field(
        default=True,
        description="When false, compare rows omit full per-variant ``result`` payload.",
    )

    @model_validator(mode="after")
    def _unique_presets_and_baseline(self) -> TaxOptBComparePresetsFromFinancialInputsRequestV1:
        if len(self.presets) != len(set(self.presets)):
            raise ValueError("presets must be unique")
        if self.baseline_variant_id is not None and self.baseline_variant_id not in set(self.presets):
            raise ValueError("baseline_variant_id must be one of presets")
        return self


__all__ = [
    "MAPPED_INTAKE_VARIANT_ID",
    "TaxOptBCompareFromFinancialInputsRequestV1",
    "TaxOptBComparePresetsFromFinancialInputsRequestV1",
    "TaxOptBCompareStrategiesRequestV1",
    "TaxOptBCompareStrategiesResponseV1",
    "TaxOptBCompareStrategyResultRowV1",
    "TaxOptBStrategyVariantV1",
]
