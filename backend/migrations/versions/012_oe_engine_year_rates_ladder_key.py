"""Split year-rate unique key so ordinary and terminal ladders can coexist.

Revision ID: f2g3h4i5j6k7
Revises: e1f2g3h4i5j6
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2g3h4i5j6k7"
down_revision = "e1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("oe_engine_year_rates")}
    unique_names = {
        uc["name"]
        for uc in inspector.get_unique_constraints("oe_engine_year_rates")
    }
    index_names = {idx["name"] for idx in inspector.get_indexes("oe_engine_year_rates")}

    with op.batch_alter_table("oe_engine_year_rates") as batch:
        if "compare_group_id" not in columns:
            batch.add_column(
                sa.Column(
                    "compare_group_id",
                    sa.String(length=128),
                    nullable=False,
                    server_default="first_schedule_rates",
                )
            )
        if "ladder_key" not in columns:
            batch.add_column(
                sa.Column(
                    "ladder_key",
                    sa.String(length=256),
                    nullable=False,
                    server_default="ordinary|full_ya",
                )
            )
        if "uq_oe_engine_year_rates_year_band_applies" in unique_names:
            batch.drop_constraint("uq_oe_engine_year_rates_year_band_applies", type_="unique")
        if "uq_oe_engine_year_rates_year_group_ladder_band" not in unique_names:
            batch.create_unique_constraint(
                "uq_oe_engine_year_rates_year_group_ladder_band",
                ["assessment_year", "compare_group_id", "ladder_key", "band_index"],
            )
        if "ix_oe_engine_year_rates_compare_group_id" not in index_names:
            batch.create_index("ix_oe_engine_year_rates_compare_group_id", ["compare_group_id"])


def downgrade() -> None:
    with op.batch_alter_table("oe_engine_year_rates") as batch:
        batch.drop_index("ix_oe_engine_year_rates_compare_group_id")
        batch.drop_constraint("uq_oe_engine_year_rates_year_group_ladder_band", type_="unique")
        batch.create_unique_constraint(
            "uq_oe_engine_year_rates_year_band_applies",
            ["assessment_year", "band_index", "applies_to"],
        )
        batch.drop_column("ladder_key")
        batch.drop_column("compare_group_id")
