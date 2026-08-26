"""Resolve "items (i) and (v) of sub-paragraph (b) of paragraph 1" to real text.

Section 52(4) grants carry-forward to two of the ten Fifth Schedule 1(b) donees
but names them only by roman numeral, so the card would otherwise ask a filer to
hold the donee list in their head. The referenced paragraph is already compiled
with its enumeration split into sub-items, so the reference is looked up there
rather than restated in code — if the Act list changes, this follows it.

Only reliefs already in the same year view are searched, so a resolved item can
never cite a provision that is not in force for that year.
"""

from __future__ import annotations

import re
from typing import Any

_ROMAN = r"[ivxIVX]+"
_ITEM_REF_RE = re.compile(
    rf"items?\s+(?P<items>\(\s*{_ROMAN}\s*\)(?:\s*(?:,|and|or|&)\s*\(\s*{_ROMAN}\s*\))*)"
    r"\s+of\s+sub-?\s?paragraph\s*\(\s*(?P<sub>[a-z])\s*\)"
    r"\s+of\s+paragraph\s*(?P<para>\d+)",
    re.IGNORECASE,
)
_ROMAN_IN_BRACKETS_RE = re.compile(rf"\(\s*({_ROMAN})\s*\)")
_PARAGRAPH_REF_RE = re.compile(r"[\s.]+")


class ItemReference:
    """A pointer from one provision to numbered items of another."""

    def __init__(self, romans: list[str], paragraph_ref: str) -> None:
        self.romans = romans
        self.paragraph_ref = paragraph_ref


def parse_item_reference(text: str) -> ItemReference | None:
    match = _ITEM_REF_RE.search(text or "")
    if match is None:
        return None
    romans = [r.lower() for r in _ROMAN_IN_BRACKETS_RE.findall(match.group("items"))]
    if not romans:
        return None
    return ItemReference(romans, f"{match.group('para')}({match.group('sub').lower()})")


def _reference_text(payload: dict[str, Any]) -> str:
    eligibility = payload.get("eligibility")
    parts = [str(payload.get("eligibility_text") or ""), str(payload.get("quote") or "")]
    if isinstance(eligibility, dict):
        parts.insert(0, str(eligibility.get("text") or ""))
    return " ".join(part for part in parts if part)


def _normalise_paragraph_ref(raw: Any) -> str:
    return _PARAGRAPH_REF_RE.sub("", str(raw or "")).lower()


def resolve_covered_items(
    payload: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """The named items of the referenced paragraph, or None when there is no reference."""
    reference = parse_item_reference(_reference_text(payload))
    if reference is None:
        return None
    wanted = _normalise_paragraph_ref(reference.paragraph_ref)
    for other in candidates:
        if other is payload:
            continue
        if _normalise_paragraph_ref(other.get("paragraph_ref")) != wanted:
            continue
        by_roman = {
            str(item.get("roman") or "").lower(): item
            for item in other.get("sub_items") or []
        }
        items = [by_roman[roman] for roman in reference.romans if roman in by_roman]
        if not items:
            continue
        return {
            "paragraph_ref": str(other.get("paragraph_ref") or reference.paragraph_ref),
            "source_group": str(other.get("compare_group_id") or ""),
            "source_display_name": str(other.get("display_name") or ""),
            "source_act_name": str(other.get("act_name") or ""),
            "source_section_ref": str(other.get("section_ref") or ""),
            "items": [dict(item) for item in items],
        }
    return None


def attach_covered_items(reliefs: list[dict[str, Any]]) -> None:
    """Second compile pass: cross-references need every relief for the year first."""
    for payload in reliefs:
        resolved = resolve_covered_items(payload, reliefs)
        if resolved is not None:
            payload["covers"] = resolved
