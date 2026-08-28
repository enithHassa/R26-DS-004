"""Persisted Optimization Engine interview + calculation snapshots per profile."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class TaxComputationSnapshot(TimestampMixin, Base):
    __tablename__ = "tax_computation_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    financial_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    assessment_year: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    taxpayer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    income_state: Mapped[dict] = mapped_column(JSON, nullable=False)
    relief_answers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_checks: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    session_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    calculate_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explain_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="auditor_manual")
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
