"""Dialog Finance consolidated statement PDF text layout."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

C1_ROOT = Path(__file__).resolve().parents[1]
if str(C1_ROOT) not in sys.path:
    sys.path.insert(0, str(C1_ROOT))

from app.services import document_extractor as de  # noqa: E402


def test_dialog_finance_multiline_and_single_line_rows() -> None:
    lines = """
Consolidated Individual Monthly Statement
Statement Period : 01-04-2025 to 30-04-2025
https://www.dialogfinance.lk/
21,487.2401-Apr-2025 01-Apr-2025 NTB_XXXXXX0001
_INVCEFT_NA
S87245 18,000.00 0.00
3,487.2401-Apr-2025 01-Apr-2025 FT
TO_COMB-2000021
375-PIYUMI
DISSANAYAKE
012680 0.00 18,000.00
327.2920-Apr-2025 20-Apr-2025 FT FEE_BOC/481107 015215 0.00 15.00
Investments Summary wdfhdack
""".strip().splitlines()

    out = de._parse_statement_lines_from_text(lines, None, file_type="pdf")
    assert out.statement_context is not None
    assert out.statement_context.bank_code == "DIALOG_FINANCE"
    assert len(out.rows) == 3
    assert out.rows[0].amount_lkr == Decimal("18000.00")
    assert out.rows[0].direction.value == "CR"
    assert "NTB" in out.rows[0].raw_desc
    assert out.rows[1].amount_lkr == Decimal("18000.00")
    assert out.rows[1].direction.value == "DR"
    assert out.rows[2].amount_lkr == Decimal("15.00")
    assert out.rows[2].direction.value == "DR"


def test_detect_bank_from_dialog_pdf_probe() -> None:
    from app.services.bank_detection import detect_bank

    probe = (
        "Consolidated Individual Monthly Statement\n"
        "financialservice@dialog.lk\n"
        "https://www.dialogfinance.lk/\n"
    )
    r = detect_bank(filename="stmt.pdf", text_probe=probe)
    assert r.bank_code == "DIALOG_FINANCE"
    assert r.confidence >= 0.35
