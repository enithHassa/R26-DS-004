"""merge recommendation and adaptive-tax heads

Revision ID: 02e5cdc3d8eb
Revises: 0006_add_recommendation_feedback_and_behavioural_answers, a1b2c3d4e5f6
Create Date: 2026-08-20 13:15:40.238090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '02e5cdc3d8eb'
down_revision: Union[str, None] = ('0006_add_recommendation_feedback_and_behavioural_answers', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
