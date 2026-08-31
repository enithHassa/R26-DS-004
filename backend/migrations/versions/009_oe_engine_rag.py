"""Optimization and Explainable Engine RAG tables (Phase 2).

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3, 0008_expand_user_account_fields
Create Date: 2026-08-26

oe_engine_consolidated_facts is created empty; Phase 3 extract writes rows.
Year views land in Phase 4. Mismatch flags are Phase 3 (010).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c9d0e1f2g3h4"
down_revision = ("b8c9d0e1f2g3", "0008_expand_user_account_fields")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oe_engine_documents",
        sa.Column("source_doc_id", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("tier", sa.String(length=32), nullable=False),
        sa.Column("instrument_type", sa.String(length=64), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("source_doc_id"),
        sa.UniqueConstraint("sha256", name="uq_oe_engine_documents_sha256"),
    )
    op.create_index("ix_oe_engine_documents_tier", "oe_engine_documents", ["tier"])
    op.create_index("ix_oe_engine_documents_sha256", "oe_engine_documents", ["sha256"])

    op.create_table(
        "oe_engine_chunks",
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("source_doc_id", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("section_ref", sa.Text(), nullable=True),
        sa.Column("parent_provision_id", sa.String(length=128), nullable=True),
        sa.Column("embedding_json", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_doc_id"],
            ["oe_engine_documents.source_doc_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index("ix_oe_engine_chunks_source_doc_id", "oe_engine_chunks", ["source_doc_id"])
    op.create_index("ix_oe_engine_chunks_channel", "oe_engine_chunks", ["channel"])

    op.create_table(
        "oe_engine_consolidated_facts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("compare_group_id", sa.String(length=128), nullable=False),
        sa.Column("year", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("consolidated_source_doc_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "compare_group_id",
            "year",
            "consolidated_source_doc_id",
            name="uq_oe_engine_consolidated_facts_group_year_doc",
        ),
    )
    op.create_index(
        "ix_oe_engine_consolidated_facts_compare_group_id",
        "oe_engine_consolidated_facts",
        ["compare_group_id"],
    )
    op.create_index(
        "ix_oe_engine_consolidated_facts_year",
        "oe_engine_consolidated_facts",
        ["year"],
    )


def downgrade() -> None:
    op.drop_table("oe_engine_consolidated_facts")
    op.drop_table("oe_engine_chunks")
    op.drop_table("oe_engine_documents")
