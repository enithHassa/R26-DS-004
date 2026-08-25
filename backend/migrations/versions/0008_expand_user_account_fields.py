"""expand users with sign-up account fields

Adds the personal-details columns collected by the new taxpayer sign-up form
(first/last name, contact details, address, date of birth, gender, and an
optional profile picture stored as a data URL). All nullable since existing
seeded/placeholder ``users`` rows only have ``full_name``/``email``.

Revision ID: 0008_expand_user_account_fields
Revises: 0007_expand_financial_profile_fields
Create Date: 2026-08-22 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008_expand_user_account_fields"
down_revision: str | None = "0007_expand_financial_profile_fields"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("mobile_number", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("country", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(length=16), nullable=True))
    op.add_column("users", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("postal_code", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("profile_picture", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "profile_picture")
    op.drop_column("users", "postal_code")
    op.drop_column("users", "city")
    op.drop_column("users", "address")
    op.drop_column("users", "gender")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "country")
    op.drop_column("users", "mobile_number")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
