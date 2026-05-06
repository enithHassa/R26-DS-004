"""Narrow tax profile contract for Component B Function 1 (v1).

This is a deliberate stub until Component A / shared profile APIs stabilize.
Fields map to Sri Lankan APIT-style MVP rules in
``models/tax-optimization/rules/it22064486_sl_tax_mvp.yaml``.

Field → rule_id (see ``it22064486_sl_tax_mvp.yaml`` ``rules``):

- ``tax_year`` — must match YAML ``assessment_year`` (``it22064486_optb_year_001``).
- ``annual_gross_income`` — retirement contribution cap uses
  ``min(pct * gross, cap)`` (``it22064486_optb_cap_retirement_001``).
- ``estimated_annual_taxable_income`` — charitable donations cap uses
  ``pct * taxable`` when set; otherwise ``pct * annual_gross_income`` is used
  as the MVP basis (``it22064486_optb_cap_donations_001``). Structured financial
  intake (``TaxOptBFinancialInputsV1``) always omits this field so the basis is
  gross only (salary + business + other).
- ``dependents``, ``employment_type`` — reserved for future rules; not evaluated in MVP.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class TaxOptBEmploymentTypeV1(StrEnum):
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    BUSINESS_OWNER = "business_owner"
    OTHER = "other"


class TaxOptBProfileV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    tax_year: str = Field(
        default="2024_25",
        pattern=r"^\d{4}_\d{2}$",
        description="Assessment year label; must match rules YAML.",
    )
    employment_type: TaxOptBEmploymentTypeV1 = TaxOptBEmploymentTypeV1.EMPLOYEE
    dependents: int = Field(default=0, ge=0, le=20)

    annual_gross_income: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Annual gross income (LKR); used for percentage-based deduction caps.",
    )
    estimated_annual_taxable_income: Decimal | None = Field(
        default=None,
        ge=0,
        description="When set, used for charitable donation cap as % of taxable income.",
    )


__all__ = ["TaxOptBEmploymentTypeV1", "TaxOptBProfileV1"]
