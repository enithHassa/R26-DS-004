"""Tax from year views — caps and slabs, plus WHT credit → balance_payable.

Copied from Optimization and Explainable calculate.py (not imported). Rates come
from compiled First Schedule rows, never a hardcoded xlsx table.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from oe_engine_app.services import year_store
from oe_engine_app.services.terminal_benefit import (
    qualifying_terminal_claim,
    select_terminal_bands,
)

BINDER_AUTO_CAP = "auto_cap"
BINDER_MIN_CLAIM_CAP = "min(claim, cap)"
BINDER_PERCENT = "percent_of_base"
BINDER_NOTICE = "notice"

KNOWN_BINDING_KINDS = {
    "solar_panel_relief",
    "senior_citizen_interest_relief",
    "rent_relief",
    "qualifying_payments",
    "donations",
    "filing_line",
    "none",
}


def _as_money(raw: Any) -> float:
    """Non-negative LKR amount rounded to 2 decimal places (rupees and cents)."""
    if raw is None or raw == "":
        return 0.0
    try:
        return max(0.0, round(float(str(raw).replace(",", "").strip()), 2))
    except (TypeError, ValueError):
        return 0.0


def _cap(raw: Any) -> float | None:
    if raw is None or raw == "":
        return None
    return _as_money(raw)


def _binding_kind(entry: dict[str, Any]) -> str:
    binding = entry.get("engine_binding")
    if isinstance(binding, dict):
        kind = str(binding.get("kind") or "none").strip()
        return kind if kind else "none"
    return "none"


def binder_for(entry: dict[str, Any]) -> str:
    kind = _binding_kind(entry)
    unit = str(entry.get("unit") or "lkr")
    input_kind = str(entry.get("input_kind") or "notice")
    if kind not in KNOWN_BINDING_KINDS:
        kind = "none"
    if kind == "rent_relief" or unit == "percent":
        return BINDER_PERCENT
    if kind in {"solar_panel_relief", "qualifying_payments", "donations", "filing_line"}:
        return BINDER_MIN_CLAIM_CAP
    if kind == "senior_citizen_interest_relief":
        return BINDER_AUTO_CAP
    if input_kind == "notice":
        cap = _cap(entry.get("cap_amount"))
        return BINDER_AUTO_CAP if cap is not None else BINDER_NOTICE
    if input_kind in {"yes_no_amount", "amount"}:
        return BINDER_MIN_CLAIM_CAP
    if input_kind == "boolean":
        return BINDER_AUTO_CAP
    return BINDER_NOTICE


def _income_base(entry: dict[str, Any], income: dict[str, float]) -> float:
    kind = _binding_kind(entry)
    group = str(entry.get("compare_group_id") or "")
    unit = str(entry.get("unit") or "")
    if kind == "senior_citizen_interest_relief":
        return income["interest"]
    # Fifth Schedule rental relief is always % of rents — never gross assessable.
    if (
        kind == "rent_relief"
        or group in {"rental_income_relief", "rent_relief"}
        or unit == "percent"
    ):
        return income["rents"]
    if group == "employment_income_relief":
        return income["employment"]
    return income["gross"]


def _claim_map(claims: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for raw in claims:
        entry_id = str(raw.get("entry_id") or "").strip()
        if entry_id:
            out[entry_id] = raw
    return out


def _component_claims(claim: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Per-recipient amounts on an enumerated relief, ignoring malformed rows."""
    raw = claim.get("components") if claim else None
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        component_id = str(item.get("component_id") or "").strip()
        if component_id:
            out.append({"component_id": component_id, "amount": _as_money(item.get("amount"))})
    return out


def _claimed_amount(claim: dict[str, Any] | None, components: list[dict[str, Any]]) -> float:
    """A split claim is the sum of its parts; the flat amount is the fallback."""
    if components:
        return round(sum(float(c["amount"]) for c in components), 2)
    return _as_money(claim.get("amount")) if claim else 0.0


