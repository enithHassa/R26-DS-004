"""Synthetic monthly financial history contracts. See services/history_service.py."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.shared.schemas.common import ORMBase


class ProfileHistorySnapshot(ORMBase):
    snapshot_month: date
    gross_monthly_income: Decimal
    monthly_expenses: Decimal
    liquid_savings: Decimal
    existing_investments: Decimal
    total_debt: Decimal
    epf_balance: Decimal
    etf_balance: Decimal
    savings_rate: float


__all__ = ["ProfileHistorySnapshot"]
