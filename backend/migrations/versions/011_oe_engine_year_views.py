"""oe_engine year views + promoted entities (Phase 4 compiler).

Revision ID: e1f2g3h4i5j6
Revises: d0e1f2g3h4i5
Create Date: 2026-08-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e1f2g3h4i5j6"
down_revision = "d0e1f2g3h4i5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oe_engine_promoted_entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_doc_id", sa.String(length=64), nullable=False),
        sa.Column("extraction_run_id", sa.String(length=64), nullable=False),
        sa.Column("entity_kind", sa.String(length=32), nullable=False),
        sa.Column("compare_group_id", sa.String(length=128), nullable=False),
        sa.Column("entry_id", sa.String(length=256), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "promoted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_oe_engine_promoted_entities_source_doc_id",
        "oe_engine_promoted_entities",
        ["source_doc_id"],
    )
    op.create_index(
        "ix_oe_engine_promoted_entities_extraction_run_id",
        "oe_engine_promoted_entities",
        ["extraction_run_id"],
    )
    op.create_index(
        "ix_oe_engine_promoted_entities_compare_group_id",
        "oe_engine_promoted_entities",
        ["compare_group_id"],
    )

    op.create_table(
        "oe_engine_promoted_runs",
        sa.Column("source_doc_id", sa.String(length=64), nullable=False),
        sa.Column("extraction_run_id", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=32), nullable=False),
        sa.Column(
            "promoted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("source_doc_id"),
    )

    op.create_table(
        "oe_engine_year_reliefs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assessment_year", sa.String(length=16), nullable=False),
        sa.Column("compare_group_id", sa.String(length=128), nullable=False),
        sa.Column("entry_id", sa.String(length=256), nullable=False),
        sa.Column("source_doc_id", sa.String(length=64), nullable=False),
        sa.Column("cap_amount", sa.Text(), nullable=True),
        sa.Column("display_name", sa.String(length=512), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="lkr"),
        sa.Column("input_kind", sa.String(length=32), nullable=False, server_default="notice"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("extraction_run_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_year",
            "compare_group_id",
            name="uq_oe_engine_year_reliefs_year_group",
        ),
    )
    op.create_index(
        "ix_oe_engine_year_reliefs_assessment_year",
        "oe_engine_year_reliefs",
        ["assessment_year"],
    )
    op.create_index(
        "ix_oe_engine_year_reliefs_compare_group_id",
        "oe_engine_year_reliefs",
        ["compare_group_id"],
    )

    op.create_table(
        "oe_engine_year_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assessment_year", sa.String(length=16), nullable=False),
        sa.Column("band_index", sa.Integer(), nullable=False),
        sa.Column("lower", sa.String(length=32), nullable=False),
        sa.Column("upper", sa.String(length=32), nullable=True),
        sa.Column("rate_percent", sa.String(length=16), nullable=False),
        sa.Column("applies_to", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("source_doc_id", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("extraction_run_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assessment_year",
            "band_index",
            "applies_to",
            name="uq_oe_engine_year_rates_year_band_applies",
        ),
    )
    op.create_index(
        "ix_oe_engine_year_rates_assessment_year",
        "oe_engine_year_rates",
        ["assessment_year"],
    )


def downgrade() -> None:
    op.drop_table("oe_engine_year_rates")
    op.drop_table("oe_engine_year_reliefs")
    op.drop_table("oe_engine_promoted_runs")
    op.drop_table("oe_engine_promoted_entities")
