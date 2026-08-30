"""Add taxpayer submit workflow fields on documents.

Revision ID: 0018_add_document_user_visibility
Revises: 0017_add_tax_computation_snapshots
Create Date: 2026-08-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0018_add_document_user_visibility"
down_revision: str | None = "0017_add_tax_computation_snapshots"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'submitted'")

    op.add_column(
        "documents",
        sa.Column("submitted_by", sa.String(length=16), nullable=False, server_default="auditor"),
    )
    op.add_column(
        "documents",
        sa.Column(
            "user_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Existing completed auditor uploads remain visible to taxpayers in demos.
    op.execute(
        sa.text(
            """
            UPDATE documents
            SET user_visible = true
            WHERE status = 'completed'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("documents", "user_visible")
    op.drop_column("documents", "submitted_by")
