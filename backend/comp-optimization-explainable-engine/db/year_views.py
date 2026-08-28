"""Year views and promoted extract rows (Phase 4)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.shared.config.database import Base


class OeEnginePromotedEntity(Base):
    """Included Act entities after promote. Compiler input; not the year view."""

    __tablename__ = "oe_engine_promoted_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_doc_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    extraction_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    compare_group_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entry_id: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class OeEnginePromotedRun(Base):
    """Last successful Act promote per source_doc_id (hash-match three-way)."""

    __tablename__ = "oe_engine_promoted_runs"

    source_doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    branch: Mapped[str] = mapped_column(String(32), nullable=False)
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class OeEngineYearRelief(Base):
    __tablename__ = "oe_engine_year_reliefs"
    __table_args__ = (
        UniqueConstraint(
            "assessment_year",
            "compare_group_id",
            name="uq_oe_engine_year_reliefs_year_group",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_year: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    compare_group_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entry_id: Mapped[str] = mapped_column(String(256), nullable=False)
    source_doc_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cap_amount: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(String(512), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="lkr")
    input_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="notice")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    effective_from: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    extraction_run_id: Mapped[str] = mapped_column(String(64), nullable=False)


class OeEngineYearRate(Base):
    __tablename__ = "oe_engine_year_rates"
    __table_args__ = (
        UniqueConstraint(
            "assessment_year",
            "compare_group_id",
            "ladder_key",
            "band_index",
            name="uq_oe_engine_year_rates_year_group_ladder_band",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    assessment_year: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    compare_group_id: Mapped[str] = mapped_column(String(128), nullable=False, default="first_schedule_rates", index=True)
    ladder_key: Mapped[str] = mapped_column(String(256), nullable=False, default="ordinary|full_ya")
    band_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lower: Mapped[str] = mapped_column(String(32), nullable=False)
    upper: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rate_percent: Mapped[str] = mapped_column(String(16), nullable=False)
    applies_to: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source_doc_id: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    effective_from: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    extraction_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