def _claim_active(entry: dict[str, Any], claim: dict[str, Any] | None) -> bool:
    input_kind = str(entry.get("input_kind") or "notice")
    if input_kind == "notice":
        return True
    if claim is None:
        return False
    if bool(claim.get("skipped")):
        return False
    if input_kind in {"yes_no_amount", "boolean"}:
        return bool(claim.get("affirmed"))
    return True


def _apply_one(
    entry: dict[str, Any],
    income: dict[str, float],
    claim: dict[str, Any] | None,
) -> dict[str, Any]:
    binder = binder_for(entry)
    cap = _cap(entry.get("cap_amount"))
    base = _income_base(entry, income)
    components = _component_claims(claim)
    claim_amt = _claimed_amount(claim, components)
    active = _claim_active(entry, claim)
    applied = 0.0
    formula = binder

    if binder == BINDER_NOTICE:
        applied = 0.0
        formula = "notice — no rupee amount"
    elif not active:
        applied = 0.0
        formula = f"{binder} (not claimed)"
    elif binder == BINDER_PERCENT:
        pct = cap or 0
        applied = round(base * pct / 100.0, 2)
        formula = f"{pct}% of {base}"
    elif binder == BINDER_AUTO_CAP:
        applied = min(cap, base) if cap is not None else 0.0
        formula = f"min(cap {cap or 0}, base {base})"
    elif binder == BINDER_MIN_CLAIM_CAP:
        if cap is None:
            applied = claim_amt
            formula = f"claim {claim_amt} (no cap)"
        else:
            applied = min(claim_amt, cap)
            formula = f"min(claim {claim_amt}, cap {cap})"
    if active and components:
        parts = " + ".join(str(c["amount"]) for c in components)
        formula = f"{formula}; claim = {parts}"

    return {
        "entry_id": entry.get("entry_id"),
        "compare_group_id": entry.get("compare_group_id"),
        "display_name": entry.get("display_name"),
        "binder": binder,
        "engine_binding_kind": _binding_kind(entry),
        "cap": cap,
        "base": base,
        "claim": claim_amt if claim else 0,
        "applied": round(applied, 2),
        "formula": formula,
        "components": components,
        "sub_items": entry.get("sub_items") or [],
        "quote": entry.get("quote") or "",
        "source_doc_id": entry.get("source_doc_id") or "",
        "act_name": entry.get("act_name") or "",
        "section_ref": entry.get("section_ref") or "",
        "unit": entry.get("unit") or "lkr",
    }


def tax_from_slabs(taxable: float, bands: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]]]:
    lines: list[dict[str, Any]] = []
    total = 0.0
    ordered = sorted(bands, key=lambda b: int(b.get("band_index") or 0))
    for band in ordered:
        lower = _as_money(band.get("lower"))
        upper_raw = band.get("upper")
        upper = None if upper_raw is None or upper_raw == "" else _as_money(upper_raw)
        rate = float(band.get("rate_percent") or 0)
        if taxable <= lower:
            slice_amt = 0.0
        elif upper is None:
            slice_amt = max(0.0, taxable - lower)
        else:
            slice_amt = max(0.0, min(taxable, upper) - lower)
        tax = round(slice_amt * rate / 100.0, 2)
        total = round(total + tax, 2)
        lines.append(
            {
                "band_index": band.get("band_index"),
                "lower": lower,
                "upper": upper,
                "rate_percent": rate,
                "slice": round(slice_amt, 2),
                "tax": tax,
                "band_label": band.get("band_label") or "",
                "quote": band.get("quote") or "",
                "source_doc_id": band.get("source_doc_id") or "",
                "act_name": band.get("act_name") or "",
                "section_ref": band.get("section_ref") or "",
            }
        )
    return total, lines


