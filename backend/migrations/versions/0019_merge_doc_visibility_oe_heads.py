"""Merge document visibility and OE engine ladder heads.

Revision ID: 0019_merge_doc_visibility_oe_heads
Revises: 0018_add_document_user_visibility, f2g3h4i5j6k7
Create Date: 2026-08-30
"""

from __future__ import annotations

revision: str = "0019_merge_doc_visibility_oe_heads"
down_revision: str | tuple[str, ...] | None = (
    "0018_add_document_user_visibility",
    "f2g3h4i5j6k7",
)
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
