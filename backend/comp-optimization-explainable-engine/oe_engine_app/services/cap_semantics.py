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


def cap_is_threshold(quote: str, cap_amount: Any) -> bool:
    """True when the quoted figure gates eligibility instead of limiting relief."""
    if cap_amount in (None, ""):
        return False
    text = quote or ""
    return bool(_THRESHOLD_RE.search(text)) and not _CEILING_RE.search(text)


def strip_threshold_cap(payload: dict[str, Any]) -> dict[str, Any]:
    """Move an entry threshold out of `cap_amount` without discarding the figure.

    It is kept as `min_qualifying_amount` because the relief is uncapped but not
    unconditional, and because a relief that loses its cap would otherwise fall
    back to a notice and become unclaimable.
    """
    if not cap_is_threshold(str(payload.get("quote") or ""), payload.get("cap_amount")):
        return payload
    out = dict(payload)
    out["min_qualifying_amount"] = str(out["cap_amount"])
    out["cap_amount"] = None
    return out
