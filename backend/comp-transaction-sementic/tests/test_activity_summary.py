"""Activity summary grouping for auditor document view."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
C1_ROOT = Path(__file__).resolve().parents[1]
for path in (str(REPO_ROOT), str(C1_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.activity_summary import build_activity_summary, classify_activity_row


def test_interest_and_invceft_are_separate_groups() -> None:
    groups = build_activity_summary(
        [
            {
                "row_id": "1",
                "raw_desc": "001020023544:Int.Pd:26-03-2025 to 25-04-2025",
                "amount_lkr": Decimal("26.36"),
                "tx_date": "2025-04-25",
                "direction": "CR",
            },
            {
                "row_id": "2",
                "raw_desc": "NTB_XXXXXX0001 _INVCEFT_NA (S87245)",
                "amount_lkr": Decimal("18000.00"),
                "tx_date": "2025-04-01",
                "direction": "CR",
            },
            {
                "row_id": "3",
                "raw_desc": "NTB_XXXXXX0001 _INVCEFT_NA",
                "amount_lkr": Decimal("25000.00"),
                "tx_date": "2025-04-05",
                "direction": "CR",
            },
        ],
    )
    labels = {g.label: g for g in groups}
    assert "Bank / FD interest" in labels
    assert labels["Bank / FD interest"].count == 1
    assert labels["Bank / FD interest"].total_lkr == Decimal("26.36")
    assert "Inward CEFT / INVCEFT" in labels
    assert labels["Inward CEFT / INVCEFT"].count == 2
    assert labels["Inward CEFT / INVCEFT"].total_lkr == Decimal("43000.00")


def test_groceries_group_keells_and_cargills() -> None:
    groups = build_activity_summary(
        [
            {
                "row_id": "1",
                "raw_desc": "POS Transaction - CARGILLS FOODCITY GANE",
                "amount_lkr": Decimal("3486.04"),
                "tx_date": "2025-04-10",
                "direction": "DR",
            },
            {
                "row_id": "2",
                "raw_desc": "KEELLS SUPER KADAWATHA LKA",
                "amount_lkr": Decimal("2100.00"),
                "tx_date": "2025-04-12",
                "direction": "DR",
            },
        ],
    )
    groceries = next(g for g in groups if g.merchant_family == "groceries")
    assert groceries.count == 2
    assert groceries.total_lkr == Decimal("5586.04")
    assert groceries.direction == "DR"


def test_uber_and_ft_fee_not_merged_by_amount() -> None:
    intent_uber, key_uber, *_ = classify_activity_row(
        raw_desc="UBER EATS CBH LKA",
        direction="DR",
    )
    intent_fee, key_fee, *_ = classify_activity_row(
        raw_desc="FT FEE_SAMP/123",
        direction="DR",
    )
    assert key_uber != key_fee
    assert intent_fee == "BANK_FEE"
