"""Year compiler: effective_from window + later amendment wins."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from db.year_views import OeEnginePromotedEntity, OeEngineYearRate, OeEngineYearRelief
from oe_engine_app.services.cap_semantics import strip_threshold_cap
from oe_engine_app.services.cross_reference import attach_covered_items
from oe_engine_app.services.definitions import (
    definitions_for,
    extract_definitions,
    interpretation_section_ref,
)
from oe_engine_app.services.engine_scope import is_promotable_scope
from oe_engine_app.services.extract_dedupe import canonical_compare_group_id, named_window_rank
from oe_engine_app.services.sub_items import sub_items_for
from oe_engine_app.services.terminal_benefit import (
    TERMINAL_BENEFIT_GROUP,
    clip_period_to_year,
    infer_employment_period_condition,
    is_terminal_rate_group,
    stamp_terminal_rate_payload,
)

ASSESSMENT_YEARS: tuple[str, ...] = (
    "2018_19",
    "2019_20",
    "2020_21",
    "2021_22",
    "2022_23",
    "2023_24",
    "2024_25",
    "2025_26",
)

BASE_ASSESSMENT_YEARS: tuple[str, ...] = ASSESSMENT_YEARS

_EPOCH = date(2018, 4, 1)
_DOC_YEAR_RE = re.compile(r"(\d{4})$")

# Fifth Schedule 2(b) employment relief is in Act 24/2017 only. Later Fifth
# Schedule substitutions omit it, so it must not carry forward as last-wins.
# First YA start that must not receive the 24/2017 row: 2020-04-01.
RELIEF_SUNSET_YA_START: dict[str, date] = {
    "employment_income_relief": date(2020, 4, 1),
    # Fifth Schedule 2(f) ended w.e.f. 1 Jan 2023 (Act 45 of 2022). First YA
    # that must not receive the last-wins row: 2023-04-01.
    "expenditure_relief": date(2023, 4, 1),
}

# Fifth Schedule 2(e) (Act 24/2017) was limited to qualifying income up to
# 31 Dec 2019 by Act 10 of 2021 s.55(2)(d). Later consolidated reprints still
# quote the Rs. 15m cap; those reprints must not reopen YA 2020/21+.
RELIEF_HARD_CLOSE_YA_START: dict[str, date] = {
    "foreign_currency_income_relief": date(2020, 4, 1),
}

FOREIGN_CURRENCY_INCOME_THROUGH = date(2019, 12, 31)


def year_start(assessment_year: str) -> date:
    year = int(assessment_year.split("_")[0])
    return date(year, 4, 1)


def year_end(assessment_year: str) -> date:
    start = year_start(assessment_year)
    return date(start.year + 1, 4, 1)


def assessment_year_label(ya_start: date) -> str:
    return f"{ya_start.year}_{str(ya_start.year + 1)[-2:]}"


def extra_new_years(rows: list[OeEnginePromotedEntity]) -> set[str]:
    """YA labels a reviewer opted in with year_kind=NEW_YEAR (may be beyond 2025/26)."""
    extra: set[str] = set()
    for row in rows:
        payload = row.payload_json or {}
        if str(payload.get("year_kind") or "").strip().upper() != "NEW_YEAR":
            continue
        if row.entity_kind not in {"relief", "rate_band"}:
            continue
        extra.add(assessment_year_label(_ya_start_containing(resolved_effective_from(payload))))
    return extra


def derive_assessment_years(rows: list[OeEnginePromotedEntity]) -> tuple[str, ...]:
    """Base catalog is 2018/19–2025/26. NEW_YEAR rows may add a later YA (e.g. 2026/27)."""
    years = set(BASE_ASSESSMENT_YEARS) | extra_new_years(rows)
    base_min = BASE_ASSESSMENT_YEARS[0]
    base_max = BASE_ASSESSMENT_YEARS[-1]

    def _add_from_date(value: date) -> None:
        label = assessment_year_label(_ya_start_containing(value))
        if base_min <= label <= base_max:
            years.add(label)

    for row in rows:
        payload = row.payload_json or {}
        if row.entity_kind not in {"relief", "rate_band"}:
            continue
        if str(payload.get("change_action") or "") == "repeal":
            _add_from_date(resolved_effective_from(payload))
            continue
        _add_from_date(resolved_effective_from(payload))
        effective_to = _parse_iso(str(payload.get("effective_to") or ""))
        if effective_to is not None:
            _add_from_date(effective_to)
    return tuple(sorted(years))


def _parse_iso(raw: str | None) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _ya_start_containing(value: date) -> date:
    if value.month >= 4:
        return date(value.year, 4, 1)
    return date(value.year - 1, 4, 1)


@lru_cache(maxsize=1)
def _manifest_publication_dates() -> dict[str, date]:
    try:
        from oe_engine_app.services.manifest import load_manifest

        payload = load_manifest()
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    out: dict[str, date] = {}
    for row in payload.get("documents") or []:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_doc_id") or "").strip()
        parsed = _parse_iso(str(row.get("publication_date") or ""))
        if source_id and parsed is not None:
            out[source_id] = parsed
    return out


def act_implicit_from(payload: dict[str, Any]) -> date:
    """YA start of the Act that introduced this row, when the quote states no date.

    Uses corpus `publication_date` (certification) when present, else April 1 of
    the year encoded in `source_doc_id` (`oee-act-10-2021` → 2021-04-01). Blank
    fields are not unbounded and do not fall back to the 2018 epoch.

    Dates that fall before the catalog epoch (2018-04-01) clamp to that epoch so
    the principal Act 24 of 2017 (certified Oct 2017) maps to YA 2018/19, not
    2017/18.
    """
    source_id = str(payload.get("source_doc_id") or "").strip()
    published = _manifest_publication_dates().get(source_id)
    if published is not None:
        implicit = _ya_start_containing(published)
    else:
        match = _DOC_YEAR_RE.search(source_id)
        if match:
            year = int(match.group(1))
            if 1990 <= year <= 2100:
                implicit = date(year, 4, 1)
            else:
                return _EPOCH
        else:
            return _EPOCH
    if implicit < _EPOCH:
        return _EPOCH
    return implicit


def resolved_effective_from(payload: dict[str, Any]) -> date:
    stated = _parse_iso(str(payload.get("effective_from") or ""))
    if stated is not None:
        return stated
    return act_implicit_from(payload)


def payload_for_apply(row: OeEnginePromotedEntity) -> dict[str, Any]:
    """Year-window check needs group/source even when JSON omitted them.

    UPDATE rows whose Act date falls after the base catalog are clipped into the
    latest base year (2025/26), matching Catalog Admin “update existing year”.
    NEW_YEAR keeps the stated date so compile can create that later YA.
    """
    payload = dict(row.payload_json or {})
    if not str(payload.get("compare_group_id") or "").strip():
        payload["compare_group_id"] = row.compare_group_id
    if not str(payload.get("source_doc_id") or "").strip():
        payload["source_doc_id"] = row.source_doc_id
    kind = str(payload.get("year_kind") or "").strip().upper()
    if kind == "UPDATE":
        derived = assessment_year_label(_ya_start_containing(resolved_effective_from(payload)))
        if derived > BASE_ASSESSMENT_YEARS[-1]:
            payload["effective_from"] = year_start(BASE_ASSESSMENT_YEARS[-1]).isoformat()
    return payload


def entity_applies(payload: dict[str, Any], assessment_year: str) -> bool:
    start = year_start(assessment_year)
    effective_from = resolved_effective_from(payload)
    effective_to = _parse_iso(str(payload.get("effective_to") or ""))
    if start < effective_from:
        return False
    if effective_to is not None and start >= effective_to:
        return False
    return _relief_open_for_ya_start(
        payload,
        start,
        effective_from=effective_from,
    )


def _relief_open_for_ya_start(
    payload: dict[str, Any],
    ya_start: date,
    *,
    effective_from: date | None = None,
) -> bool:
    """Hard-close / sunset gates shared by compile and interview list filtering."""
    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="relief",
    )
    hard_close = RELIEF_HARD_CLOSE_YA_START.get(group)
    if hard_close is not None and ya_start >= hard_close:
        return False
    if effective_from is None:
        effective_from = resolved_effective_from(payload)
    sunset = RELIEF_SUNSET_YA_START.get(group)
    if sunset is not None and ya_start >= sunset and effective_from < sunset:
        return False
    return True


def relief_interview_visible(payload: dict[str, Any], assessment_year: str) -> bool:
    """Drop hard-closed / sunset reliefs from taxpayer interview (incl. stale views)."""
    start = year_start(assessment_year)
    effective_from = resolved_effective_from(payload)
    effective_to = _parse_iso(str(payload.get("effective_to") or ""))
    if start < effective_from:
        return False
    if effective_to is not None and start >= effective_to:
        return False
    return _relief_open_for_ya_start(
        payload,
        start,
        effective_from=effective_from,
    )


def _sort_key(row: OeEnginePromotedEntity) -> tuple:
    payload = row.payload_json or {}
    effective = resolved_effective_from(payload)
    promoted = row.promoted_at or datetime.min
    return (effective, promoted, row.id or 0)


def _relief_winner_better(row: OeEnginePromotedEntity, current: OeEnginePromotedEntity) -> bool:
    """Later effective date wins; reprints of the same date keep the named schedule."""
    row_key = _sort_key(row)
    cur_key = _sort_key(current)
    if row_key[0] != cur_key[0]:
        return row_key > cur_key
    named_row = named_window_rank(str(row.entry_id or ""))
    named_cur = named_window_rank(str(current.entry_id or ""))
    if named_row != named_cur:
        return named_row < named_cur
    return row_key >= cur_key


# Reliefs the engine has modelled and that genuinely reduce tax on their own.
# A capped relief outside this set is something extraction has newly surfaced:
# it must be claimed, because "notice" plus a cap binds to auto_cap and would
# hand every filer the full amount without them ever entering an expenditure.
AUTO_APPLYING_RELIEF_GROUPS = frozenset(
    {
        "personal_relief",
        "employment_income_relief",
        "rental_income_relief",
        "rent_relief",
        "senior_citizen_interest_income_relief",
        "donation_to_charitable_institution",
        "donation_to_government_or_approved_fund",
        "qualifying_payment_carry_forward",
        "capital_allowance",
    }
)


def _stated_or_default_input_kind(payload: dict[str, Any]) -> str:
    stated = str(payload.get("input_kind") or "").strip()
    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="relief",
    )
    if group == "qp_samurdhi_shop":
        return "amount"
    if group == "foreign_currency_income_relief":
        return "amount"
    if stated:
        return stated
    if group == "personal_relief":
        return "notice"
    if group in {"solar_panel_relief", "qualifying_payments", "donations"}:
        return "yes_no_amount"
    if group == "expenditure_relief":
        return "amount"
    if group in {"rental_income_relief", "rent_relief"}:
        return "boolean"
    return "notice"


def infer_input_kind(payload: dict[str, Any]) -> str:
    kind = _stated_or_default_input_kind(payload)
    if kind != "notice":
        return kind
    # A relief that enumerates its recipients is a list the filer chooses from,
    # so it takes a rupee amount per item instead of applying on its own.
    if payload.get("sub_items"):
        return "amount"
    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="relief",
    )
    if group in AUTO_APPLYING_RELIEF_GROUPS:
        return kind
    # An uncapped relief that states a minimum spend is still expenditure the
    # taxpayer has to declare, so it must be claimable rather than a notice.
    if payload.get("min_qualifying_amount") not in (None, ""):
        return "amount"
    if payload.get("cap_amount") in (None, ""):
        return kind
    # Extraction guesses "notice" freely, and notice + cap binds to auto_cap.
    # For a relief the engine has not modelled that would deduct the full cap
    # from every filer, so make it claim-based instead.
    return "amount"


def infer_engine_binding(payload: dict[str, Any]) -> dict[str, str]:
    binding = payload.get("engine_binding")
    if isinstance(binding, dict) and str(binding.get("kind") or "").strip():
        return {"kind": str(binding.get("kind"))}
    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="relief",
    )
    mapping = {
        "solar_panel_relief": "solar_panel_relief",
        "rental_income_relief": "rent_relief",
        "rent_relief": "rent_relief",
        "qualifying_payments": "qualifying_payments",
        "donations": "donations",
        "senior_citizen_interest_relief": "senior_citizen_interest_relief",
        "expenditure_relief": "filing_line",
        "qp_samurdhi_shop": "filing_line",
        "foreign_currency_income_relief": "filing_line",
    }
    return {"kind": mapping.get(group, "none")}


def _stamp_foreign_currency_year_copy(payload: dict[str, Any], assessment_year: str) -> None:
    """Keep Fifth Schedule 2(e) in 2018/19–2019/20, with the Act 10 income cutoff."""
    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="relief",
    )
    if group != "foreign_currency_income_relief":
        return
    payload["display_name"] = "Foreign currency service income relief"
    if not str(payload.get("effective_from") or "").strip():
        payload["effective_from"] = year_start("2018_19").isoformat()
    if not str(payload.get("effective_to") or "").strip():
        payload["effective_to"] = FOREIGN_CURRENCY_INCOME_THROUGH.isoformat()
    if assessment_year != "2019_20":
        return
    hint = (
        "Qualifying foreign-currency service income is counted only up to "
        "31 December 2019."
    )
    existing = str(payload.get("help") or "").strip()
    if hint.lower() not in existing.lower():
        payload["help"] = f"{existing} {hint}".strip() if existing else hint


def default_question_prompt(payload: dict[str, Any]) -> str:
    """Taxpayer question used when extract / prior catalog did not supply one."""
    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="relief",
    )
    if group == "foreign_currency_income_relief":
        return "What is your qualifying foreign-currency service income?"
    name = str(payload.get("display_name") or payload.get("compare_group_id") or "Relief")
    kind = str(payload.get("input_kind") or "notice")
    if kind == "notice":
        return f"{name} applies automatically for this year of assessment."
    if payload.get("sub_items"):
        return f"{name}: enter an amount for each recipient you gave to this year."
    if kind in {"boolean", "yes_no_amount"}:
        return f"Does {name} apply to you this year?"
    return f"Did you incur {name} this year?"


def load_promoted_entities(
    session: Session,
    *,
    exclude_source_doc_id: str | None = None,
) -> list[OeEnginePromotedEntity]:
    query = session.query(OeEnginePromotedEntity)
    skip = (exclude_source_doc_id or "").strip() or None
    if skip:
        query = query.filter(OeEnginePromotedEntity.source_doc_id != skip)
    return query.all()


def rate_winner_key(payload: dict[str, Any]) -> str:
    """Same taxpayer class despite 'and'/'or' and plural 'individuals'."""
    text = re.sub(r"\s+", " ", str(payload.get("applies_to") or "").strip().lower())
    text = text.replace(" and ", " or ")
    if text.endswith("individuals"):
        text = text[: -len("s")]
    return text


def compile_rate_key(payload: dict[str, Any]) -> str:
    """Last-wins key: ordinary ladders share applies_to; terminal family is independent."""
    applies = rate_winner_key(payload)
    group = canonical_compare_group_id(
        str(payload.get("compare_group_id") or ""),
        entity_kind="rate_band",
    )
    if is_terminal_rate_group(group) or is_terminal_rate_group(
        str(payload.get("compare_group_id") or "")
    ):
        condition = infer_employment_period_condition(payload)
        period_to = str(payload.get("period_to") or "").strip() or "full_ya"
        return f"terminal|{applies}|{condition}|{period_to}"
    return f"ordinary|{applies}"


def entity_overlaps_year(payload: dict[str, Any], assessment_year: str) -> bool:
    """True when [effective_from, effective_to] overlaps the YA (inclusive end date)."""
    ya_start = year_start(assessment_year)
    ya_end = year_end(assessment_year)
    effective_from = resolved_effective_from(payload)
    effective_to = _parse_iso(str(payload.get("effective_to") or ""))
    if effective_from >= ya_end:
        return False
    if effective_to is not None and effective_to < ya_start:
        return False
    return True


def _prepare_rate_payload(
    row: OeEnginePromotedEntity,
    assessment_year: str,
) -> dict[str, Any] | None:
    payload = payload_for_apply(row)
    if is_terminal_rate_group(str(payload.get("compare_group_id") or "")):
        payload = stamp_terminal_rate_payload(payload)
        if not entity_overlaps_year(payload, assessment_year):
            return None
        period_from, period_to = clip_period_to_year(
            ya_start=year_start(assessment_year),
            ya_end=year_end(assessment_year),
            effective_from=resolved_effective_from(payload),
            effective_to=_parse_iso(str(payload.get("effective_to") or "")),
        )
        if period_from > period_to:
            return None
        payload["period_from"] = period_from.isoformat()
        payload["period_to"] = period_to.isoformat()
        payload["compare_group_id"] = TERMINAL_BENEFIT_GROUP
        payload["rule_family"] = TERMINAL_BENEFIT_GROUP
        payload["ladder_key"] = compile_rate_key(payload)
        return payload
    if not entity_applies(payload, assessment_year):
        return None
    payload["ladder_key"] = compile_rate_key(payload)
    return payload


def validate_rate_ladder_key(entity: dict[str, Any]) -> str:
    applies = rate_winner_key(entity)
    group = canonical_compare_group_id(
        str(entity.get("compare_group_id") or ""),
        entity_kind="rate_band",
    )
    if is_terminal_rate_group(group) or is_terminal_rate_group(
        str(entity.get("compare_group_id") or "")
    ):
        return f"terminal|{applies}|{infer_employment_period_condition(entity)}"
    return f"ordinary|{applies}"


def _decimal(value: object) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def validate_rate_band_set(entities: list[dict[str, Any]]) -> list[str]:
    """Validate ordering, overlaps, gaps, and duplicate indices per ladder."""
    errors: list[str] = []
    by_class: dict[str, list[dict[str, Any]]] = {}
    for entity in entities:
        if entity.get("entity_kind") != "rate_band":
            continue
        key = validate_rate_ladder_key(entity)
        by_class.setdefault(key, []).append(entity)
    for applies_to, bands in sorted(by_class.items()):
        ordered = sorted(bands, key=lambda row: int(row.get("band_index") or 0))
        indices = [int(row.get("band_index") or 0) for row in ordered]
        if len(indices) != len(set(indices)):
            errors.append(f"Duplicate band_index for {applies_to or 'taxpayer class'}.")
        prev_upper: float | None = None
        for index, row in enumerate(ordered):
            lower = _decimal(row.get("lower"))
            upper = _decimal(row.get("upper"))
            if lower is None:
                errors.append(f"Band {indices[index]} for {applies_to} missing lower bound.")
                continue
            if index == 0 and lower != 0:
                errors.append(f"First band for {applies_to} must start at 0.")
            if prev_upper is not None and lower not in (prev_upper, prev_upper + 1):
                errors.append(
                    f"Gap or overlap between bands for {applies_to}: "
                    f"expected lower {prev_upper}, got {lower}."
                )
            if upper is not None and upper <= lower:
                errors.append(f"Band {indices[index]} for {applies_to} has upper <= lower.")
            prev_upper = upper
        if ordered and _decimal(ordered[-1].get("upper")) is not None:
            errors.append(f"Top band for {applies_to} should have blank upper bound.")
    return errors


def _repeal_dates(rows: list[OeEnginePromotedEntity]) -> dict[str, date]:
    out: dict[str, date] = {}
    for row in rows:
        if row.entity_kind != "relief":
            continue
        payload = row.payload_json or {}
        if str(payload.get("change_action") or "") != "repeal":
            continue
        group = str(payload.get("compare_group_id") or row.compare_group_id or "")
        group = canonical_compare_group_id(group, entity_kind="relief")
        if not group:
            continue
        repeal_from = resolved_effective_from(payload)
        current = out.get(group)
        if current is None or repeal_from < current:
            out[group] = repeal_from
    return out


def _repealed_for_year(group: str, ya: str, repeal_map: dict[str, date], winner_from: date) -> bool:
    repeal_from = repeal_map.get(group)
    if repeal_from is None:
        return False
    ya_start = year_start(ya)
    return ya_start >= repeal_from and winner_from < repeal_from


def _sub_item_resolver(
    document_text: Callable[[str], str] | None,
) -> Callable[[dict[str, Any]], list[dict[str, str]]]:
    """Split each enumerated relief once, not once per assessment year."""
    cache: dict[tuple[str, str], list[dict[str, str]]] = {}

    def resolve(payload: dict[str, Any]) -> list[dict[str, str]]:
        key = (str(payload.get("source_doc_id") or ""), str(payload.get("quote") or ""))
        if key not in cache:
            document = document_text(key[0]) if document_text is not None else ""
            cache[key] = sub_items_for(payload, document)
        return cache[key]

    return resolve


def _definition_resolver(
    document_text: Callable[[str], str] | None,
) -> Callable[[dict[str, Any]], list[dict[str, str]]]:
    """Scan each Act for defined terms once, not once per relief per year."""
    parsed: dict[str, tuple[dict[str, str], str]] = {}

    def resolve(payload: dict[str, Any]) -> list[dict[str, str]]:
        if document_text is None:
            return []
        source_doc_id = str(payload.get("source_doc_id") or "")
        if source_doc_id not in parsed:
            document = document_text(source_doc_id)
            parsed[source_doc_id] = (
                extract_definitions(document),
                interpretation_section_ref(document),
            )
        definitions, section_ref = parsed[source_doc_id]
        return definitions_for(payload, definitions, section_ref)

    return resolve


def compile_maps(
    rows: list[OeEnginePromotedEntity],
    document_text: Callable[[str], str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    assessment_years = derive_assessment_years(rows)
    reliefs_by_year: dict[str, list[dict[str, Any]]] = {ya: [] for ya in assessment_years}
    rates_by_year: dict[str, list[dict[str, Any]]] = {ya: [] for ya in assessment_years}
    resolve_sub_items = _sub_item_resolver(document_text)
    resolve_definitions = _definition_resolver(document_text)
    repeal_map = _repeal_dates(rows)

    relief_rows = [
        r
        for r in rows
        if r.entity_kind == "relief"
        and is_promotable_scope(r.payload_json or {})
        and str((r.payload_json or {}).get("change_action") or "") != "repeal"
    ]
    rate_rows = [
        r
        for r in rows
        if r.entity_kind == "rate_band" and is_promotable_scope(r.payload_json or {})
    ]

    for ya in assessment_years:
        winners: dict[str, OeEnginePromotedEntity] = {}
        for row in relief_rows:
            if not entity_applies(payload_for_apply(row), ya):
                continue
            payload = payload_for_apply(row)
            group = canonical_compare_group_id(
                str(payload.get("compare_group_id") or row.compare_group_id or ""),
                entity_kind="relief",
            )
            if not group:
                continue
            winner_from = resolved_effective_from(payload)
            if _repealed_for_year(group, ya, repeal_map, winner_from):
                continue
            current = winners.get(group)
            if current is None or _relief_winner_better(row, current):
                winners[group] = row
        for group, row in sorted(winners.items()):
            payload = strip_threshold_cap(payload_for_apply(row))
            payload["compare_group_id"] = group
            items = resolve_sub_items(payload)
            if items:
                payload["sub_items"] = items
            terms = resolve_definitions(payload)
            if terms:
                payload["definitions"] = terms
            payload["input_kind"] = infer_input_kind(payload)
            payload["engine_binding"] = infer_engine_binding(payload)
            if not str(payload.get("question_prompt") or "").strip():
                payload["question_prompt"] = default_question_prompt(payload)
            payload["help"] = str(payload.get("help") or "")
            payload["assessment_year"] = ya
            _stamp_foreign_currency_year_copy(payload, ya)
            reliefs_by_year[ya].append(payload)
        attach_covered_items(reliefs_by_year[ya])

        rate_winners: dict[str, OeEnginePromotedEntity] = {}
        prepared: list[tuple[OeEnginePromotedEntity, dict[str, Any]]] = []
        for row in rate_rows:
            payload = _prepare_rate_payload(row, ya)
            if payload is None:
                continue
            prepared.append((row, payload))
            key = str(payload.get("ladder_key") or compile_rate_key(payload))
            current = rate_winners.get(key)
            if current is None or _sort_key(row) >= _sort_key(current):
                rate_winners[key] = row
        bands: list[dict[str, Any]] = []
        for key, winner in rate_winners.items():
            for row, payload in prepared:
                if row.source_doc_id != winner.source_doc_id:
                    continue
                if str(payload.get("ladder_key") or compile_rate_key(payload)) != key:
                    continue
                bands.append(dict(payload))
        bands.sort(
            key=lambda b: (
                str(b.get("compare_group_id") or ""),
                str(b.get("ladder_key") or ""),
                int(b.get("band_index") or 0),
            )
        )
        for band in bands:
            band["assessment_year"] = ya
        rates_by_year[ya] = bands

    return reliefs_by_year, rates_by_year


def persist_year_views(
    session: Session,
    reliefs_by_year: dict[str, list[dict[str, Any]]],
    rates_by_year: dict[str, list[dict[str, Any]]],
) -> None:
    # Shared SessionLocal is autoflush=False; bulk delete + pending inserts must be
    # flushed or the next SELECT (catalog, calculate, mismatch) sees empty tables.
    session.query(OeEngineYearRelief).delete(synchronize_session=False)
    session.query(OeEngineYearRate).delete(synchronize_session=False)
    session.flush()
    for ya, entries in reliefs_by_year.items():
        if not entries:
            continue
        for payload in entries:
            session.add(
                OeEngineYearRelief(
                    assessment_year=ya,
                    compare_group_id=str(payload.get("compare_group_id") or ""),
                    entry_id=str(payload.get("entry_id") or ""),
                    source_doc_id=str(payload.get("source_doc_id") or ""),
                    cap_amount=None if payload.get("cap_amount") in (None, "") else str(payload.get("cap_amount")),
                    display_name=str(payload.get("display_name") or payload.get("compare_group_id") or ""),
                    unit=str(payload.get("unit") or "lkr"),
                    input_kind=infer_input_kind(payload),
                    payload_json=payload,
                    effective_from=str(payload.get("effective_from") or ""),
                    extraction_run_id=str(payload.get("extraction_run_id") or ""),
                )
            )
    for ya, bands in rates_by_year.items():
        if not bands:
            continue
        for payload in bands:
            upper = payload.get("upper")
            session.add(
                OeEngineYearRate(
                    assessment_year=ya,
                    compare_group_id=str(payload.get("compare_group_id") or "first_schedule_rates"),
                    ladder_key=str(payload.get("ladder_key") or compile_rate_key(payload)),
                    band_index=int(payload.get("band_index") or 0),
                    lower=str(payload.get("lower") or "0"),
                    upper=None if upper in (None, "") else str(upper),
                    rate_percent=str(payload.get("rate_percent") or "0"),
                    applies_to=str(payload.get("applies_to") or ""),
                    source_doc_id=str(payload.get("source_doc_id") or ""),
                    payload_json=payload,
                    effective_from=str(payload.get("effective_from") or ""),
                    extraction_run_id=str(payload.get("extraction_run_id") or ""),
                )
            )
    session.flush()
    allowed = set(reliefs_by_year) | set(rates_by_year) | set(BASE_ASSESSMENT_YEARS)
    _drop_years_outside_catalog(session, allowed_years=allowed)


def _drop_years_outside_catalog(session: Session, allowed_years: set[str] | None = None) -> None:
    """Drop year-view rows outside the compiled catalog (base years plus any NEW_YEAR YA)."""
    from db.mismatch import OeEngineMismatchFlag
    from db.models import OeEngineConsolidatedFact

    allowed = set(BASE_ASSESSMENT_YEARS) if allowed_years is None else set(allowed_years)
    session.query(OeEngineYearRelief).filter(
        ~OeEngineYearRelief.assessment_year.in_(allowed)
    ).delete(synchronize_session=False)
    session.query(OeEngineYearRate).filter(
        ~OeEngineYearRate.assessment_year.in_(allowed)
    ).delete(synchronize_session=False)
    session.query(OeEngineConsolidatedFact).filter(
        ~OeEngineConsolidatedFact.year.in_(allowed)
    ).delete(synchronize_session=False)
    session.query(OeEngineMismatchFlag).filter(
        ~OeEngineMismatchFlag.year.in_(allowed)
    ).delete(synchronize_session=False)
    session.flush()


def _document_text_loader(session: Session) -> Callable[[str], str]:
    """Act text for completing a quote the extractor cut short mid-list.

    Imported here because only a recompile needs chunk text; the pure compile
    path stays free of the ingest layer.
    """
    from oe_engine_app.services.windows import load_doc_text

    cache: dict[str, str] = {}

    def load(source_doc_id: str) -> str:
        if source_doc_id not in cache:
            try:
                cache[source_doc_id] = load_doc_text(session, source_doc_id).stream
            except Exception:
                cache[source_doc_id] = ""
        return cache[source_doc_id]

    return load


def recompile_year_views(
    session: Session,
    *,
    exclude_source_doc_id: str | None = None,
    persist: bool = True,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    session.flush()
    rows = load_promoted_entities(session, exclude_source_doc_id=exclude_source_doc_id)
    reliefs, rates = compile_maps(rows, document_text=_document_text_loader(session))
    if persist and not exclude_source_doc_id:
        persist_year_views(session, reliefs, rates)
    return reliefs, rates
