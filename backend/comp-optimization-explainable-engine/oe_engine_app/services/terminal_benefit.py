"""Qualifying employment terminal-benefit First Schedule ladders.

Ordinary individual progressive bands stay `first_schedule_rates`. These tables
tax only specified terminal/employment benefits, never ordinary salary.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

TERMINAL_BENEFIT_GROUP = "terminal_benefit_tax_rate"

TERMINAL_RATE_ALIASES = {
    "employment_income_tax": TERMINAL_BENEFIT_GROUP,
    "employment_income": TERMINAL_BENEFIT_GROUP,
    "employment_income_tax_20_years": TERMINAL_BENEFIT_GROUP,
    "terminal_benefit_tax_rate": TERMINAL_BENEFIT_GROUP,
    "terminal_benefit_rates": TERMINAL_BENEFIT_GROUP,
    "terminal_benefit_tax_rates": TERMINAL_BENEFIT_GROUP,
}

PERIOD_UPTO_20 = "upto_20_years"
PERIOD_OVER_20 = "over_20_years"
PERIOD_NA = "not_applicable"

QUALIFYING_INCOME_TYPES = (
    "commuted_pension",
    "retiring_gratuity",
    "loss_of_office_compensation",
    "etf_retirement_payment",
)

LOSS_OF_OFFICE_TYPE = "loss_of_office_compensation"

BASE_ACT_NAME = "Inland Revenue Act No. 24 of 2017"
AMENDMENT_ACT_10_NAME = "Inland Revenue (Amendment) Act No. 10 of 2021"

TERMINAL_2017_FROM = date(2018, 4, 1)
TERMINAL_2017_THROUGH = date(2019, 12, 31)
TERMINAL_ACT10_FROM = date(2020, 1, 1)

PERIOD_PRE_2020 = "pre_2020"
PERIOD_FROM_2020 = "from_2020_01_01"


def is_terminal_rate_group(group: str) -> bool:
    key = (group or "").strip().lower().replace("-", "_")
    if key in TERMINAL_RATE_ALIASES:
        return True
    return key == TERMINAL_BENEFIT_GROUP


def canonical_terminal_group(group: str) -> str:
    key = (group or "").strip().lower().replace("-", " ").replace(" ", "_")
    key = "_".join(part for part in key.split("_") if part)
    return TERMINAL_RATE_ALIASES.get(key, key)


def _as_int(raw: Any) -> int | None:
    text = str(raw or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def infer_employment_period_condition(payload: dict[str, Any]) -> str:
    stated = str(payload.get("employment_period_condition") or "").strip()
    if stated in {PERIOD_UPTO_20, PERIOD_OVER_20, PERIOD_NA}:
        return stated
    group = str(payload.get("compare_group_id") or "")
    if "20_years" in group or "over_20" in group:
        return PERIOD_OVER_20
    quote = f"{payload.get('quote') or ''} {payload.get('band_label') or ''} {payload.get('applies_to') or ''}"
    fold = quote.lower()
    if "more than twenty" in fold or "exceeding twenty" in fold or "> 20" in fold:
        return PERIOD_OVER_20
    if "not exceeding twenty" in fold or "twenty years or less" in fold or "<= 20" in fold:
        return PERIOD_UPTO_20
    first_upper = _as_int(payload.get("upper")) if str(payload.get("band_index") or "1") in {"1", "0"} else None
    if first_upper == 5_000_000:
        return PERIOD_OVER_20
    if first_upper == 2_000_000:
        return PERIOD_UPTO_20
    if first_upper == 10_000_000 or _as_int(payload.get("upper")) == 10_000_000:
        return PERIOD_NA
    lower = _as_int(payload.get("lower"))
    if lower in {10_000_000, 20_000_000}:
        return PERIOD_NA
    if lower in {2_000_001, 3_000_001} or _as_int(payload.get("upper")) in {2_000_000, 3_000_000}:
        return PERIOD_UPTO_20
    if lower in {5_000_001, 6_000_001} or _as_int(payload.get("upper")) in {5_000_000, 6_000_000}:
        return PERIOD_OVER_20
    if group in {"employment_income", "employment_income_tax_rate"}:
        return PERIOD_NA
    if "employment_income_tax" in group and "20" not in group:
        return PERIOD_UPTO_20
    return PERIOD_NA


def ladder_key(payload: dict[str, Any]) -> str:
    condition = infer_employment_period_condition(payload)
    period_to = str(payload.get("period_to") or "").strip() or "full_ya"
    return f"{condition}|{period_to}"


def default_qualifying_types() -> list[str]:
    return list(QUALIFYING_INCOME_TYPES)


def stamp_terminal_rate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Fill family metadata without rewriting the Act quote."""
    if not is_terminal_rate_group(str(payload.get("compare_group_id") or "")):
        return payload
    condition = infer_employment_period_condition(payload)
    payload["compare_group_id"] = TERMINAL_BENEFIT_GROUP
    payload["rule_family"] = TERMINAL_BENEFIT_GROUP
    payload["employment_period_condition"] = condition
    types = payload.get("qualifying_income_types")
    if not isinstance(types, list) or not types:
        payload["qualifying_income_types"] = default_qualifying_types()
    source = str(payload.get("source_doc_id") or "")
    if "10-2021" in source or "10_2021" in source:
        payload["effective_from"] = TERMINAL_ACT10_FROM.isoformat()
        if not str(payload.get("amendment_act_name") or "").strip():
            payload["amendment_act_name"] = str(payload.get("act_name") or AMENDMENT_ACT_10_NAME)
        if not str(payload.get("base_act_name") or "").strip():
            payload["base_act_name"] = BASE_ACT_NAME
    elif "24-2017" in source:
        payload["effective_from"] = TERMINAL_2017_FROM.isoformat()
        payload["effective_to"] = TERMINAL_2017_THROUGH.isoformat()
        if not str(payload.get("base_act_name") or "").strip():
            payload["base_act_name"] = str(payload.get("act_name") or BASE_ACT_NAME)
    else:
        if not str(payload.get("effective_from") or "").strip():
            payload["effective_from"] = TERMINAL_2017_FROM.isoformat()
        if not str(payload.get("base_act_name") or "").strip():
            payload["base_act_name"] = str(payload.get("act_name") or BASE_ACT_NAME)
    return payload


