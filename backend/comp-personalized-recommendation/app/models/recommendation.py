"""Recommendation run + ranked items ORM models (FR5, FR6)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import JSON, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class Recommendation(TimestampMixin, Base):
    """One row per generated recommendation batch for a profile."""

    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)


class RecommendationItem(TimestampMixin, Base):
    """One row per ranked strategy inside a recommendation batch."""

    __tablename__ = "recommendation_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("tax_strategies.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    rank: Mapped[int] = mapped_column(nullable=False)
    estimated_annual_savings: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    adoption_probability: Mapped[float] = mapped_column(nullable=False)
    risk_score: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)

    scores_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
