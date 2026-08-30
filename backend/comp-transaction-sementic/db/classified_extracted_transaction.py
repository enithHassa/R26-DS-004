"""Persisted tax classification for document extraction rows."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.shared.config.database import Base


class ClassifiedExtractedTransaction(Base):
    __tablename__ = "classified_extracted_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    financial_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extracted_transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    semantic_category: Mapped[str] = mapped_column(String(64), nullable=False)
    economic_event: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_rule_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    taxability_status: Mapped[str] = mapped_column(String(32), nullable=False)
    taxable_amount_lkr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    gross_amount_lkr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    certainty_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    class_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_semantic_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    classified_by: Mapped[str | None] = mapped_column(Text, nullable=True)
