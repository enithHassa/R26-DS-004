"""Split one relief row that states two intra-year caps into two entities.

Gazette style: "Rs. 2,250,000, for first nine months and Rs. 300,000 for
second three months of the year of assessment commencing on April 1, 2022".
Never keep a single averaged or full-year cap when two amounts are stated.
"""

from __future__ import annotations

import copy
import re
from datetime import date
from typing import Any

from oe_engine_app.services.effective_dates import lift_effective_dates

_WORD_MONTHS = {
    "three": 3,
    "six": 6,
    "nine": 9,
    "twelve": 12,
}

_SPLIT_RE = re.compile(
    r"Rs\.?\s*(?P<a>[\d,]+)\s*,?\s*for\s+(?:the\s+)?first\s+"
    r"(?P<n1>nine|six|three|twelve|\d+)\s+months"
    r".{0,120}?"
    r"Rs\.?\s*(?P<b>[\d,]+)\s+for\s+(?:the\s+)?second\s+"
    r"(?P<n2>three|six|nine|twelve|\d+)\s+months",
    re.IGNORECASE | re.DOTALL,
)


def _months(raw: str) -> int | None:
    key = raw.strip().lower()
    if key in _WORD_MONTHS:
        return _WORD_MONTHS[key]
    if key.isdigit():
        value = int(key)
        if 1 <= value <= 12:
            return value
    return None


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, start.day)


def _parse_iso(raw: str) -> date | None:
    text = (raw or "").strip()[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _digits(raw: str) -> str:
    return raw.replace(",", "").strip()


def expand_split_period_relief(entity: dict[str, Any]) -> list[dict[str, Any]]:
    if str(entity.get("entity_kind") or "") != "relief":
        return [entity]
    quote = str(entity.get("quote") or "")
    match = _SPLIT_RE.search(quote)
    if match is None:
        return [entity]
    first_months = _months(match.group("n1"))
    second_months = _months(match.group("n2"))
    if first_months is None or second_months is None:
        return [entity]
    start_s, _end = lift_effective_dates(quote)
    start = _parse_iso(start_s)
    if start is None:
        return [entity]
    mid = _add_months(start, first_months)
    stop = _add_months(start, first_months + second_months)
    cap = _digits(str(entity.get("cap_amount") or ""))
    existing_from = _parse_iso(str(entity.get("effective_from") or ""))
    existing_to = _parse_iso(str(entity.get("effective_to") or ""))
    first_cap = _digits(match.group("a"))
    second_cap = _digits(match.group("b"))
    if cap == first_cap and existing_to == mid:
        return [entity]
    if cap == second_cap and existing_from == mid:
        return [entity]
    first = copy.deepcopy(entity)
    second = copy.deepcopy(entity)
    first["cap_amount"] = _digits(match.group("a"))
    first["effective_from"] = start.isoformat()
    first["effective_to"] = mid.isoformat()
    second["cap_amount"] = _digits(match.group("b"))
    second["effective_from"] = mid.isoformat()
    second["effective_to"] = stop.isoformat()
    second["entry_id"] = f"{entity.get('entry_id')}:b"
    return [first, second]
