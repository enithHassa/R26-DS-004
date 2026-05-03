"""extend financial_profiles for Phase 2

Adds demographics, EPF/ETF balances, debt servicing, insurance contributions
and tax-year snapshot fields used by the Financial Profile Module (FR1, FR2)
and the synthetic dataset.

Revision ID: 0002_extend_financial_profile
Revises: 0001_initial
Create Date: 2026-04-29 15:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002_extend_financial_profile"
down_revision: str | None = "0001_initial"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


_NEW_COLUMNS: tuple[tuple[str, sa.types.TypeEngine, object], ...] = (
    ("gender", sa.String(length=16), sa.text("'other'")),
    ("district", sa.String(length=64), sa.text("'Colombo'")),
    ("marital_status", sa.String(length=16), sa.text("'single'")),
    ("years_employed", sa.Integer(), sa.text("0")),
    ("monthly_debt_service", sa.Numeric(14, 2), sa.text("0")),
    ("existing_investments", sa.Numeric(14, 2), sa.text("0")),
    ("epf_balance", sa.Numeric(14, 2), sa.text("0")),
    ("etf_balance", sa.Numeric(14, 2), sa.text("0")),
    ("health_insurance", sa.Boolean(), sa.false()),
    ("life_insurance_premium_annual", sa.Numeric(14, 2), sa.text("0")),
    ("home_loan_interest_annual", sa.Numeric(14, 2), sa.text("0")),
    ("donations_annual", sa.Numeric(14, 2), sa.text("0")),
    ("tax_year", sa.String(length=8), sa.text("'2024_25'")),
)


def upgrade() -> None:
    for name, col_type, default in _NEW_COLUMNS:
        op.add_column(
            "financial_profiles",
            sa.Column(name, col_type, nullable=False, server_default=default),
        )

    op.create_index("ix_financial_profiles_district", "financial_profiles", ["district"])
    op.create_index("ix_financial_profiles_occupation", "financial_profiles", ["occupation"])
    op.create_index("ix_financial_profiles_tax_year", "financial_profiles", ["tax_year"])


def downgrade() -> None:
    op.drop_index("ix_financial_profiles_tax_year", table_name="financial_profiles")
    op.drop_index("ix_financial_profiles_occupation", table_name="financial_profiles")
    op.drop_index("ix_financial_profiles_district", table_name="financial_profiles")

    for name, _col_type, _default in reversed(_NEW_COLUMNS):
        op.drop_column("financial_profiles", name)
