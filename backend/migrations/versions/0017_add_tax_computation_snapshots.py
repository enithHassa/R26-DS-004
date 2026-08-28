"""Persist OE Engine interview drafts and calculation results per profile.

Revision ID: 0017_add_tax_computation_snapshots
Revises: 0016_add_profile_taxable_income_monthly
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_add_tax_computation_snapshots"
down_revision: str | None = "0016_add_profile_taxable_income_monthly"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "tax_computation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("financial_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_year", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("taxpayer_name", sa.String(length=200), nullable=True),
        sa.Column("tin", sa.String(length=32), nullable=True),
        sa.Column("income_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "relief_answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "evidence_checks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("session_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("calculate_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("explain_narrative", sa.Text(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'auditor_manual'"),
        ),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["financial_profile_id"],
            ["financial_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tax_computation_snapshots_profile_id",
        "tax_computation_snapshots",
        ["financial_profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_tax_computation_snapshots_assessment_year",
        "tax_computation_snapshots",
        ["assessment_year"],
        unique=False,
    )
    op.create_index(
        "ix_tax_computation_snapshots_status",
        "tax_computation_snapshots",
        ["status"],
        unique=False,
    )
    op.create_index(
        "uq_tax_computation_draft_per_profile_year",
        "tax_computation_snapshots",
        ["financial_profile_id", "assessment_year"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_tax_computation_draft_per_profile_year",
        table_name="tax_computation_snapshots",
    )
    op.drop_index("ix_tax_computation_snapshots_status", table_name="tax_computation_snapshots")
    op.drop_index(
        "ix_tax_computation_snapshots_assessment_year",
        table_name="tax_computation_snapshots",
    )
    op.drop_index(
        "ix_tax_computation_snapshots_profile_id",
        table_name="tax_computation_snapshots",
    )
    op.drop_table("tax_computation_snapshots")
