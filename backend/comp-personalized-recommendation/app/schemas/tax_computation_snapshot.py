"""Pydantic contracts for profile-scoped OE calculation snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from backend.shared.schemas.common import ORMBase

SnapshotStatus = Literal["draft", "calculated", "finalized"]
SnapshotSource = Literal["auditor_manual", "profile_load", "transaction_merge"]


class TaxComputationSnapshotUpsert(ORMBase):
    assessment_year: str
    status: SnapshotStatus = "draft"
    taxpayer_name: str | None = None
    tin: str | None = None
    income_state: dict[str, Any]
    relief_answers: list[dict[str, Any]] = Field(default_factory=list)
    evidence_checks: dict[str, Any] = Field(default_factory=dict)
    session_meta: dict[str, Any] | None = None
    calculate_result: dict[str, Any] | None = None
    explain_narrative: str | None = None
    source: SnapshotSource = "auditor_manual"
    created_by: str | None = None


class TaxComputationSnapshotStatusUpdate(ORMBase):
    status: SnapshotStatus


class TaxComputationSnapshotSummary(ORMBase):
    id: UUID
    financial_profile_id: UUID
    assessment_year: str
    status: SnapshotStatus
    taxpayer_name: str | None = None
    tin: str | None = None
    source: SnapshotSource
    created_at: datetime
    updated_at: datetime | None = None
    has_calculate_result: bool = False


class TaxComputationSnapshotDetail(TaxComputationSnapshotSummary):
    income_state: dict[str, Any]
    relief_answers: list[dict[str, Any]]
    evidence_checks: dict[str, Any]
    session_meta: dict[str, Any] | None = None
    calculate_result: dict[str, Any] | None = None
    explain_narrative: str | None = None
    created_by: str | None = None
