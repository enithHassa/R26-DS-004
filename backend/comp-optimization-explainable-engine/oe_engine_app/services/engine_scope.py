"""Taxpayer class for year-table promote. Individual interview vs other entities."""

from __future__ import annotations

import re
from typing import Any, Literal

EngineScope = Literal["individual", "other"]

_INDIVIDUAL_RE = re.compile(
    r"\b(individuals?|resident\s+individual|non-resident\s+individual|"
    r"natural\s+person)\b",
    re.IGNORECASE,
)

# Taxpayer classes that must not enter the individual slab/relief engine.
# Do not use a bare "fund" substring (would match "refund").
_OTHER_TAXPAYER_RE = re.compile(
    r"\b("
    r"employees['’]?\s+trust|"
    r"trust\s+funds?|"
    r"unit\s+trusts?|"
    r"trusts?|"
    r"provident|"
    r"pension\s+funds?|"
    r"gratuity|"
    r"termination\s+funds?|"
    r"companies|"
    r"company|"
    r"corporate|"
    r"corporation|"
    r"partnerships|"
    r"partnership|"
    r"body\s+of\s+persons|"
    r"institutions?|"
    r"institutional|"
    r"non[\s-]?governmental|"
    r"ngos?|"
    r"n\.g\.o\.?s?|"
    r"organisations?|"
    r"organizations?|"
    r"entities|"
    r"entity|"
    r"funds|"
    r"fund"
    r")\b",
    re.IGNORECASE,
)


def _haystack(
    *,
    applies_to: str = "",
    display_name: str = "",
    eligibility_text: str = "",
    compare_group_id: str = "",
    band_label: str = "",
) -> str:
    return " ".join(
        part
        for part in (
            applies_to,
            display_name,
            eligibility_text,
            compare_group_id.replace("_", " "),
            band_label,
        )
        if (part or "").strip()
    )


def infer_engine_scope(
    *,
    applies_to: str = "",
    display_name: str = "",
    eligibility_text: str = "",
    compare_group_id: str = "",
    band_label: str = "",
) -> EngineScope:
    text = _haystack(
        applies_to=applies_to,
        display_name=display_name,
        eligibility_text=eligibility_text,
        compare_group_id=compare_group_id,
        band_label=band_label,
    )
    has_individual = bool(_INDIVIDUAL_RE.search(text))
    has_other = bool(_OTHER_TAXPAYER_RE.search(text))
    if has_other and not has_individual:
        return "other"
    if has_individual:
        return "individual"
    if has_other:
        return "other"
    return "individual"


def infer_engine_scope_from_entity(entity: dict[str, Any]) -> EngineScope:
    eligibility = entity.get("eligibility") or {}
    eligibility_text = ""
    if isinstance(eligibility, dict):
        eligibility_text = str(eligibility.get("text") or "")
    return infer_engine_scope(
        applies_to=str(entity.get("applies_to") or ""),
        display_name=str(entity.get("display_name") or ""),
        eligibility_text=eligibility_text,
        compare_group_id=str(entity.get("compare_group_id") or ""),
        band_label=str(entity.get("band_label") or ""),
    )


def resolve_engine_scope(entity: dict[str, Any]) -> EngineScope:
    """Stored tag or inference; other wins so a bad individual tag cannot promote."""
    inferred = infer_engine_scope_from_entity(entity)
    stored = str(entity.get("engine_scope") or "").strip().lower()
    if stored == "other" or inferred == "other":
        return "other"
    if stored == "individual":
        return "individual"
    return inferred


def is_promotable_scope(entity: dict[str, Any]) -> bool:
    return resolve_engine_scope(entity) == "individual"
