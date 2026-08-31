"""Link documents to financial profiles; store transaction_taxpayer_id on profiles.

Revision ID: 0014_add_profile_document_ownership
Revises: 0012_add_tax_return_detail
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_add_profile_document_ownership"
down_revision: str | None = "0012_add_tax_return_detail"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_profiles",
        sa.Column("transaction_taxpayer_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_financial_profiles_transaction_taxpayer_id",
        "financial_profiles",
        ["transaction_taxpayer_id"],
        unique=False,
    )

    op.add_column(
        "documents",
        sa.Column("financial_profile_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("tax_year", sa.String(length=8), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("statement_period_from", sa.Date(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("statement_period_to", sa.Date(), nullable=True),
    )
    op.create_index(
        "ix_documents_financial_profile_id",
        "documents",
        ["financial_profile_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_documents_financial_profile_id",
        "documents",
        "financial_profiles",
        ["financial_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Demo profile ↔ taxpayer_00001 YAML used by transaction semantic rules.
    op.execute(
        sa.text(
            """
            UPDATE financial_profiles
            SET transaction_taxpayer_id = 'taxpayer_00001'
            WHERE transaction_taxpayer_id IS NULL
              AND (
                full_name ILIKE '%taxpayer%00001%'
                OR full_name ILIKE '%Taxpayer_00001%'
              )
            """
        )
    )

    # Attach existing bank statements to the demo profile when present.
    op.execute(
        sa.text(
            """
            UPDATE documents
            SET financial_profile_id = (
                SELECT id FROM financial_profiles
                WHERE transaction_taxpayer_id = 'taxpayer_00001'
                ORDER BY created_at ASC
                LIMIT 1
            )
            WHERE financial_profile_id IS NULL
              AND EXISTS (
                SELECT 1 FROM financial_profiles
                WHERE transaction_taxpayer_id = 'taxpayer_00001'
              )
            """
        )
    )

    # Copy statement period metadata from statement_totals when available.
    op.execute(
        sa.text(
            """
            UPDATE documents d
            SET
              statement_period_from = st.period_start,
              statement_period_to = st.period_end
            FROM (
              SELECT DISTINCT ON (document_id)
                document_id,
                period_start,
                period_end
              FROM statement_totals
              WHERE period_start IS NOT NULL OR period_end IS NOT NULL
              ORDER BY document_id, period_start NULLS LAST
            ) st
            WHERE d.id = st.document_id
              AND d.statement_period_from IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_financial_profile_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_financial_profile_id", table_name="documents")
    op.drop_column("documents", "statement_period_to")
    op.drop_column("documents", "statement_period_from")
    op.drop_column("documents", "tax_year")
    op.drop_column("documents", "financial_profile_id")
    op.drop_index("ix_financial_profiles_transaction_taxpayer_id", table_name="financial_profiles")
    op.drop_column("financial_profiles", "transaction_taxpayer_id")
