"""add recommendation_feedback and behavioural_answers tables

Adds the two tables needed to close the "answers -> retrain -> better
recommendations" loop: `recommendation_feedback` records whether a user
actually adopted a recommended strategy (the real adoption signal the
synthetic-trained model currently lacks), and `behavioural_answers` records
a taxpayer's answers to simple financial-behaviour questions.

Revision ID: 0006_add_recommendation_feedback_and_behavioural_answers
Revises: 0005_add_profile_history
Create Date: 2026-08-08 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0006_add_recommendation_feedback_and_behavioural_answers"
down_revision: str | None = "0005_add_profile_history"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_item_id",
            sa.Uuid(),
            sa.ForeignKey("recommendation_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("dismissed_reason", sa.String(length=500), nullable=True),
        sa.Column("user_rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index(
        "ix_recommendation_feedback_recommendation_item_id",
        "recommendation_feedback",
        ["recommendation_item_id"],
    )

    op.create_table(
        "behavioural_answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Uuid(),
            sa.ForeignKey("financial_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question_key", sa.String(length=80), nullable=False),
        sa.Column("answer_value", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("profile_id", "question_key", name="uq_behavioural_answer_profile_question"),
    )
    op.create_index("ix_behavioural_answers_profile_id", "behavioural_answers", ["profile_id"])
    op.create_index("ix_behavioural_answers_question_key", "behavioural_answers", ["question_key"])


def downgrade() -> None:
    op.drop_index("ix_behavioural_answers_question_key", table_name="behavioural_answers")
    op.drop_index("ix_behavioural_answers_profile_id", table_name="behavioural_answers")
    op.drop_table("behavioural_answers")

    op.drop_index(
        "ix_recommendation_feedback_recommendation_item_id", table_name="recommendation_feedback"
    )
    op.drop_table("recommendation_feedback")
