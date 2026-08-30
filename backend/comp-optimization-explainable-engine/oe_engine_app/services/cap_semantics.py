"""Tell a deduction ceiling apart from an eligibility threshold.

"not exceeding twenty-five million rupees" caps what may be deducted.
"not less than five million rupees" is the spend required to qualify at all —
carrying it as `cap_amount` would silently cap the claim at the entry price.
The distinction is read off the quote, so it needs no second model call.
"""

from __future__ import annotations

import re
from typing import Any

_CEILING_RE = re.compile(
    r"not\s+exceeding|shall\s+not\s+exceed|up\s+to|maximum|at\s+most|whichever\s+is\s+less",
    re.IGNORECASE,
)
_THRESHOLD_RE = re.compile(
    r"not\s+less\s+than|no\s+less\s+than|at\s+least|minimum\s+of|or\s+more",
    re.IGNORECASE,
)

# "not less than five million rupees" / "not less than Rs. 5,000,000"
_WORD_MILLIONS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "twenty-five": 25,
    "thirty": 30,
    "fifty": 50,
}
_THRESHOLD_AMOUNT_RE = re.compile(
    r"(?:not\s+less\s+than|no\s+less\s+than|at\s+least|minimum\s+of)\s+"
    r"(?:rs\.?\s*|rupees?\s*)?"
    r"(?:"
    r"(?P<digits>[\d,]+(?:\.\d+)?)\s*(?P<digit_scale>million)?"
    r"|"
    r"(?P<words>twenty-five|twenty|thirty|fifteen|eleven|twelve|fifty|"
    r"one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s+million"
    r")",
    re.IGNORECASE,
)


def cap_is_threshold(quote: str, cap_amount: Any) -> bool:
    """True when the quoted figure gates eligibility instead of limiting relief."""
    if cap_amount in (None, ""):
        return False
    text = quote or ""
    return bool(_THRESHOLD_RE.search(text)) and not _CEILING_RE.search(text)


def quote_is_threshold_only(quote: str) -> bool:
    """True when the quote states a minimum spend without a deduction ceiling."""
    text = quote or ""
    return bool(_THRESHOLD_RE.search(text)) and not _CEILING_RE.search(text)


def parse_threshold_amount_from_quote(quote: str) -> str | None:
    """Pull the eligibility floor from Act wording when extraction left cap empty."""
    if not quote_is_threshold_only(quote):
        return None
    match = _THRESHOLD_AMOUNT_RE.search(quote or "")
    if not match:
        return None
    words = match.group("words")
    if words:
        millions = _WORD_MILLIONS.get(words.lower())
        return str(millions * 1_000_000) if millions else None
    digits = match.group("digits")
    if not digits:
        return None
    try:
        value = float(digits.replace(",", ""))
    except ValueError:
        return None
    if match.group("digit_scale"):
        value *= 1_000_000
    if value <= 0:
        return None
    return str(int(value) if value == int(value) else value)


def strip_threshold_cap(payload: dict[str, Any]) -> dict[str, Any]:
    """Move an entry threshold out of `cap_amount` without discarding the figure.

    It is kept as `min_qualifying_amount` because the relief is uncapped but not
    unconditional, and because a relief that loses its cap would otherwise fall
    back to a notice and become unclaimable.
    """
    out = dict(payload)
    changed = False
    if cap_is_threshold(str(out.get("quote") or ""), out.get("cap_amount")):
        out["min_qualifying_amount"] = str(out["cap_amount"])
        out["cap_amount"] = None
        changed = True
    if out.get("min_qualifying_amount") in (None, ""):
        parsed = parse_threshold_amount_from_quote(str(out.get("quote") or ""))
        if parsed:
            out["min_qualifying_amount"] = parsed
            changed = True
    return out if changed else payload

def normalize_relief_amounts(entry: dict[str, Any]) -> dict[str, Any]:
    """Apply-time view: thresholds never act as deduction ceilings."""
    return strip_threshold_cap(entry)