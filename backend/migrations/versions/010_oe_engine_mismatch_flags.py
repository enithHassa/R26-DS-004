"""oe_engine_mismatch_flags for Consolidated cross-check (Phase 3 terminus).

Revision ID: d0e1f2g3h4i5
Revises: c9d0e1f2g3h4
Create Date: 2026-08-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d0e1f2g3h4i5"
down_revision = "c9d0e1f2g3h4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oe_engine_mismatch_flags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("compare_group_id", sa.String(length=128), nullable=False),
        sa.Column("year", sa.String(length=16), nullable=False),
        sa.Column("value_consolidated", sa.Text(), nullable=False),
        sa.Column("value_act", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("consolidated_source_doc_id", sa.String(length=64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "compare_group_id",
            "year",
            "consolidated_source_doc_id",
            name="uq_oe_engine_mismatch_flags_group_year_doc",
        ),
    )
    op.create_index(
        "ix_oe_engine_mismatch_flags_compare_group_id",
        "oe_engine_mismatch_flags",
        ["compare_group_id"],
    )
    op.create_index("ix_oe_engine_mismatch_flags_year", "oe_engine_mismatch_flags", ["year"])


def downgrade() -> None:
    op.drop_table("oe_engine_mismatch_flags")
