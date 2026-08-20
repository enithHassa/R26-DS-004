"""widen rule_source.amends_section for verbose GPT labels

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-05 17:15:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "rule_source",
        "amends_section",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "rule_source",
        "amends_section",
        existing_type=sa.Text(),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
