"""Database models for RAG Relief Component."""

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    JSON,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()


class RagReliefChunk(Base):
    """Tax relief provision chunks with vector embeddings."""

    __tablename__ = "rag_relief_chunks"

    chunk_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False, index=True)
    has_relief = Column(Boolean, default=False)
    has_amount = Column(Boolean, default=False)
    relief_amounts = Column(JSON, default=list)  # ["1200000", "500000"]

    # Embeddings (pgvector)
    embedding = Column("embedding", String, nullable=True)  # pgvector type as text
    embedding_model = Column(String, default="text-embedding-3-small")

    # Source tracking
    source_act = Column(String, nullable=True)  # Act name/number
    source_section = Column(String, nullable=True)  # Section reference
    page_number = Column(Integer, nullable=True)

    # Metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Vector store status
    indexed = Column(Boolean, default=True)
    searchable = Column(Boolean, default=True)


class RagReliefExtraction(Base):
    """Extracted relief information with auditor approval status."""

    __tablename__ = "rag_relief_extractions"

    extraction_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Extraction data
    relief_name = Column(String, nullable=False)
    cap_amount = Column(String, nullable=True)  # "1200000"
    currency = Column(String, default="LKR")
    effective_from = Column(String, nullable=True)  # YYYY-MM-DD
    assessment_years = Column(JSON, default=list)  # ["2023_24", "2024_25"]
    section_ref = Column(String, nullable=True)
    quote = Column(Text, nullable=True)
    source_act = Column(String, nullable=True)

    # Confidence scores
    confidence_name = Column(Float, default=0.0)
    confidence_amount = Column(Float, default=0.0)
    confidence_date = Column(Float, default=0.0)
    confidence_overall = Column(Float, default=0.0)

    # Auditor approval
    status = Column(String, default="pending")  # pending, approved, rejected, needs_review
    auditor_notes = Column(Text, nullable=True)
    approved_by = Column(String, nullable=True)  # User email
    approved_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagReliefAuditLog(Base):
    """Audit trail for all RAG operations."""

    __tablename__ = "rag_relief_audit_log"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    operation = Column(String, nullable=False)  # ingest, search, extract, approve, reject
    user_email = Column(String, nullable=True)
    details = Column(JSON, nullable=True)

    # Source info
    pdf_filename = Column(String, nullable=True)
    chunks_affected = Column(Integer, nullable=True)

    # Results
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
