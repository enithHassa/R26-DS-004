"""Request/response models for POST /api/v1/compliance/check (Function 1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from tax_opt_b_app.tax_opt_b_schemas_explainability_v1 import TaxOptBExplainRequestFlagsV1
from tax_opt_b_app.tax_opt_b_schemas_financial_inputs_v1 import TaxOptBFinancialInputsV1
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBEmploymentTypeV1, TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1


class TaxOptBViolationSeverityV1(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class TaxOptBRuleViolationV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    rule_id: str
    severity: TaxOptBViolationSeverityV1 = TaxOptBViolationSeverityV1.ERROR
    message: str
    reference: str = Field(description="Human-readable act / schedule pointer from rules YAML.")


class TaxOptBComplianceResultV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    passed: bool
    violations: list[TaxOptBRuleViolationV1] = Field(default_factory=list)
    applied_relief: dict[str, Any] = Field(
        default_factory=dict,
        description="Capped or normalized amounts applied during evaluation (transparency).",
    )
    ruleset_assessment_year: str | None = None
    ruleset_schema_version: str | None = None
    rules_version_label: str | None = Field(
        default=None,
        description="From COMP_OPTIMIZATION_RULES_VERSION when set.",
    )
    income_snapshot: dict[str, Any] | None = Field(
        default=None,
        description="Component 1 income snapshot JSON when using check-from-transactions.",
    )
    mapped_profile: TaxOptBProfileV1 | None = Field(
        default=None,
        description="Profile derived from structured financial inputs (check-from-financial-inputs only).",
    )
    mapped_strategy: TaxOptBStrategyProposalV1 | None = Field(
        default=None,
        description="Strategy derived from deductions + mapped investments (check-from-financial-inputs only).",
    )


class TaxOptBComplianceCheckRequestV1(TaxOptBExplainRequestFlagsV1):
    profile: TaxOptBProfileV1
    strategy: TaxOptBStrategyProposalV1


class TaxOptBComplianceFromFinancialInputsRequestV1(TaxOptBFinancialInputsV1, TaxOptBExplainRequestFlagsV1):
    """Structured intake; profile always uses gross-only basis (no estimated taxable field)."""


class TaxOptBComplianceFromTransactionsRequestV1(BaseModel):
    """Orchestrated check: Component 1 snapshot → profile → ``evaluate_compliance``."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(min_length=1, max_length=128)
    tax_year: str = Field(
        default="2024_25",
        pattern=r"^\d{4}_\d{2}$",
        description="Must match rules YAML assessment year and snapshot query.",
    )
    employment_type: TaxOptBEmploymentTypeV1 = TaxOptBEmploymentTypeV1.EMPLOYEE
    dependents: int = Field(default=0, ge=0, le=20)
    strategy: TaxOptBStrategyProposalV1


__all__ = [
    "TaxOptBComplianceCheckRequestV1",
    "TaxOptBComplianceFromFinancialInputsRequestV1",
    "TaxOptBComplianceFromTransactionsRequestV1",
    "TaxOptBComplianceResultV1",
    "TaxOptBRuleViolationV1",
    "TaxOptBViolationSeverityV1",
]
