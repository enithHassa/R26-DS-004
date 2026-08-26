"""Lift effective_from / effective_to from a quote's own qualifying clause.

GPT often copies the date into `quote` and leaves the structured fields empty
(window w010 of 10/2021). There was no deterministic lift — w008 rows were
filled only when the model happened to populate the fields. This module fills
empty fields from the entity's own quote and does not call the model.

Empty `effective_from` is left empty here. The year compiler then floors
it to the Act's own year (not the 2018 epoch).
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

_MONTH = "|".join(_MONTHS)
# Gazette style: "January 1, 2020" or "1 January 2020"
_DATE_MDY = (
    rf"(?P<month>{_MONTH})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<year>\d{{4}})"
)
_DATE_DMY = (
    rf"(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<month>{_MONTH}),?\s+(?P<year>\d{{4}})"
)
# Longer alternatives first so "commencing on or after" wins over "commencing on".
_FROM_PREFIX = (
    r"(?:commencing\s+on\s+or\s+after|commencing\s+from|on\s+or\s+after|"
    r"with\s+effect\s+from|commencing\s+on)\s+"
)
_PRIOR_PREFIX = r"(?<!or\s)prior\s+to\s+"
_DATE_PHRASE_RE = re.compile(
    r"(?<!or\s)prior\s+to\s+|commencing\s+on\s+or\s+after\s+|commencing\s+from\s+"
    r"|on\s+or\s+after\s+|with\s+effect\s+from\s+|commencing\s+on\s+",
    re.IGNORECASE,
)


def _parse_named_date(match: re.Match[str]) -> date | None:
    month = _MONTHS.get(match.group("month").lower())
    if month is None:
        return None
    try:
        return date(int(match.group("year")), month, int(match.group("day")))
    except ValueError:
        return None


def _first_date(prefix: str, text: str) -> date | None:
    for date_pat in (_DATE_MDY, _DATE_DMY):
        found = re.search(prefix + date_pat, text, flags=re.IGNORECASE)
        if found is not None:
            parsed = _parse_named_date(found)
            if parsed is not None:
                return parsed
    return None


def _iso(value: date) -> str:
    return value.isoformat()


def _day_before(value: date) -> str:
    return _iso(value - timedelta(days=1))


def lift_effective_dates(
    quote: str,
    *,
    effective_from: str = "",
    effective_to: str = "",
) -> tuple[str, str]:
    """Fill empty fields from explicit phrases in `quote`. Never overwrite a set field.

    A quote that contains both a prior-to date and an on-or-after / with-effect-from
    date (two rates in one sentence) only lifts `effective_from`. Filling both would
    produce a contradictory closed window.
    """
    start = (effective_from or "").strip()
    end = (effective_to or "").strip()
    text = quote or ""
    from_date = _first_date(_FROM_PREFIX, text)
    prior_date = _first_date(_PRIOR_PREFIX, text)
    if not start and from_date is not None:
        start = _iso(from_date)
    if not end and prior_date is not None and from_date is None:
        end = _day_before(prior_date)
    return start, end


def fill_effective_dates(entity: dict[str, Any]) -> dict[str, Any]:
    kind = str(entity.get("entity_kind") or "")
    if kind not in {"relief", "rate_band"}:
        return entity
    start, end = lift_effective_dates(
        str(entity.get("quote") or ""),
        effective_from=str(entity.get("effective_from") or ""),
        effective_to=str(entity.get("effective_to") or ""),
    )
    entity["effective_from"] = start
    if kind == "relief" or "effective_to" in entity or end:
        entity["effective_to"] = end
    return entity


def quote_has_effective_phrase(quote: str) -> bool:
    return bool(_DATE_PHRASE_RE.search(quote or ""))


def dates_still_missing(entity: dict[str, Any]) -> bool:
    quote = str(entity.get("quote") or "")
    if not quote_has_effective_phrase(quote):
        return False
    start = str(entity.get("effective_from") or "").strip()
    end = str(entity.get("effective_to") or "").strip()
    from_date = _first_date(_FROM_PREFIX, quote)
    prior_date = _first_date(_PRIOR_PREFIX, quote)
    needs_from = from_date is not None and not start
    needs_to = prior_date is not None and from_date is None and not end
    return needs_from or needs_to
