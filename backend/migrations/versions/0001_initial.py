"""initial schema

Creates the Phase 0 baseline tables owned by Component 3:
``users``, ``financial_profiles``, ``tax_strategies``, ``recommendations``,
``recommendation_items``.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-18 22:05:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "financial_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("occupation", sa.String(length=40), nullable=False),
        sa.Column("dependents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gross_monthly_income", sa.Numeric(14, 2), nullable=False),
        sa.Column("monthly_expenses", sa.Numeric(14, 2), nullable=False),
        sa.Column("liquid_savings", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_debt", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("risk_tolerance", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("investment_horizon_years", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("income_sources", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_profiles_user"),
    )
    op.create_index("ix_financial_profiles_user_id", "financial_profiles", ["user_id"])

    op.create_table(
        "tax_strategies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("legal_reference", sa.String(length=200), nullable=True),
        sa.Column("min_income", sa.Numeric(14, 2), nullable=True),
        sa.Column("max_income", sa.Numeric(14, 2), nullable=True),
        sa.Column("min_age", sa.Integer(), nullable=True),
        sa.Column("max_age", sa.Integer(), nullable=True),
        sa.Column("min_liquidity", sa.Numeric(14, 2), nullable=True),
        sa.Column("risk_profile", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("effort_score", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint("code", name="uq_tax_strategies_code"),
    )
    op.create_index("ix_tax_strategies_code", "tax_strategies", ["code"], unique=True)
    op.create_index("ix_tax_strategies_category", "tax_strategies", ["category"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["financial_profiles.id"], ondelete="CASCADE", name="fk_recs_profile"
        ),
    )
    op.create_index("ix_recommendations_profile_id", "recommendations", ["profile_id"])

    op.create_table(
        "recommendation_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("estimated_annual_savings", sa.Numeric(14, 2), nullable=False),
        sa.Column("adoption_probability", sa.Float(), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("scores_json", sa.JSON(), nullable=True),
        sa.Column("explanation_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(
            ["recommendation_id"], ["recommendations.id"], ondelete="CASCADE", name="fk_items_rec"
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"], ["tax_strategies.id"], ondelete="RESTRICT", name="fk_items_strategy"
        ),
    )
    op.create_index("ix_recommendation_items_rec_id", "recommendation_items", ["recommendation_id"])
    op.create_index("ix_recommendation_items_strategy_id", "recommendation_items", ["strategy_id"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_items_strategy_id", table_name="recommendation_items")
    op.drop_index("ix_recommendation_items_rec_id", table_name="recommendation_items")
    op.drop_table("recommendation_items")

    op.drop_index("ix_recommendations_profile_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_tax_strategies_category", table_name="tax_strategies")
    op.drop_index("ix_tax_strategies_code", table_name="tax_strategies")
    op.drop_table("tax_strategies")

    op.drop_index("ix_financial_profiles_user_id", table_name="financial_profiles")
    op.drop_table("financial_profiles")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
