"""Taxpayer-initiated flags on transaction classifications."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.shared.config.database import Base


class UserTransactionFlag(Base):
    __tablename__ = "user_transaction_flags"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    financial_profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_transaction_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
