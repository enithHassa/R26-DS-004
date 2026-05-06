"""Versioned aggregate income view from Component 1 (bank transactions → taxability).

Used by Component B (Option B) to populate ``TaxOptBProfileV1.annual_gross_income`` and
``estimated_annual_taxable_income`` before rule evaluation.

**Derivation (contract):** ``estimated_annual_taxable_income`` is the sum of positive
``taxable_amount`` on inflow transactions classified as taxable income for the assessment
window, minus structurally allowed exclusions (stub: not yet computed from DB; the live
pipeline will replace the stub implementation while keeping this schema).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class IncomeSnapshotV1(BaseModel):
    """Stable JSON shape for ``GET .../income-snapshot`` (v1)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    schema_version: str = Field(
        default="income_snapshot_v1",
        description="Literal version tag; bump when fields or semantics change.",
    )
    user_id: str
    assessment_year: str = Field(pattern=r"^\d{4}_\d{2}$")
    annual_gross_income: Decimal = Field(ge=0, description="Gross inflows attributed to income.")
    estimated_annual_taxable_income: Decimal = Field(
        ge=0,
        description="Taxable-income basis after exclusions; used for % caps on relief.",
    )
    charity_outflows_annual: Decimal | None = Field(
        default=None,
        ge=0,
        description="Optional aggregate charity debits (reserved for future rules).",
    )
    source: str = Field(
        description="Provenance, e.g. component1_stub or component1_live.",
    )
    derivation_summary: str = Field(
        min_length=1,
        description="Short human-readable note on how figures were derived.",
    )
    pipeline_version: str
    transaction_count: int = Field(ge=0, default=0)


__all__ = ["IncomeSnapshotV1"]
