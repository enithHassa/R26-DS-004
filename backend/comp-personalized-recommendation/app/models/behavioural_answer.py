"""Behavioural-question answer ORM model.

Captures a taxpayer's click-through answers to simple financial-behaviour
questions (e.g. risk comfort, investing frequency). Some answers are mapped
onto existing `FinancialProfile` fields the recommendation model already
consumes (see `app/routers/profiles.py`); others are stored here only, for
future use once the training pipeline is extended to consume them — see the
module docstring in `scripts/export_training_data.py`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class BehaviouralAnswer(TimestampMixin, Base):
    __tablename__ = "behavioural_answers"
    __table_args__ = (
        UniqueConstraint("profile_id", "question_key", name="uq_behavioural_answer_profile_question"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("financial_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    question_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    answer_value: Mapped[str] = mapped_column(String(80), nullable=False)
