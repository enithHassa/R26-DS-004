"""add tax_return_detail and section_completion to financial_profiles

Stores the multi-section TaxWise tax return wizard (sections 1–8) as JSON
alongside the flat recommendation profile scalars.

Revision ID: 0012_add_tax_return_detail
Revises: e1f2g3h4i5j6
Create Date: 2026-08-28 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0012_add_tax_return_detail"
down_revision: str | None = "e1f2g3h4i5j6"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_profiles",
        sa.Column("tax_return_detail", sa.JSON(), nullable=True),
    )
    op.add_column(
        "financial_profiles",
        sa.Column("section_completion", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("financial_profiles", "section_completion")
    op.drop_column("financial_profiles", "tax_return_detail")
