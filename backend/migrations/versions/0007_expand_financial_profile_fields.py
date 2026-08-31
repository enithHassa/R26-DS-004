"""expand financial_profiles with new profile fields

Adds residency status/nationality, employment type/sector, annual bonus,
vehicle/property values, and a retirement age target so the Create Profile
form can capture a fuller financial picture.

NOTE: this intentionally chains off "0006_..." only, not off the other
existing head "a1b2c3d4e5f6" (adaptive tax amendment tables). That other
branch creates columns typed ``postgresql.JSONB``, which fails on SQLite
dev databases (DATABASE_MODE=sqlite) — merging the two heads here would
force every sqlite dev environment through that incompatible migration.
The two heads pre-date this migration and merging them is a separate
piece of work (fixing the JSONB typing to be dialect-agnostic) — tracked
as a known gap, not addressed here.

Revision ID: 0007_expand_financial_profile_fields
Revises: 0006_add_recommendation_feedback_and_behavioural_answers
Create Date: 2026-08-17 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007_expand_financial_profile_fields"
down_revision: str | None = "0006_add_recommendation_feedback_and_behavioural_answers"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_profiles",
        sa.Column("residency_status", sa.String(16), nullable=False, server_default="resident"),
    )
    op.add_column(
        "financial_profiles",
        sa.Column("nationality", sa.String(64), nullable=True),
    )
    op.add_column(
        "financial_profiles",
        sa.Column("employment_type", sa.String(16), nullable=False, server_default="permanent"),
    )
    op.add_column(
        "financial_profiles",
        sa.Column("employer_sector", sa.String(16), nullable=False, server_default="private"),
    )
    op.add_column(
        "financial_profiles",
        sa.Column(
            "annual_bonus_lkr",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "financial_profiles",
        sa.Column(
            "vehicle_value",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "financial_profiles",
        sa.Column(
            "property_value",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "financial_profiles",
        sa.Column("retirement_age_target", sa.Integer(), nullable=False, server_default="60"),
    )


def downgrade() -> None:
    op.drop_column("financial_profiles", "retirement_age_target")
    op.drop_column("financial_profiles", "property_value")
    op.drop_column("financial_profiles", "vehicle_value")
    op.drop_column("financial_profiles", "annual_bonus_lkr")
    op.drop_column("financial_profiles", "employer_sector")
    op.drop_column("financial_profiles", "employment_type")
    op.drop_column("financial_profiles", "nationality")
    op.drop_column("financial_profiles", "residency_status")
