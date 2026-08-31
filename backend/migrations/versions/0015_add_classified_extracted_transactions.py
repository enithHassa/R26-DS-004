"""Persist tax classifications on extracted document rows.

Revision ID: 0015_add_classified_extracted_transactions
Revises: 0014_add_profile_document_ownership
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_add_classified_extracted_transactions"
down_revision: str | None = "0014_add_profile_document_ownership"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "classified_extracted_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extracted_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("semantic_category", sa.String(length=64), nullable=False),
        sa.Column("economic_event", sa.String(length=64), nullable=True),
        sa.Column("tax_rule_code", sa.String(length=64), nullable=True),
        sa.Column("taxability_status", sa.String(length=32), nullable=False),
        sa.Column("taxable_amount_lkr", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("gross_amount_lkr", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("certainty_tier", sa.String(length=32), nullable=True),
        sa.Column("class_source", sa.String(length=32), nullable=True),
        sa.Column("decision_mode", sa.String(length=32), nullable=True),
        sa.Column("model_semantic_category", sa.String(length=64), nullable=True),
        sa.Column("analysis_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "classified_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("classified_by", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["extracted_transaction_id"],
            ["extracted_transactions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["financial_profile_id"],
            ["financial_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_classified_extracted_document_id",
        "classified_extracted_transactions",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_classified_extracted_financial_profile_id",
        "classified_extracted_transactions",
        ["financial_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_classified_extracted_extracted_transaction_id",
        "classified_extracted_transactions",
        ["extracted_transaction_id"],
        unique=False,
    )
    op.create_index(
        "uq_classified_extracted_current",
        "classified_extracted_transactions",
        ["extracted_transaction_id"],
        unique=True,
        postgresql_where=sa.text("is_current = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_classified_extracted_current", table_name="classified_extracted_transactions")
    op.drop_index(
        "ix_classified_extracted_extracted_transaction_id",
        table_name="classified_extracted_transactions",
    )
    op.drop_index(
        "ix_classified_extracted_financial_profile_id",
        table_name="classified_extracted_transactions",
    )
    op.drop_index(
        "ix_classified_extracted_document_id",
        table_name="classified_extracted_transactions",
    )
    op.drop_table("classified_extracted_transactions")
