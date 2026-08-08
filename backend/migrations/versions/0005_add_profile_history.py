"""add profile_history_snapshots table

Synthetic monthly financial history (income, expenses, balances) per
profile, generated on demand to evidence whether a profile's trajectory
supports adopting a recommended strategy.

Revision ID: 0005_add_profile_history
Revises: 0004_add_user_password
Create Date: 2026-08-08 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_profile_history"
down_revision: str | None = "0004_add_user_password"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "profile_history_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("financial_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_month", sa.Date(), nullable=False),
        sa.Column("gross_monthly_income", sa.Numeric(14, 2), nullable=False),
        sa.Column("monthly_expenses", sa.Numeric(14, 2), nullable=False),
        sa.Column("liquid_savings", sa.Numeric(14, 2), nullable=False),
        sa.Column("existing_investments", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_debt", sa.Numeric(14, 2), nullable=False),
        sa.Column("epf_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("etf_balance", sa.Numeric(14, 2), nullable=False),
        sa.Column("savings_rate", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("profile_id", "snapshot_month", name="uq_profile_snapshot_month"),
    )
    op.create_index(
        "ix_profile_history_snapshots_profile_id", "profile_history_snapshots", ["profile_id"]
    )
    op.create_index(
        "ix_profile_history_snapshots_snapshot_month", "profile_history_snapshots", ["snapshot_month"]
    )


def downgrade() -> None:
    op.drop_index("ix_profile_history_snapshots_snapshot_month", table_name="profile_history_snapshots")
    op.drop_index("ix_profile_history_snapshots_profile_id", table_name="profile_history_snapshots")
    op.drop_table("profile_history_snapshots")