def clip_period_to_year(
    *,
    ya_start: date,
    ya_end: date,
    effective_from: date,
    effective_to: date | None,
) -> tuple[date, date]:
    """Inclusive [period_from, period_to] clipped to the assessment year."""
    last_ya = ya_end - timedelta(days=1)
    start = max(ya_start, effective_from)
    stop = last_ya if effective_to is None else min(last_ya, effective_to)
    return start, stop


def qualifying_terminal_claim(
    *,
    amount: int,
    benefit_type: str | None,
    loss_of_office_scheme_approved: bool | None,
) -> bool:
    if amount <= 0:
        return False
    kind = (benefit_type or "").strip()
    if kind not in QUALIFYING_INCOME_TYPES:
        return False
    if kind == LOSS_OF_OFFICE_TYPE and not loss_of_office_scheme_approved:
        return False
    return True


def select_terminal_bands(
    bands: list[dict[str, Any]],
    *,
    assessment_year: str,
    over_20_years: bool | None,
    period: str | None,
) -> list[dict[str, Any]]:
    terminal = [row for row in bands if is_terminal_rate_group(str(row.get("compare_group_id") or ""))]
    if not terminal:
        return []
    if assessment_year == "2019_20":
        if period == PERIOD_FROM_2020:
            terminal = [
                row
                for row in terminal
                if str(row.get("period_from") or "") >= TERMINAL_ACT10_FROM.isoformat()
                or infer_employment_period_condition(row) == PERIOD_NA
            ]
            terminal = [row for row in terminal if infer_employment_period_condition(row) == PERIOD_NA]
        elif period == PERIOD_PRE_2020:
            want = PERIOD_OVER_20 if over_20_years else PERIOD_UPTO_20
            terminal = [
                row for row in terminal if infer_employment_period_condition(row) == want
            ]
        else:
            return []
    else:
        ya_start_year = int(assessment_year.split("_")[0])
        if ya_start_year >= 2020:
            terminal = [row for row in terminal if infer_employment_period_condition(row) == PERIOD_NA]
        else:
            want = PERIOD_OVER_20 if over_20_years else PERIOD_UPTO_20
            terminal = [row for row in terminal if infer_employment_period_condition(row) == want]
    return sorted(terminal, key=lambda row: int(row.get("band_index") or 0))


def group_terminal_ladders(bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in bands:
        if not is_terminal_rate_group(str(row.get("compare_group_id") or "")):
            continue
        stamped = stamp_terminal_rate_payload(dict(row))
        key = ladder_key(stamped)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(stamped)
    ladders: list[dict[str, Any]] = []
    for key in order:
        rows = sorted(buckets[key], key=lambda item: int(item.get("band_index") or 0))
        sample = rows[0]
        ladders.append(
            {
                "compare_group_id": TERMINAL_BENEFIT_GROUP,
                "rule_family": TERMINAL_BENEFIT_GROUP,
                "ladder_key": key,
                "employment_period_condition": infer_employment_period_condition(sample),
                "period_from": str(sample.get("period_from") or ""),
                "period_to": str(sample.get("period_to") or ""),
                "act_name": str(sample.get("act_name") or ""),
                "base_act_name": str(sample.get("base_act_name") or ""),
                "amendment_act_name": str(sample.get("amendment_act_name") or ""),
                "effective_from": str(sample.get("effective_from") or ""),
                "effective_to": str(sample.get("effective_to") or ""),
                "qualifying_income_types": sample.get("qualifying_income_types")
                or default_qualifying_types(),
                "source_doc_id": str(sample.get("source_doc_id") or ""),
                "section_ref": str(sample.get("section_ref") or ""),
                "entry_id": str(sample.get("entry_id") or ""),
                "quote": str(sample.get("quote") or ""),
                "bands": rows,
            }
        )
    return ladders
