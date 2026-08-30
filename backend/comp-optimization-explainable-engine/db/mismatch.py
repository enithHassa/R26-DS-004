"""Mismatch-flag row for Consolidated vs Act year views."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.shared.config.database import Base


class OeEngineMismatchFlag(Base):
    __tablename__ = "oe_engine_mismatch_flags"
    __table_args__ = (
        UniqueConstraint(
            "compare_group_id",
            "year",
            "consolidated_source_doc_id",
            name="uq_oe_engine_mismatch_flags_group_year_doc",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    compare_group_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    year: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    value_consolidated: Mapped[str] = mapped_column(Text, nullable=False)
    value_act: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    consolidated_source_doc_id: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
