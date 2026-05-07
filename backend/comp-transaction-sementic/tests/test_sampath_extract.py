"""Sampath statement layout parsing (PDF text and PNG OCR output)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

C1_ROOT = Path(__file__).resolve().parents[1]
if str(C1_ROOT) not in sys.path:
    sys.path.insert(0, str(C1_ROOT))

from app.services import document_extractor as de  # noqa: E402


def test_merge_split_ocr_lines_joins_date_only_with_next_line() -> None:
    raw = [
        "01APR2026",
        "622.17Cr",
        "06Ar26",
        "KIRIBATH SalaryMAR26 Enit 41,387.00 42,009.17Cr",
    ]
    merged = de._merge_split_ocr_lines(raw)
    assert merged == [
        "01APR2026 622.17Cr",
        "06Ar26 KIRIBATH SalaryMAR26 Enit 41,387.00 42,009.17Cr",
    ]


def test_sampath_parse_after_split_lines_like_ocr() -> None:
    lines = """
Sampath Bank PLC
Statement Period: 01-04-2026 to 30-04-2026
01APR2026
622.17Cr
06Ar26
KIRIBATH SalaryMAR26 Enit 41,387.00 42,009.17Cr
10Apr26 GAMPAHA VSRTFR 3,000.00 39,009.17Cr
""".strip().splitlines()
    merged = de._merge_split_ocr_lines(lines)
    out = de._parse_statement_lines_from_text(merged, "SAMPATH", file_type="png")
    assert len(out.rows) >= 3
    assert out.rows[0].amount_lkr == Decimal("622.17")
    assert out.rows[1].amount_lkr == Decimal("41387.00")
    assert out.rows[2].amount_lkr == Decimal("3000.00")


def test_sampath_compact_dates_and_balance_direction() -> None:
    lines = """
Sampath Bank PLC
Statement Period: 01-04-2026 to 30-04-2026
DATE PARTICULARS DEBITS CREDITS BALANCE
01APR2026 Balance Brought Forward 622.17
06Apr26 KIRIBATH SalaryMAR26 41,387.00 42,009.17
10Apr26 GAMPAHA VSRTFR 3,000.00 39,009.17
29Apr2026 C/F Closing 6,386.71
Total Debits 37,243.05
""".strip().splitlines()

    out = de._parse_statement_lines_from_text(lines, "SAMPATH", file_type="png")
    assert out.statement_context is not None
    assert out.statement_context.period_start is not None
    assert out.statement_context.bank_code == "SAMPATH"
    assert len(out.rows) == 3
    assert "balance" in out.rows[0].raw_desc.lower()
    assert out.rows[0].amount_lkr == Decimal("622.17")
    assert out.rows[1].direction.value == "CR"
    assert out.rows[1].amount_lkr == Decimal("41387.00")
    assert out.rows[2].direction.value == "DR"
    assert out.rows[2].amount_lkr == Decimal("3000.00")


def test_sampath_opening_cr_only_and_ocr_ar_typo_for_apr() -> None:
    """Opening line without 'balance' wording; Apr misread as Ar (06Ar26)."""
    lines = """
Sampath Bank PLC
Statement Period: 01-04-2026 to 30-04-2026
01APR2026 622.17Cr
06Ar26 KIRIBATH SalaryMAR26 Enit 41,387.00 42,009.17
""".strip().splitlines()

    out = de._parse_statement_lines_from_text(lines, "SAMPATH", file_type="png")
    assert len(out.rows) == 2
    assert out.rows[0].amount_lkr == Decimal("622.17")
    assert "Opening" in out.rows[0].raw_desc
    assert out.rows[1].tx_date == "2026-04-06"
    assert out.rows[1].amount_lkr == Decimal("41387.00")
    assert out.rows[1].direction.value == "CR"