def _legacy_terminal_items(income: dict[str, Any]) -> list[dict[str, Any]]:
    amount = _as_money(income.get("terminal_benefit_amount"))
    kind = income.get("terminal_benefit_type")
    if amount <= 0 and not str(kind or "").strip():
        return []
    return [
        {
            "type": kind,
            "amount": amount,
            "employment_period_over_20_years": income.get("employment_period_over_20_years"),
            "loss_of_office_scheme_approved": income.get("loss_of_office_scheme_approved"),
            "terminal_benefit_period": income.get("terminal_benefit_period"),
        }
    ]


def _terminal_items(income: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    raw = income.get("terminal_benefits")
    if isinstance(raw, list) and raw:
        return raw, False
    return _legacy_terminal_items(income), True


def _terminal_ladder_group_key(assessment_year: str, item: dict[str, Any]) -> str | None:
    """Bucket that shares one progressive terminal ladder. None = skip (e.g. missing 2019/20 period)."""
    period = str(item.get("terminal_benefit_period") or "").strip()
    over_20 = bool(item.get("employment_period_over_20_years"))
    if assessment_year == "2019_20":
        if period == "from_2020_01_01":
            return "from_2020_01_01"
        if period == "pre_2020":
            return f"pre_2020|{'over_20_years' if over_20 else 'upto_20_years'}"
        return None
    ya_start_year = int(assessment_year.split("_")[0])
    if ya_start_year >= 2020:
        return "not_applicable"
    return "over_20_years" if over_20 else "upto_20_years"


def calculate(
    session: Session,
    assessment_year: str,
    income: dict[str, Any],
    claims: list[dict[str, Any]] | None = None,
    exclude_source_doc_id: str | None = None,
    wht_already_paid: float = 0,
    apit_already_paid: float = 0,
) -> dict[str, Any]:
    reliefs = year_store.reliefs_for_year(session, assessment_year, exclude_source_doc_id)
    rates = year_store.rates_for_year(session, assessment_year, exclude_source_doc_id)
    if reliefs is None or rates is None:
        raise KeyError(assessment_year)
    ordinary_rates, terminal_rates = year_store.split_year_rates(rates)
    if not ordinary_rates:
        raise ValueError("no_rate_bands")

    raw_employment = _as_money(income.get("employment"))
    terminal_items, subtract_legacy = _terminal_items(income)
    employment = raw_employment
    if subtract_legacy and terminal_items:
        legacy = terminal_items[0]
        legacy_amount = _as_money(legacy.get("amount"))
        if qualifying_terminal_claim(
            amount=legacy_amount,
            benefit_type=legacy.get("type"),
            loss_of_office_scheme_approved=legacy.get("loss_of_office_scheme_approved"),
        ) and raw_employment >= legacy_amount:
            employment = round(raw_employment - legacy_amount, 2)
    business = _as_money(income.get("business"))
    investment = _as_money(income.get("investment"))
    other = _as_money(income.get("other"))
    ordinary_gross = round(employment + business + investment + other, 2)
    qualifying_amount = 0.0
    for item in terminal_items:
        amount = _as_money(item.get("amount"))
        if qualifying_terminal_claim(
            amount=amount,
            benefit_type=item.get("type"),
            loss_of_office_scheme_approved=item.get("loss_of_office_scheme_approved"),
        ):
            qualifying_amount = round(qualifying_amount + amount, 2)
    gross = round(ordinary_gross + qualifying_amount, 2)
    packed = {
        "employment": employment,
        "business": business,
        "investment": investment,
        "other": other,
        "interest": _as_money(income.get("interest")),
        "rents": _as_money(income.get("rents")),
        "gross": ordinary_gross,
    }

    by_id = _claim_map(claims or [])
    remaining = ordinary_gross
    relief_lines: list[dict[str, Any]] = []
    ordered = sorted(
        reliefs,
        key=lambda e: (int(e.get("sort_order") or 0), str(e.get("entry_id") or "")),
    )
    for entry in ordered:
        line = _apply_one(entry, packed, by_id.get(str(entry.get("entry_id") or "")))
        applied = min(float(line["applied"]), remaining)
        line["applied"] = round(applied, 2)
        remaining = round(remaining - applied, 2)
        relief_lines.append(line)

    taxable = remaining
    tax_payable, slab_lines = tax_from_slabs(taxable, ordinary_rates)
    terminal_tax = 0.0
    terminal_slab_lines: list[dict[str, Any]] = []
    terminal_benefit_lines: list[dict[str, Any]] = []
    grouped: dict[str, list[tuple[dict[str, Any], float]]] = {}
    group_order: list[str] = []
    prepared: list[tuple[str, dict[str, Any], float]] = []
    for item in terminal_items:
        amount = _as_money(item.get("amount"))
        if not qualifying_terminal_claim(
            amount=amount,
            benefit_type=item.get("type"),
            loss_of_office_scheme_approved=item.get("loss_of_office_scheme_approved"),
        ):
            continue
        key = _terminal_ladder_group_key(assessment_year, item)
        if key is None:
            continue
        prepared.append((key, item, amount))
        if key not in grouped:
            grouped[key] = []
            group_order.append(key)
        grouped[key].append((item, amount))
    taxed_groups: set[str] = set()
    for key in group_order:
        members = grouped[key]
        sample, _ = members[0]
        chosen = select_terminal_bands(
            terminal_rates,
            assessment_year=assessment_year,
            over_20_years=sample.get("employment_period_over_20_years"),
            period=sample.get("terminal_benefit_period"),
        )
        if not chosen:
            continue
        group_total = round(sum(amount for _, amount in members), 2)
        group_tax, group_slabs = tax_from_slabs(group_total, chosen)
        terminal_tax = round(terminal_tax + group_tax, 2)
        terminal_slab_lines.extend(group_slabs)
        taxed_groups.add(key)
    for key, item, amount in prepared:
        if key not in taxed_groups:
            continue
        terminal_benefit_lines.append(
            {
                "type": item.get("type"),
                "amount": amount,
                "tax": None,
                "slab_lines": [],
            }
        )
    tax_payable = round(tax_payable + terminal_tax, 2)
    # Prepaid credits against tax payable (not reductions of employment income):
    # APIT = Advance Personal Income Tax deducted from salary; WHT = interest WHT.
    claimed_apit = _as_money(
        apit_already_paid if apit_already_paid else income.get("apit_already_paid")
    )
    claimed_wht = _as_money(wht_already_paid if wht_already_paid else income.get("wht_already_paid"))
    apit_credit = min(claimed_apit, tax_payable)
    remaining_after_apit = round(tax_payable - apit_credit, 2)
    wht_credit = min(claimed_wht, remaining_after_apit)
    balance_payable = round(tax_payable - apit_credit - wht_credit, 2)
    tax_refund = max(0.0, round(claimed_apit + claimed_wht - tax_payable, 2))
    return {
        "assessment_year": assessment_year,
        "gross_income": gross,
        "employment_income": employment,
        "business_income": business,
        "investment_income": investment,
        "other_income": other,
        "total_reliefs": round(ordinary_gross - taxable, 2),
        "taxable_income": taxable,
        "tax_payable": tax_payable,
        "terminal_benefit_amount": qualifying_amount,
        "terminal_benefit_tax": terminal_tax,
        "terminal_benefit_lines": terminal_benefit_lines,
        "apit_already_paid": claimed_apit,
        "apit_credit": apit_credit,
        "wht_already_paid": claimed_wht,
        "wht_credit": wht_credit,
        "balance_payable": balance_payable,
        "tax_refund": tax_refund,
        "exclude_source_doc_id": exclude_source_doc_id or None,
        "relief_lines": relief_lines,
        "slab_lines": slab_lines,
        "terminal_benefit_slab_lines": terminal_slab_lines,
    }
