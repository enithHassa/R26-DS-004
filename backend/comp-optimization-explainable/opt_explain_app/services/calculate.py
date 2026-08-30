"""Tax from the year-indexed RAG store — caps and slabs, no hardcoded tables."""

from __future__ import annotations

from typing import Any

from opt_explain_app.services import rag_index

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
    n = _as_int(raw)
    return n


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
    claim_amt = _as_int(claim.get("amount")) if claim else 0
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
        "quote": entry.get("quote") or "",
        "source_doc_id": entry.get("source_doc_id") or "",
        "act_name": entry.get("act_name") or "",
        "section_ref": entry.get("section_ref") or "",
        "unit": entry.get("unit") or "lkr",
    }


def tax_from_slabs(taxable: int, bands: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]]]:
    """Progressive tax from RAG rate docs. Band edges come from the index."""
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
    assessment_year: str,
    income: dict[str, Any],
    claims: list[dict[str, Any]] | None = None,
    exclude_source_doc_id: str | None = None,
) -> dict[str, Any]:
    reliefs = rag_index.reliefs_for_year(assessment_year, exclude_source_doc_id)
    rates = rag_index.rates_for_year(assessment_year, exclude_source_doc_id)
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
        "exclude_source_doc_id": exclude_source_doc_id or None,
        "relief_lines": relief_lines,
        "slab_lines": slab_lines,
    }
