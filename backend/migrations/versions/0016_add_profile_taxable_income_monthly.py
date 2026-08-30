"""Monthly taxable income rollup per financial profile.

Revision ID: 0016_add_profile_taxable_income_monthly
Revises: 0015_add_classified_extracted_transactions
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_add_profile_taxable_income_monthly"
down_revision: str | None = "0015_add_classified_extracted_transactions"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "profile_taxable_income_monthly",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tax_year", sa.String(length=8), nullable=True),
        sa.Column("calendar_month", sa.Date(), nullable=False),
        sa.Column("class_key", sa.String(length=64), nullable=False),
        sa.Column("taxable_amount_lkr", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column(
            "source_document_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["financial_profile_id"],
            ["financial_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "financial_profile_id",
            "tax_year",
            "calendar_month",
            "class_key",
            name="uq_profile_taxable_income_monthly_bucket",
        ),
    )
    op.create_index(
        "ix_profile_taxable_income_monthly_profile_id",
        "profile_taxable_income_monthly",
        ["financial_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_profile_taxable_income_monthly_calendar_month",
        "profile_taxable_income_monthly",
        ["calendar_month"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_profile_taxable_income_monthly_calendar_month",
        table_name="profile_taxable_income_monthly",
    )
    op.drop_index(
        "ix_profile_taxable_income_monthly_profile_id",
        table_name="profile_taxable_income_monthly",
    )
    op.drop_table("profile_taxable_income_monthly")
