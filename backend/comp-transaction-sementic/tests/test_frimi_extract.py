"""FriMi PDF text layout (pypdf often emits one token per line)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

C1_ROOT = Path(__file__).resolve().parents[1]
if str(C1_ROOT) not in sys.path:
    sys.path.insert(0, str(C1_ROOT))

from app.services import document_extractor as de  # noqa: E402
from app.services.bank_detection import detect_bank  # noqa: E402


def test_frimi_tokenized_multiline_row_and_footer_skip() -> None:
    lines = """
www.frimi.lk
From
2222298247
01-Aug-2023
To
31-Aug-2023
Entry
Date
01-Aug-2023
01-Aug-2023
FriMi Fund Transfer From 2222378211
  S935206
0.00
8,100.00
8,120.78
02-Aug-2023
02-Aug-2023
CEFTS
S176673
0.00
1,000.00
6,120.78
""".strip().splitlines()

    out = de._parse_statement_lines_from_text(lines, None, file_type="pdf")
    assert out.statement_context is not None
    assert out.statement_context.bank_code == "FRIMI"
    assert len(out.rows) == 2
    assert out.rows[0].amount_lkr == Decimal("8100.00")
    assert out.rows[0].direction.value == "CR"
    assert out.rows[1].amount_lkr == Decimal("1000.00")


def test_detect_frimi_from_probe() -> None:
    r = detect_bank(
        filename="stmt.pdf",
        text_probe="FriMi Fund Transfer To 2222249213\nwww.frimi.lk\n",
    )
    assert r.bank_code == "FRIMI"
