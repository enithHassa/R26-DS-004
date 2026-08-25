"""Minimal user ownership row.

Only fields needed for FK ownership and dashboard login land here in Phase 0.
Auth/RBAC columns (hashed_password, role, etc.) are added in the security phase.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Date, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampMixin
from backend.shared.config.database import Base


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # Plaintext login password (username = full_name, or email for accounts
    # created via the sign-up form). Prototype-only auth — see
    # routers/auth.py; do not carry this pattern into a real deployment.
    password: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Sign-up form fields (see migration 0008_expand_user_account_fields).
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mobile_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Optional avatar, stored as a data: URL (prototype — no object storage).
    profile_picture: Mapped[str | None] = mapped_column(Text, nullable=True)
