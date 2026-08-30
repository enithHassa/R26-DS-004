"""Synthetic monthly financial history generator.

These profiles have only a single current snapshot — there is no real
historical data. To evidence whether a profile's trajectory supports
adopting a recommended strategy, we deterministically generate a plausible
backward trend (income growth, gradual balance accumulation, debt pay-down)
seeded from the profile id, so the same profile always yields the same
history. This is clearly-synthetic demo data, not a claim of real records.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import FinancialProfile as FinancialProfileORM
from app.models.profile_history import ProfileHistorySnapshot as HistoryORM

DEFAULT_MONTHS = 36


def _shift_month(d: date, months_back: int) -> date:
    total = d.year * 12 + (d.month - 1) - months_back
    year, month0 = divmod(total, 12)
    return date(year, month0 + 1, 1)


def _q2(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class MonthlySnapshot:
    snapshot_month: date
    gross_monthly_income: Decimal
    monthly_expenses: Decimal
    liquid_savings: Decimal
    existing_investments: Decimal
    total_debt: Decimal
    epf_balance: Decimal
    etf_balance: Decimal
    savings_rate: float


def _generate(profile: FinancialProfileORM, months: int) -> list[MonthlySnapshot]:
    rng = random.Random(int(profile.id.int) & 0xFFFFFFFF)

    current_income = float(profile.gross_monthly_income)
    current_expenses = float(profile.monthly_expenses)
    current_liquid = float(profile.liquid_savings)
    current_invest = float(profile.existing_investments)
    current_debt = float(profile.total_debt)
    current_epf = float(profile.epf_balance)
    current_etf = float(profile.etf_balance)

    annual_income_growth = rng.uniform(0.02, 0.09)
    monthly_growth = (1 + annual_income_growth) ** (1 / 12) - 1
    expense_ratio_now = current_expenses / current_income if current_income > 0 else 0.0
    expense_ratio_drift = rng.uniform(-0.01, 0.03)

    balance_start_fraction = rng.uniform(0.35, 0.65)
    debt_start_multiplier = rng.uniform(1.05, 1.35)

    today = date.today().replace(day=1)
    anchor = _shift_month(today, 1)  # most recent completed month

    rows: list[MonthlySnapshot] = []
    for months_ago in range(months, 0, -1):
        frac = months_ago / months

        income_noise = rng.gauss(0, 0.015)
        income = max(0.0, current_income / ((1 + monthly_growth) ** months_ago) * (1 + income_noise))

        expense_ratio = expense_ratio_now - expense_ratio_drift * frac
        expense_noise = rng.gauss(0, 0.02)
        expenses = max(0.0, income * max(expense_ratio, 0.05) * (1 + expense_noise))

        liquid = current_liquid * (balance_start_fraction**frac) * (1 + rng.gauss(0, 0.03))
        invest = current_invest * (balance_start_fraction**frac) * (1 + rng.gauss(0, 0.03))
        epf = current_epf * (balance_start_fraction**frac) * (1 + rng.gauss(0, 0.01))
        etf = current_etf * (balance_start_fraction**frac) * (1 + rng.gauss(0, 0.01))
        debt = current_debt * (debt_start_multiplier**frac) if current_debt > 0 else 0.0

        savings_rate = (income - expenses) / income if income > 0 else 0.0

        rows.append(
            MonthlySnapshot(
                snapshot_month=_shift_month(anchor, months_ago - 1),
                gross_monthly_income=_q2(income),
                monthly_expenses=_q2(expenses),
                liquid_savings=_q2(max(0.0, liquid)),
                existing_investments=_q2(max(0.0, invest)),
                total_debt=_q2(max(0.0, debt)),
                epf_balance=_q2(max(0.0, epf)),
                etf_balance=_q2(max(0.0, etf)),
                savings_rate=round(savings_rate, 6),
            )
        )
    return rows


def get_or_create_history(
    db: Session, profile: FinancialProfileORM, months: int = DEFAULT_MONTHS
) -> list[HistoryORM]:
    existing = list(
        db.execute(
            select(HistoryORM)
            .where(HistoryORM.profile_id == profile.id)
            .order_by(HistoryORM.snapshot_month.asc())
        )
        .scalars()
        .all()
    )
    if len(existing) >= months:
        return existing[-months:]

    for row in existing:
        db.delete(row)
    db.flush()

    generated = _generate(profile, months)
    orm_rows = [
        HistoryORM(
            profile_id=profile.id,
            snapshot_month=snap.snapshot_month,
            gross_monthly_income=snap.gross_monthly_income,
            monthly_expenses=snap.monthly_expenses,
            liquid_savings=snap.liquid_savings,
            existing_investments=snap.existing_investments,
            total_debt=snap.total_debt,
            epf_balance=snap.epf_balance,
            etf_balance=snap.etf_balance,
            savings_rate=snap.savings_rate,
        )
        for snap in generated
    ]
    db.add_all(orm_rows)
    db.commit()
    for row in orm_rows:
        db.refresh(row)
    return orm_rows


__all__ = ["DEFAULT_MONTHS", "get_or_create_history"]
