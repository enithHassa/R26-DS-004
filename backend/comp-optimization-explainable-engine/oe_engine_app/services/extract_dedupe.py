"""Collapse reprint rows so act-admin review matches Catalog Admin's one-row-per-relief result."""

from __future__ import annotations

import re
from typing import Any

from oe_engine_app.services.quote_gate import normalize_for_match
from oe_engine_app.services.terminal_benefit import (
    TERMINAL_RATE_ALIASES,
    infer_employment_period_condition,
    is_terminal_rate_group,
)

_NAMED_WINDOWS = frozenset({"first_schedule", "fifth_schedule", "part_vi_a"})

_RELIEF_GROUP_ALIASES = {
    "personal": "personal_relief",
    "basic_relief": "personal_relief",
    "tax_free_threshold": "personal_relief",
    "digital_productivity": "digital_productivity_equipment_relief",
    "digital_productivity_relief": "digital_productivity_equipment_relief",
    "digital_productivity_equipment": "digital_productivity_equipment_relief",
    "foreign_currency_income": "foreign_currency_income_relief",
    "foreign_currency_relief": "foreign_currency_income_relief",
    "resident_individual_expenditure": "expenditure_relief",
    "fifth_schedule_2_f": "expenditure_relief",
    "contribution_to_samurdhi_shop": "qp_samurdhi_shop",
    "contribution_shop_samurdhi": "qp_samurdhi_shop",
    "samurdhi_shop_contribution": "qp_samurdhi_shop",
    "childcare": "childcare_support_relief",
    "childcare_support": "childcare_support_relief",
    "childcare_relief": "childcare_support_relief",
    "professional_skills": "professional_skills_development_relief",
    "professional_skills_development": "professional_skills_development_relief",
    "ev_charging": "ev_charging_infrastructure_relief",
    "electric_vehicle_charging": "ev_charging_infrastructure_relief",
    "ev_charging_infrastructure": "ev_charging_infrastructure_relief",
}

_RATE_GROUP_ALIASES = {
    "individual_tax_rates": "first_schedule_rates",
    "individual_tax_rates_2026_27": "first_schedule_rates",
    "individual_rate_bands": "first_schedule_rates",
    "individual_progressive_rates": "first_schedule_rates",
    **TERMINAL_RATE_ALIASES,
}

# Definitions / restated caps of a relief already kept under the parent group.
_SUBSUMED_RELIEF_GROUPS = {
    "qualifying_computer_equipment": "digital_productivity_equipment_relief",
    "qualifying_digital_equipment": "digital_productivity_equipment_relief",
    "qualifying_digital_productivity_equipment": "digital_productivity_equipment_relief",
}

_YA_IN_QUESTION_RE = re.compile(
    r"\s*(?:for\s+)?(?:the\s+)?(?:year of assessment|assessment year|YA)\b"
    r"(?:\s+commencing\s+on(?:\s+or\s+after)?)?"
    r"(?:\s+April\s+1,?\s+\d{4})?"
    r"(?:\s+\d{4}/\d{2})?"
    r"(?:\s+\d{4})?",
    re.IGNORECASE,
)
_COMMENCE_DATE_RE = re.compile(
    r"\s*commencing on(?: or after)?\s+April\s+1,?\s+\d{4}",
    re.IGNORECASE,
)
_USED_PRIMARILY_RE = re.compile(
    r"\s+used primarily in(?: the)? production of income",
    re.IGNORECASE,
)
_SPACE_RE = re.compile(r"\s{2,}")


def canonical_compare_group_id(group: str, *, entity_kind: str = "relief") -> str:
    key = (group or "").strip().lower().replace("-", " ").replace(" ", "_")
    key = re.sub(r"_+", "_", key).strip("_")
    if entity_kind == "rate_band":
        return _RATE_GROUP_ALIASES.get(key, key)
    return _RELIEF_GROUP_ALIASES.get(key, key)


