"""Fix assessment_year column to accept longer strings (for year arrays).

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-24 14:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "b8c9d0e1f2g3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    """Change assessment_year from VARCHAR(20) to TEXT to allow JSON arrays."""
    # Modify column type
    op.alter_column(
        'rag_relief_variations',
        'assessment_year',
        type_=sa.Text(),
        existing_type=sa.String(20),
    )


def downgrade():
    """Revert assessment_year back to VARCHAR(20)."""
    op.alter_column(
        'rag_relief_variations',
        'assessment_year',
        type_=sa.String(20),
        existing_type=sa.Text(),
    )
