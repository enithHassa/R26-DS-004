"""Request/response models for MVP deterministic tax computation (Phase B)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tax_opt_b_app.tax_opt_b_schemas_compliance_v1 import TaxOptBComplianceResultV1
from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import TaxOptBExplanationBundleV1


class TaxOptBSlabTaxSliceV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    slab_index: int = Field(ge=0)
    rate: str
    slice_width_cap: str | None = Field(
        default=None,
        description="Band width from YAML; null for remainder band (upper null).",
    )
    taxable_in_slice: str
    tax_in_slice: str


class TaxOptBTaxComputationV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    income_basis_before_personal_relief: str
    annual_gross_income: str
    estimated_annual_taxable_income: str | None
    personal_relief_annual: str
    taxable_after_personal_relief: str
    total_allowed_deductions: str
    per_deduction_allowed: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Echo of applied_relief entries (stringified values) for explainability.",
    )
    taxable_after_deductions: str
    slab_slices: list[TaxOptBSlabTaxSliceV1]
    total_tax: str
    algorithm_documentation: str = Field(
        description="Short plain-language description of basis, relief, and slab walk.",
    )


class TaxOptBComputeTaxResponseV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    compliance: TaxOptBComplianceResultV1
    tax_computation: TaxOptBTaxComputationV1 | None = Field(
        default=None,
        description="Present only when compliance passed; otherwise null.",
    )
    research_disclaimer: str
    explanations: TaxOptBExplanationBundleV1 | None = Field(
        default=None,
        description=(
            "Optional FR5 template narrative from nested ``compliance`` and ``tax_computation`` "
            "(violations, reliefs, slabs); not generated for POST /check unless extended later."
        ),
    )


__all__ = [
    "TaxOptBComputeTaxResponseV1",
    "TaxOptBSlabTaxSliceV1",
    "TaxOptBTaxComputationV1",
]
