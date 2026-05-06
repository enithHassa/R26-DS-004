"""Statement-level totals extracted from a document."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.config.database import Base


class StatementTotal(Base):
    __tablename__ = "statement_totals"

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
    opening_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    closing_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_debit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_credit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
