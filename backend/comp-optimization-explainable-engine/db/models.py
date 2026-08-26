"""Postgres tables for Optimization and Explainable Engine RAG."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.shared.config.database import Base


class OeEngineDocument(Base):
    __tablename__ = "oe_engine_documents"

    source_doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    instrument_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class OeEngineChunk(Base):
    __tablename__ = "oe_engine_chunks"

    chunk_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_doc_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("oe_engine_documents.source_doc_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_provision_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class OeEngineConsolidatedFact(Base):
    """Year-keyed Consolidated facts. Empty until Phase 3 extract."""

    __tablename__ = "oe_engine_consolidated_facts"
    __table_args__ = (
        UniqueConstraint(
            "compare_group_id",
            "year",
            "consolidated_source_doc_id",
            name="uq_oe_engine_consolidated_facts_group_year_doc",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    compare_group_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    year: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    consolidated_source_doc_id: Mapped[str] = mapped_column(String(64), nullable=False)
