"""Minimal anchor for ``financial_profiles`` FK resolution outside Comp 3.

The full profile ORM lives in ``comp-personalized-recommendation``. Component 1
and shared rollup tables reference ``financial_profiles.id`` but must not import
the full Comp 3 model graph. Registering this stub on the shared ``Base``
metadata lets SQLAlchemy flush cross-component rows without
``NoReferencedTableError``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.config.database import Base


class FinancialProfileRef(Base):
    __tablename__ = "financial_profiles"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
