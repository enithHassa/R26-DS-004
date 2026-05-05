"""merge migration heads

Revision ID: 02c096e1756f
Revises: 0002_extend_financial_profile, 1368d0abd1f8
Create Date: 2026-05-05 23:21:45.369927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02c096e1756f'
down_revision: Union[str, None] = ('0002_extend_financial_profile', '1368d0abd1f8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
