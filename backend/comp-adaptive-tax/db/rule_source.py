"""Reviewable extracted rules with mandatory source quotes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from backend.shared.config.database import Base

from .enums import RuleSourceStatus, RuleType, rule_source_status_enum, rule_type_enum


class RuleSource(Base):
    __tablename__ = "rule_source"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    amendment_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("amendment_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extract_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("amendment_extract_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    paragraph: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_type: Mapped[RuleType] = mapped_column(rule_type_enum, nullable=False)
    concept_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amends_section: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RuleSourceStatus] = mapped_column(
        rule_source_status_enum,
        nullable=False,
        server_default=RuleSourceStatus.PENDING.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
