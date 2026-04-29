"""Canonical Transaction table.

Owned by no single component; every component (semantic reasoning, language
model, recommendation, tax optimization) reads from this table.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from backend.shared.config.database import Base
from backend.shared.db.enums import TxnDirection, txn_direction_enum


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    raw_desc: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_desc: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount_lkr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tx_date: Mapped[date] = mapped_column(Date, nullable=False)
    direction: Mapped[TxnDirection] = mapped_column(txn_direction_enum, nullable=False)

    bank_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_transactions_bank_code_tx_date", "bank_code", "tx_date"),
    )
