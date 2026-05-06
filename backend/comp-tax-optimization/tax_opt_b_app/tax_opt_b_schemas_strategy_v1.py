"""Proposed strategy / relief vector for compliance checking (v1).

Each claim is an annual LKR amount the user or upstream planner proposes to
claim for a given ``relief_code``. Valid ``relief_code`` values are defined by
the active rules YAML (``deduction_caps_annual`` keys and special cases).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TaxOptBReliefClaimV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    relief_code: str = Field(min_length=1, max_length=64)
    claimed_amount_annual: Decimal = Field(ge=0, description="Annual amount in LKR.")


class TaxOptBStrategyProposalV1(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    claims: list[TaxOptBReliefClaimV1] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)


__all__ = ["TaxOptBReliefClaimV1", "TaxOptBStrategyProposalV1"]
