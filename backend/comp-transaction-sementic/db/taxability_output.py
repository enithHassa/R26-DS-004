"""Pipeline output: taxability decision + evidence chain per transaction."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Float, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from backend.shared.config.database import Base

from .enums import TaxabilityStatus, taxability_status_enum


class TaxabilityOutput(Base):
    __tablename__ = "taxability_outputs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    tx_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
    )

    taxability_status: Mapped[TaxabilityStatus] = mapped_column(
        taxability_status_enum, nullable=False
    )
    taxable_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_taxability_outputs_tx_id", "tx_id"),
    )