def named_window_rank(entry_id: str) -> int:
    """0 for Fifth/First Schedule windows, 1 for numbered reprint windows."""
    return 0 if _window_id({"entry_id": entry_id}) in _NAMED_WINDOWS else 1


def _prefer_year_relief(new: dict[str, Any], old: dict[str, Any]) -> bool:
    new_from = str(new.get("effective_from") or "")
    old_from = str(old.get("effective_from") or "")
    if new_from != old_from:
        return new_from > old_from
    new_named = named_window_rank(str(new.get("entry_id") or ""))
    old_named = named_window_rank(str(old.get("entry_id") or ""))
    if new_named != old_named:
        return new_named < old_named
    return len(str(new.get("quote") or "")) > len(str(old.get("quote") or ""))


def collapse_year_relief_aliases(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One catalog row when extracts used alias compare_group_id values for the same relief."""
    winners: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for entry in entries:
        ranked = dict(entry)
        group = canonical_compare_group_id(
            str(ranked.get("compare_group_id") or ""),
            entity_kind="relief",
        )
        if not group:
            key = f"__ungrouped__{len(order)}"
            winners[key] = ranked
            order.append(key)
            continue
        ranked["compare_group_id"] = group
        existing = winners.get(group)
        if existing is None:
            winners[group] = ranked
            order.append(group)
            continue
        if _prefer_year_relief(ranked, existing):
            winners[group] = ranked
    return [winners[key] for key in order]


def _window_id(entity: dict[str, Any]) -> str:
    entry_id = str(entity.get("entry_id") or "")
    parts = entry_id.split(":")
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return ""


def _rank(entity: dict[str, Any]) -> tuple[int, int, int, int, int]:
    status = str(entity.get("review_status") or "pending")
    status_rank = {"accepted": 0, "pending": 1, "rejected": 2}.get(status, 1)
    window_rank = 0 if _window_id(entity) in _NAMED_WINDOWS else 1
    included_rank = 0 if entity.get("included") else 1
    bounds_rank = (
        0
        if str(entity.get("lower") or "").strip() or str(entity.get("upper") or "").strip()
        else 1
    )
    quote_len = -len(str(entity.get("quote") or ""))
    return (status_rank, window_rank, included_rank, bounds_rank, quote_len)


def _applies_bucket(value: str) -> str:
    fold = normalize_for_match(value)
    if "compan" in fold:
        return "company"
    if "trust fund" in fold:
        return fold
    if "individual" in fold or fold in {"", "person", "a person"}:
        return "individual"
    return fold


def _relief_key(entity: dict[str, Any]) -> tuple[str, ...]:
    group = canonical_compare_group_id(str(entity.get("compare_group_id") or ""), entity_kind="relief")
    cap = str(entity.get("cap_amount") or "").strip()
    start = str(entity.get("effective_from") or "").strip()
    end = str(entity.get("effective_to") or "").strip()
    if cap:
        # Same rupee ceiling is the same fact even when a reprint omitted the date.
        return ("relief", group, cap)
    if start:
        return ("relief-dated", group, start, end)
    quote = normalize_for_match(str(entity.get("quote") or ""))
    return ("relief-quote", group, quote)


def _rate_key(entity: dict[str, Any]) -> tuple[str, ...]:
    group = canonical_compare_group_id(str(entity.get("compare_group_id") or ""), entity_kind="rate_band")
    return (
        "rate_band",
        group,
        str(entity.get("rate_percent") or "").strip(),
        str(entity.get("effective_from") or "").strip(),
        _applies_bucket(str(entity.get("applies_to") or "")),
        infer_employment_period_condition(entity),
    )


def _dedupe_key(entity: dict[str, Any]) -> tuple[str, ...] | None:
    kind = str(entity.get("entity_kind") or "")
    if kind == "relief":
        return _relief_key(entity)
    if kind == "rate_band":
        return _rate_key(entity)
    return None


def collapse_duplicate_extract_entities(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per dated relief / slab when later windows reprint the same fact."""
    winners: dict[tuple[str, ...], dict[str, Any]] = {}
    order: list[tuple[str, ...]] = []
    passthrough: list[dict[str, Any]] = []
    for entity in entities:
        key = _dedupe_key(entity)
        if key is None:
            passthrough.append(dict(entity))
            continue
        current = dict(entity)
        kind = str(current.get("entity_kind") or "")
        current["compare_group_id"] = canonical_compare_group_id(
            str(current.get("compare_group_id") or ""),
            entity_kind=kind,
        )
        existing = winners.get(key)
        if existing is None:
            winners[key] = current
            order.append(key)
            continue
        if _rank(current) < _rank(existing):
            winners[key] = current
    kept: list[dict[str, Any]] = [winners[key] for key in order]
    kept.extend(passthrough)
    present_groups = {
        canonical_compare_group_id(str(row.get("compare_group_id") or ""), entity_kind="relief")
        for row in kept
        if row.get("entity_kind") == "relief"
    }
    trimmed: list[dict[str, Any]] = []
    for row in kept:
        if row.get("entity_kind") != "relief":
            trimmed.append(row)
            continue
        group = canonical_compare_group_id(str(row.get("compare_group_id") or ""), entity_kind="relief")
        parent = _SUBSUMED_RELIEF_GROUPS.get(group)
        if parent and parent in present_groups and parent != group:
            continue
        trimmed.append(row)
    return collapse_competing_rate_ladders(trimmed)


def _rate_applies_key(entity: dict[str, Any]) -> str:
    text = re.sub(r"\s+", " ", str(entity.get("applies_to") or "").strip().lower())
    text = text.replace(" and ", " or ")
    if text.endswith("individuals"):
        text = text[: -len("s")]
    return text


def _ladder_class(entity: dict[str, Any]) -> str:
    applies = _rate_applies_key(entity)
    group = canonical_compare_group_id(
        str(entity.get("compare_group_id") or ""),
        entity_kind="rate_band",
    )
    if is_terminal_rate_group(group) or is_terminal_rate_group(
        str(entity.get("compare_group_id") or "")
    ):
        return f"terminal|{applies}|{infer_employment_period_condition(entity)}"
    return f"ordinary|{applies}"


def _band_float(value: object) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _ladder_contiguous(bands: list[dict[str, Any]]) -> bool:
    if not bands:
        return False
    ordered = sorted(bands, key=lambda row: int(row.get("band_index") or 0))
    indices = [int(row.get("band_index") or 0) for row in ordered]
    if len(indices) != len(set(indices)):
        return False
    prev_upper: float | None = None
    for index, row in enumerate(ordered):
        lower = _band_float(row.get("lower"))
        upper = _band_float(row.get("upper"))
        if lower is None:
            return False
        if index == 0 and lower != 0:
            return False
        if prev_upper is not None and lower not in (prev_upper, prev_upper + 1):
            return False
        if upper is not None and upper <= lower:
            return False
        prev_upper = upper
    return True


def _rate_window_rank(entity: dict[str, Any]) -> int:
    window = _window_id(entity)
    if window == "first_schedule":
        return 0
    if window in _NAMED_WINDOWS:
        return 1
    return 2


def _chain_sort_key(bands: list[dict[str, Any]]) -> tuple:
    window = min((_rate_window_rank(row) for row in bands), default=9)
    latest = max((str(row.get("effective_from") or "") for row in bands), default="")
    first_id = min((str(row.get("entry_id") or "") for row in bands), default="")
    return (1 if _ladder_contiguous(bands) else 0, -window, latest, first_id)


def _entry_token(entity: dict[str, Any]) -> str:
    return str(entity.get("entry_id") or "") or str(id(entity))


def _split_by_window(bands: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    by_window: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for band in bands:
        key = _window_id(band) or "_"
        if key not in by_window:
            order.append(key)
            by_window[key] = []
        by_window[key].append(band)
    return [by_window[key] for key in order]


def _split_lower_zero_chains(bands: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    starts = [band for band in bands if _band_float(band.get("lower")) == 0]
    if len(starts) <= 1:
        return [bands]
    assigned: set[str] = set()
    chains: list[list[dict[str, Any]]] = []
    for start in starts:
        token = _entry_token(start)
        if token in assigned:
            continue
        chain = [start]
        assigned.add(token)
        prev = start
        while True:
            prev_upper = _band_float(prev.get("upper"))
            if prev_upper is None:
                break
            nxt = next(
                (
                    band
                    for band in bands
                    if _entry_token(band) not in assigned
                    and _band_float(band.get("lower")) in (prev_upper, prev_upper + 1)
                ),
                None,
            )
            if nxt is None:
                break
            chain.append(nxt)
            assigned.add(_entry_token(nxt))
            prev = nxt
        chains.append(chain)
    leftover = [band for band in bands if _entry_token(band) not in assigned]
    if leftover:
        chains.append(leftover)
    return chains


def collapse_competing_rate_ladders(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One ordinary / terminal staircase per taxpayer class when an Act reprints an old table.

    A new First Schedule (e.g. 0–1.2M at 5%) plus a consolidated reprint (0–1M at 6%)
    otherwise fails activate with duplicate band_index / gap-or-overlap errors.
    """
    by_class: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        if entity.get("entity_kind") != "rate_band":
            continue
        by_class.setdefault(_ladder_class(entity), []).append(entity)
    keep_ids: set[str] = set()
    for bands in by_class.values():
        if _ladder_contiguous(bands):
            keep_ids.update(_entry_token(band) for band in bands)
            continue
        candidates: list[list[dict[str, Any]]] = []
        for window_bands in _split_by_window(bands):
            if _ladder_contiguous(window_bands):
                candidates.append(window_bands)
            else:
                candidates.extend(_split_lower_zero_chains(window_bands))
        valid = [chain for chain in candidates if _ladder_contiguous(chain)]
        winner = max(valid, key=_chain_sort_key) if valid else bands
        keep_ids.update(_entry_token(band) for band in winner)
    out: list[dict[str, Any]] = []
    for entity in entities:
        if entity.get("entity_kind") != "rate_band":
            out.append(entity)
            continue
        if _entry_token(entity) in keep_ids:
            out.append(entity)
    return out


def _tidy_sentence(text: str, *, question: bool) -> str:
    cleaned = _SPACE_RE.sub(" ", (text or "").strip())
    cleaned = cleaned.strip(" ,;")
    if not cleaned:
        return ""
    if question and "?" not in cleaned:
        cleaned = cleaned.rstrip(".") + "?"
    return cleaned


def scrub_interview_fields(entity: dict[str, Any]) -> dict[str, Any]:
    """Strip dates/caps that belong in structured fields, matching Catalog Admin wording."""
    if str(entity.get("entity_kind") or "") != "relief":
        return entity
    prompt = str(entity.get("question_prompt") or "")
    help_text = str(entity.get("help") or "")
    prompt = _YA_IN_QUESTION_RE.sub("", prompt)
    prompt = _COMMENCE_DATE_RE.sub("", prompt)
    prompt = _USED_PRIMARILY_RE.sub("", prompt)
    prompt = _tidy_sentence(prompt, question=True)
    help_text = _YA_IN_QUESTION_RE.sub("", help_text)
    help_text = _COMMENCE_DATE_RE.sub("", help_text)
    help_text = _tidy_sentence(help_text, question=False)
    prompt_fold = normalize_for_match(prompt)
    help_fold = normalize_for_match(help_text)
    if help_fold and (help_fold == prompt_fold or help_fold in prompt_fold or prompt_fold in help_fold):
        help_text = ""
    entity["question_prompt"] = prompt
    entity["help"] = help_text
    return entity
