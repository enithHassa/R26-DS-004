"""Human-in-the-loop review queue for low-confidence/OOD predictions (WP7)."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from backend.shared.config.database import Base

from .enums import ReviewStatus, review_status_enum


class ReviewQueueItem(Base):
    __tablename__ = "review_queue"

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

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(
        review_status_enum,
        nullable=False,
        server_default=ReviewStatus.PENDING.value,
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_review_queue_status", "status"),
    )
