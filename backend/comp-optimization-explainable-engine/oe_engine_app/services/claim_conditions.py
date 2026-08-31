"""Turn Act-stated eligibility, dates, caps, and provisos into interview conditions.

Does not invent IRD documents. If the window never named evidence, proof stays empty.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from oe_engine_app.services.extract_dedupe import canonical_compare_group_id

_PROVIDED = re.compile(
    r"provided\s+that[:,]?\s*(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_WHITESPACE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", (text or "").strip())


def _sentence(text: str) -> str:
    cleaned = _clean(text)
    if not cleaned:
        return ""
    if not re.search(r"[.!?]$", cleaned):
        cleaned += "."
    return cleaned[0].upper() + cleaned[1:] if cleaned else ""


def _format_iso_date(value: str) -> str:
    raw = (value or "").strip()
    try:
        parsed = date.fromisoformat(raw[:10])
    except ValueError:
        return ""
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def _provisos(*blobs: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for blob in blobs:
        match = _PROVIDED.search(_clean(blob))
        if not match:
            continue
        clause = _sentence(match.group(1))
        key = clause.lower()
        if clause and key not in seen:
            seen.add(key)
            found.append(clause)
    return found


def derive_claim_conditions(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Structured conditions copied in substance from the promoted row."""
    eligibility = payload.get("eligibility")
    who = ""
    elig_quote = ""
    if isinstance(eligibility, dict):
        who = _sentence(str(eligibility.get("text") or ""))
        elig_quote = str(eligibility.get("quote") or "")
    else:
        who = _sentence(str(payload.get("eligibility_text") or ""))
        elig_quote = str(payload.get("eligibility_quote") or "")

    quote = str(payload.get("quote") or "")
    stacking = str(payload.get("stacking") or "")
    items: list[dict[str, str]] = []

    if who:
        items.append({"kind": "who", "text": who})

    when = _format_iso_date(str(payload.get("effective_from") or ""))
    if when:
        items.append(
            {
                "kind": "when",
                "text": f"The Act counts expenditure on or after {when}.",
            }
        )

    cap = str(payload.get("cap_amount") or "").strip()
    unit = str(payload.get("unit") or "lkr").lower()
    if cap and unit == "lkr" and cap.replace(".", "", 1).isdigit():
        try:
            amount = int(float(cap))
        except ValueError:
            amount = None
        if amount and amount > 0:
            items.append(
                {
                    "kind": "cap",
                    "text": (
                        f"The Act ceilings this at {amount:,} LKR "
                        "(not more than that cost)."
                    ),
                }
            )

    for proviso in _provisos(quote, elig_quote, stacking):
        items.append({"kind": "restriction", "text": proviso})

    stacking_clean = _sentence(stacking)
    if stacking_clean and not _PROVIDED.search(stacking):
        items.append({"kind": "stacking", "text": stacking_clean})

    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="relief",
    )
    ya = str(payload.get("assessment_year") or "")
    quote_has_2019_cutoff = re.search(
        r"up\s*to\s+(?:31(?:st)?\s+december|december\s+31(?:st)?),?\s+2019",
        quote,
        flags=re.IGNORECASE,
    )
    if group == "foreign_currency_income_relief" and (
        ya == "2019_20" or (not ya and quote_has_2019_cutoff)
    ):
        cutoff = (
            "Qualifying income is counted only up to 31 December 2019."
        )
        if cutoff.lower() not in " ".join(item["text"] for item in items).lower():
            items.append({"kind": "restriction", "text": cutoff})

    return items


def derive_proof(payload: dict[str, Any]) -> dict[str, Any]:
    """Documents the Act named, or a flag that it named none."""
    raw = payload.get("required_evidence")
    named: list[str] = []
    if isinstance(raw, list):
        seen: set[str] = set()
        for item in raw:
            text = _clean(str(item))
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                named.append(text)
    return {
        "named_by_act": named,
        "act_names_documents": bool(named),
    }
