"""Taxpayer flags on classified transactions for adviser follow-up.

Revision ID: 0020_add_user_transaction_flags
Revises: 0019_merge_doc_visibility_oe_heads
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_add_user_transaction_flags"
down_revision: str | None = "0019_merge_doc_visibility_oe_heads"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "user_transaction_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("financial_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extracted_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["financial_profile_id"],
            ["financial_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "financial_profile_id",
            "extracted_transaction_id",
            name="uq_user_transaction_flags_profile_tx",
        ),
    )
    op.create_index(
        "ix_user_transaction_flags_financial_profile_id",
        "user_transaction_flags",
        ["financial_profile_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_transaction_flags_financial_profile_id", table_name="user_transaction_flags")
    op.drop_table("user_transaction_flags")
