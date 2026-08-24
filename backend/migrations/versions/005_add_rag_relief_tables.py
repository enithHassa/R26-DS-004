"""Add RAG Relief component tables with pgvector support.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-24 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    # Note: pgvector extension requires server-level permissions
    # On Azure, this may not be available. Embeddings stored as text instead.
    # For local PostgreSQL: install pgvector manually or the extension will be skipped.
    # op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create rag_relief_chunks table
    op.create_table(
        "rag_relief_chunks",
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("has_relief", sa.Boolean(), default=False),
        sa.Column("has_amount", sa.Boolean(), default=False),
        sa.Column("relief_amounts", postgresql.JSON(), default=[]),
        sa.Column("embedding", sa.String(), nullable=True),
        sa.Column("embedding_model", sa.String(), default="text-embedding-3-small"),
        sa.Column("source_act", sa.String(), nullable=True),
        sa.Column("source_section", sa.String(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("indexed", sa.Boolean(), default=True),
        sa.Column("searchable", sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index("ix_rag_relief_chunks_text", "rag_relief_chunks", ["text"])
    op.create_index(
        "ix_rag_relief_chunks_has_relief", "rag_relief_chunks", ["has_relief"]
    )
    op.create_index(
        "ix_rag_relief_chunks_source_act", "rag_relief_chunks", ["source_act"]
    )

    # Create rag_relief_extractions table
    op.create_table(
        "rag_relief_extractions",
        sa.Column("extraction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relief_name", sa.String(), nullable=False),
        sa.Column("cap_amount", sa.String(), nullable=True),
        sa.Column("currency", sa.String(), default="LKR"),
        sa.Column("effective_from", sa.String(), nullable=True),
        sa.Column("assessment_years", postgresql.JSON(), default=[]),
        sa.Column("section_ref", sa.String(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column("source_act", sa.String(), nullable=True),
        sa.Column("confidence_name", sa.Float(), default=0.0),
        sa.Column("confidence_amount", sa.Float(), default=0.0),
        sa.Column("confidence_date", sa.Float(), default=0.0),
        sa.Column("confidence_overall", sa.Float(), default=0.0),
        sa.Column("status", sa.String(), default="pending"),
        sa.Column("auditor_notes", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("extraction_id"),
    )
    op.create_index(
        "ix_rag_relief_extractions_status",
        "rag_relief_extractions",
        ["status"],
    )
    op.create_index(
        "ix_rag_relief_extractions_relief_name",
        "rag_relief_extractions",
        ["relief_name"],
    )
    op.create_index(
        "ix_rag_relief_extractions_source_act",
        "rag_relief_extractions",
        ["source_act"],
    )

    # Create rag_relief_audit_log table
    op.create_table(
        "rag_relief_audit_log",
        sa.Column("log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("details", postgresql.JSON(), nullable=True),
        sa.Column("pdf_filename", sa.String(), nullable=True),
        sa.Column("chunks_affected", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), default=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("log_id"),
    )
    op.create_index(
        "ix_rag_relief_audit_log_operation",
        "rag_relief_audit_log",
        ["operation"],
    )
    op.create_index(
        "ix_rag_relief_audit_log_user",
        "rag_relief_audit_log",
        ["user_email"],
    )


def downgrade():
    # Drop tables
    op.drop_table("rag_relief_audit_log")
    op.drop_table("rag_relief_extractions")
    op.drop_table("rag_relief_chunks")

    # Note: pgvector extension not dropped (if it exists, leave for other components)
