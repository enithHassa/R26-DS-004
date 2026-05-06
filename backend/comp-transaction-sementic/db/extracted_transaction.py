"""Normalized rows extracted from documents."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.config.database import Base

from backend.shared.db.enums import TxnDirection, txn_direction_enum


class ExtractedTransaction(Base):
    __tablename__ = "extracted_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tx_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    reference_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    debit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    credit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    amount_lkr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    direction: Mapped[TxnDirection] = mapped_column(txn_direction_enum, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_row_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_flagged: Mapped[bool] = mapped_column(nullable=False, server_default="false")
