"""Phase 3 Step 9 — extra validation for Lex override relationships (OVERRIDES, MODIFIES, SUPERSEDES)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

LEX_OVERRIDE_REL_TYPES = frozenset({"OVERRIDES", "MODIFIES", "SUPERSEDES"})


def validate_lex_override_row(row: dict[str, Any], *, strict: bool, line_no: int | None = None) -> list[str]:
    """Additional checks for precedence edges. When ``strict``, require provenance fields."""
    loc = f"line {line_no}: " if line_no is not None else ""
    rt = row.get("rel_type")
    if not isinstance(rt, str) or rt not in LEX_OVERRIDE_REL_TYPES:
        return []

    errs: list[str] = []
    if strict:
        sn = (row.get("source_note") or "").strip()
        if not sn:
            errs.append(f"{loc}lex override rel_type {rt} requires non-empty source_note (--strict-lex-overrides)")
        rs = (row.get("review_status") or "").strip()
        if not rs:
            errs.append(f"{loc}lex override rel_type {rt} requires review_status (--strict-lex-overrides)")
    return errs
