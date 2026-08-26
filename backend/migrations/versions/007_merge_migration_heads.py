"""Merge migration heads from recommendation/adaptive-tax and rag-relief branches.

Revision ID: a7b8c9d0e1f2
Revises: 02e5cdc3d8eb, f6a7b8c9d0e1
Create Date: 2026-08-24 13:05:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "a7b8c9d0e1f2"
down_revision = ("02e5cdc3d8eb", "f6a7b8c9d0e1")
branch_labels = None
depends_on = None


def upgrade():
    """Merge the two migration branches."""
    pass


def downgrade():
    """Downgrade is not supported for merge migrations."""
    pass
