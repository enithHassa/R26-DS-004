"""Tax from year views — caps and slabs, plus WHT credit → balance_payable.

Copied from Optimization and Explainable calculate.py (not imported). Rates come
from compiled First Schedule rows, never a hardcoded xlsx table.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from oe_engine_app.services import year_store

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


def _as_int(raw: Any) -> int:
    if raw is None or raw == "":
        return 0
    try:
        return max(0, int(round(float(str(raw).replace(",", "").strip()))))
    except (TypeError, ValueError):
        return 0


def _cap(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    return _as_int(raw)


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


def _income_base(entry: dict[str, Any], income: dict[str, int]) -> int:
    kind = _binding_kind(entry)
    group = str(entry.get("compare_group_id") or "")
    if kind == "senior_citizen_interest_relief":
        return income["interest"]
    if kind == "rent_relief" or str(entry.get("unit") or "") == "percent":
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
            out.append({"component_id": component_id, "amount": _as_int(item.get("amount"))})
    return out


def _claimed_amount(claim: dict[str, Any] | None, components: list[dict[str, Any]]) -> int:
    """A split claim is the sum of its parts; the flat amount is the fallback."""
    if components:
        return sum(int(c["amount"]) for c in components)
    return _as_int(claim.get("amount")) if claim else 0


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
    income: dict[str, int],
    claim: dict[str, Any] | None,
) -> dict[str, Any]:
    binder = binder_for(entry)
    cap = _cap(entry.get("cap_amount"))
    base = _income_base(entry, income)
    components = _component_claims(claim)
    claim_amt = _claimed_amount(claim, components)
    active = _claim_active(entry, claim)
    applied = 0
    formula = binder

    if binder == BINDER_NOTICE:
        applied = 0
        formula = "notice — no rupee amount"
    elif not active:
        applied = 0
        formula = f"{binder} (not claimed)"
    elif binder == BINDER_PERCENT:
        pct = cap or 0
        applied = int(base * pct // 100)
        formula = f"{pct}% of {base}"
    elif binder == BINDER_AUTO_CAP:
        applied = min(cap, base) if cap is not None else 0
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
        "applied": applied,
        "formula": formula,
        "components": components,
        "sub_items": entry.get("sub_items") or [],
        "quote": entry.get("quote") or "",
        "source_doc_id": entry.get("source_doc_id") or "",
        "act_name": entry.get("act_name") or "",
        "section_ref": entry.get("section_ref") or "",
        "unit": entry.get("unit") or "lkr",
    }


def tax_from_slabs(taxable: int, bands: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    lines: list[dict[str, Any]] = []
    total = 0
    ordered = sorted(bands, key=lambda b: int(b.get("band_index") or 0))
    for band in ordered:
        lower = _as_int(band.get("lower"))
        upper_raw = band.get("upper")
        upper = None if upper_raw is None or upper_raw == "" else _as_int(upper_raw)
        rate = float(band.get("rate_percent") or 0)
        if taxable <= lower:
            slice_amt = 0
        elif upper is None:
            slice_amt = max(0, taxable - lower)
        else:
            slice_amt = max(0, min(taxable, upper) - lower)
        tax = int(round(slice_amt * rate / 100.0))
        total += tax
        lines.append(
            {
                "band_index": band.get("band_index"),
                "lower": lower,
                "upper": upper,
                "rate_percent": rate,
                "slice": slice_amt,
                "tax": tax,
                "band_label": band.get("band_label") or "",
                "quote": band.get("quote") or "",
                "source_doc_id": band.get("source_doc_id") or "",
                "act_name": band.get("act_name") or "",
                "section_ref": band.get("section_ref") or "",
            }
        )
    return total, lines


def calculate(
    session: Session,
    assessment_year: str,
    income: dict[str, Any],
    claims: list[dict[str, Any]] | None = None,
    exclude_source_doc_id: str | None = None,
    wht_already_paid: int = 0,
) -> dict[str, Any]:
    reliefs = year_store.reliefs_for_year(session, assessment_year, exclude_source_doc_id)
    rates = year_store.rates_for_year(session, assessment_year, exclude_source_doc_id)
    if reliefs is None or rates is None:
        raise KeyError(assessment_year)
    if not rates:
        raise ValueError("no_rate_bands")

    employment = _as_int(income.get("employment"))
    business = _as_int(income.get("business"))
    investment = _as_int(income.get("investment"))
    other = _as_int(income.get("other"))
    gross = employment + business + investment + other
    packed = {
        "employment": employment,
        "business": business,
        "investment": investment,
        "other": other,
        "interest": _as_int(income.get("interest")),
        "rents": _as_int(income.get("rents")),
        "gross": gross,
    }

    by_id = _claim_map(claims or [])
    remaining = gross
    relief_lines: list[dict[str, Any]] = []
    ordered = sorted(
        reliefs,
        key=lambda e: (int(e.get("sort_order") or 0), str(e.get("entry_id") or "")),
    )
    for entry in ordered:
        line = _apply_one(entry, packed, by_id.get(str(entry.get("entry_id") or "")))
        applied = min(int(line["applied"]), remaining)
        line["applied"] = applied
        remaining -= applied
        relief_lines.append(line)

    taxable = remaining
    tax_payable, slab_lines = tax_from_slabs(taxable, rates)
    claimed_wht = _as_int(wht_already_paid if wht_already_paid else income.get("wht_already_paid"))
    credits_applied = min(claimed_wht, tax_payable)
    balance_payable = tax_payable - credits_applied
    tax_refund = max(0, claimed_wht - tax_payable)
    return {
        "assessment_year": assessment_year,
        "gross_income": gross,
        "employment_income": employment,
        "business_income": business,
        "investment_income": investment,
        "other_income": other,
        "total_reliefs": gross - taxable,
        "taxable_income": taxable,
        "tax_payable": tax_payable,
        "wht_already_paid": claimed_wht,
        "wht_credit": credits_applied,
        "balance_payable": balance_payable,
        "tax_refund": tax_refund,
        "exclude_source_doc_id": exclude_source_doc_id or None,
        "relief_lines": relief_lines,
        "slab_lines": slab_lines,
    }
