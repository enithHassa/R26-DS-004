"""Per-extract audit runs for amendment GPT / fixture extraction."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from backend.shared.config.database import Base

from .enums import AmendmentExtractRunStatus, amendment_extract_run_status_enum


class AmendmentExtractRun(Base):
    __tablename__ = "amendment_extract_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    amendment_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("amendment_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[AmendmentExtractRunStatus] = mapped_column(
        amendment_extract_run_status_enum,
        nullable=False,
        server_default=AmendmentExtractRunStatus.STARTED.value,
    )
    warnings: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Viva audit: prompts + focused text + raw GPT completion + structured rules.
    audit_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
