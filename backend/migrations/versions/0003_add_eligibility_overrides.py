"""add eligibility_overrides to financial_profiles

Lets a user manually pin an eligibility flag on/off for a profile,
overriding the value the rules engine would otherwise compute.

Revision ID: 0003_add_eligibility_overrides
Revises: 7109b7d4c2a8
Create Date: 2026-08-08 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_eligibility_overrides"
down_revision: str | None = "7109b7d4c2a8"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_profiles",
        sa.Column(
            "eligibility_overrides",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("financial_profiles", "eligibility_overrides")
