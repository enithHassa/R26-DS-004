"""Training/labeling rows for the semantic classifier (WP3)."""

import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from backend.shared.config.database import Base

from .enums import LabelSource, label_source_enum


class TransactionLabel(Base):
    __tablename__ = "transaction_labels"

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

    semantic_category: Mapped[str] = mapped_column(String(64), nullable=False)
    economic_event: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tax_rule_code: Mapped[str | None] = mapped_column(String(64), nullable=True)

    label_source: Mapped[LabelSource] = mapped_column(label_source_enum, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_transaction_labels_tx_id", "tx_id"),
    )
