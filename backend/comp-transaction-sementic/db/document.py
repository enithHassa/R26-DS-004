"""Document metadata for ingestion pipeline."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import DateTime

from backend.shared.config.database import Base

from .enums import DocumentStatus, document_status_enum


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bank_detected: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        document_status_enum,
        nullable=False,
        server_default=DocumentStatus.UPLOADED.value,
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    financial_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tax_year: Mapped[str | None] = mapped_column(String(8), nullable=True)
    statement_period_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    statement_period_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    submitted_by: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="auditor",
    )
    user_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
