"""Recommendation adoption feedback ORM model.

Records whether a user actually acted on a recommended strategy, keyed to a
persisted `recommendation_items` row (see `app/models/recommendation.py`).
This is the real-world adoption signal the synthetic-trained model currently
has no access to — see `scripts/export_training_data.py` for how it later
feeds back into retraining.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class RecommendationFeedback(TimestampMixin, Base):
    __tablename__ = "recommendation_feedback"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("recommendation_items.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    accepted: Mapped[bool] = mapped_column(nullable=False)
    dismissed_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
