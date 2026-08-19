"""Admin param-override DTOs (Phase 4 amendment adaptivity)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ParamOverrideOut(BaseModel):
    """Summary of a written runtime relief-cap override."""

    written: bool = True
    source: str
    path: str
    concept_id: str
    cap_amount: str = Field(description="Cap amount as decimal string (LKR).")
    rule_source_id: str | None = None
    amendment_job_id: str | None = None


class ParamResetResponse(BaseModel):
    """Response for POST /admin/params/reset-to-pre-amend."""

    ok: bool = True
    source: Literal["reset_to_pre_amend"] = "reset_to_pre_amend"
    override_path: str
    concept_id: str
    personal_relief_cap: str = Field(description="Personal relief cap amount (LKR) as decimal string.")
    override: dict[str, Any] | None = None
