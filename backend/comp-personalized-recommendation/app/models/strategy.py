"""Tax strategy catalog ORM model (FR3).

Populated by the rules-seed script in Phase 1 from
``models/personalized-recommendation/rules/sl_tax_2024_25.yaml``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class TaxStrategy(TimestampMixin, Base):
    __tablename__ = "tax_strategies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    legal_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)

    min_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    max_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    min_age: Mapped[int | None] = mapped_column(nullable=True)
    max_age: Mapped[int | None] = mapped_column(nullable=True)
    min_liquidity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    risk_profile: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    effort_score: Mapped[float] = mapped_column(default=0.3, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
