"""add password to users, backfill from existing full_name

Adds a plaintext login password column to ``users`` (username = full_name)
for the customer-facing "User View" dashboard, and backfills a password for
already-seeded rows so existing demo profiles (e.g. Taxpayer_25265) can log
in immediately.

Revision ID: 0004_add_user_password
Revises: 0003_add_eligibility_overrides
Create Date: 2026-08-08 00:00:00
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_user_password"
down_revision: str | None = "0003_add_eligibility_overrides"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

_TAXPAYER_RE = re.compile(r"Taxpayer_0*(\d+)")


def _derive_password(full_name: str | None) -> str:
    if full_name:
        match = _TAXPAYER_RE.fullmatch(full_name)
        if match:
            return f"{match.group(1)}@Tax"
    return "changeme@Tax"


def upgrade() -> None:
    op.add_column("users", sa.Column("password", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Uuid()), sa.column("full_name", sa.String()), sa.column("password", sa.String()))
    rows = bind.execute(sa.select(users.c.id, users.c.full_name)).fetchall()
    for row in rows:
        bind.execute(
            users.update().where(users.c.id == row.id).values(password=_derive_password(row.full_name))
        )


def downgrade() -> None:
    op.drop_column("users", "password")
