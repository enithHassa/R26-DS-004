"""Phase 8 catalog rate engine — tax from ``rates/{ya}.json`` only.

Additive module. Does **not** import or patch ``rule_engine.calculate`` /
its YA enum. ``POST /calculate`` remains the verified authority for
``2024_25`` / ``2025_26``; this module may also emit an additional
extracted-catalog estimate for those years (interview Result dual card).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from backend.shared.config.settings import PROJECT_ROOT

RATES_DIR = PROJECT_ROOT / "models" / "adaptive-tax" / "relief-interview" / "rates"
APPROVED_DIR = PROJECT_ROOT / "models" / "adaptive-tax" / "relief-interview" / "approved"
ACCURACY_RESULT = (
    PROJECT_ROOT
    / "models"
    / "adaptive-tax"
    / "relief-interview"
    / "extracted"
    / "accuracy_result.json"
)

ENGINE_AUTHORITY_YAS = frozenset({"2024_25", "2025_26"})
CATALOG_YAS = (
    "2018_19",
    "2019_20",
    "2020_21",
    "2021_22",
    "2022_23",
    "2023_24",
    "2024_25",
    "2025_26",
)

_DEDICATED_CLAIM_GROUPS = frozenset(
    {
        "personal_relief",
        "solar_panel_relief",
        "rental_income_relief",
        "senior_citizen_interest_relief",
    }
)
_EXTRA_CLAIM_KINDS = frozenset(
    {"qualifying_payments", "donations", "filing_line"}
)

MONEY_QUANT = Decimal("0.01")


class CatalogEngineError(ValueError):
    """Input / catalog problems that should surface as HTTP 4xx."""


class CatalogEngineGateError(RuntimeError):
    """Phase 4 accuracy gate not cleared — refuse to invent older-year tax."""


def _q(value: Decimal | int | str | float | None) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> str:
    return format(_q(value), "f")


def accuracy_gate_passed() -> bool:
    if not ACCURACY_RESULT.is_file():
        return False
    try:
        data = json.loads(ACCURACY_RESULT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return bool(data.get("gate_pass"))


def load_rates(ya: str) -> dict[str, Any]:
    path = RATES_DIR / f"{ya}.json"
    if not path.is_file():
        raise CatalogEngineError(f"rates/{ya}.json missing")
    return json.loads(path.read_text(encoding="utf-8"))


def load_approved(ya: str) -> dict[str, Any]:
    path = APPROVED_DIR / f"{ya}.json"
    if not path.is_file():
        raise CatalogEngineError(f"approved/{ya}.json missing")
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_bands(raw_bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map extractor ladder bounds onto ontology-style exclusive lowers.

    Extracted tables often share a boundary (500000 then 500000). The live
    engine's ontology packs use 500000 then 500001. Normalize so slab widths
    match the accuracy-gated ladder intent.
    """
    ordered = sorted(
        raw_bands,
        key=lambda b: (int(b.get("band_index") or 0), int(b.get("lower") or 0)),
    )
    out: list[dict[str, Any]] = []
    prev_upper: int | None = None
    for band in ordered:
        lower = int(band.get("lower") or 0)
        upper = band.get("upper")
        upper_i = int(upper) if upper is not None else None
        if prev_upper is not None and lower == prev_upper:
            lower = prev_upper + 1
        rate_percent = Decimal(str(band.get("rate_percent") or 0))
        # Catalog stores 6.0 for 6%; tolerate accidental fractional form.
        rate = rate_percent / Decimal("100") if rate_percent > 1 else rate_percent
        out.append(
            {
                **band,
                "lower_norm": lower,
                "upper_norm": upper_i,
                "rate": rate,
            }
        )
        prev_upper = upper_i
    return out


def _band_width(lower: int, upper: int | None) -> Decimal | None:
    if upper is None:
        return None
    return Decimal(upper - max(lower - 1, 0))


@dataclass(frozen=True)
class CatalogClaim:
    compare_group_id: str
    amount: Decimal = Decimal("0")


@dataclass
class CatalogCalculateInput:
    assessment_year: str
    employment_income: Decimal = Decimal("0")
    business_income: Decimal = Decimal("0")
    investment_income: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")
    solar_panel_relief: Decimal = Decimal("0")
    rent_relief: Decimal = Decimal("0")
    senior_citizen_interest_relief: Decimal = Decimal("0")
    claims: tuple[CatalogClaim, ...] = ()


def _claims_amount(claims: tuple[CatalogClaim, ...], group_id: str) -> Decimal:
    total = Decimal("0")
    for claim in claims:
        if claim.compare_group_id == group_id:
            total += _q(claim.amount)
    return total


def _capped_claim(
    entry: dict[str, Any], claim_amount: Decimal, remaining: Decimal
) -> Decimal:
    if claim_amount <= 0 or remaining <= 0:
        return Decimal("0")
    unit = str(entry.get("unit") or "lkr").lower()
    cap_raw = entry.get("cap_amount")
    if unit == "lkr" and cap_raw not in (None, ""):
        cap = _q(cap_raw)
        if cap > 0:
            return min(claim_amount, cap, remaining)
    return min(claim_amount, remaining)


def calculate_from_catalog(inp: CatalogCalculateInput) -> dict[str, Any]:
    """Compute tax from approved + rates catalogs (all interview YAs)."""
    ya = inp.assessment_year
    if ya not in CATALOG_YAS:
        raise CatalogEngineError(f"Unsupported catalog assessment_year {ya!r}")
    if not accuracy_gate_passed():
        raise CatalogEngineGateError(
            "Phase 4 accuracy gate has not passed — refusing catalog tax figures"
        )

    rates = load_rates(ya)
    approved = load_approved(ya)
    bands_raw = rates.get("bands") or []
    if not bands_raw:
        raise CatalogEngineError(f"rates/{ya}.json has no bands")

    bands = _normalize_bands(list(bands_raw))
    rates_need_manual = bool(rates.get("needs_manual_verification", True))

    gross = _q(
        inp.employment_income
        + inp.business_income
        + inp.investment_income
        + inp.other_income
    )

    entries = {
        e.get("compare_group_id"): e
        for e in (approved.get("entries") or [])
        if e.get("compare_group_id")
    }

    reliefs_applied: list[dict[str, Any]] = []
    running = gross

    personal = entries.get("personal_relief")
    personal_cap = _q(personal.get("cap_amount") if personal else 0)
    personal_applied = min(personal_cap, running) if personal and personal_cap > 0 else Decimal("0")
    if personal_applied > 0 and personal:
        running = _q(running - personal_applied)
        reliefs_applied.append(_relief_receipt(personal, personal_applied, "personal_relief"))

    solar_entry = entries.get("solar_panel_relief")
    solar_cap = _q(solar_entry.get("cap_amount") if solar_entry else 0)
    solar_claim = _q(inp.solar_panel_relief)
    if solar_claim <= 0:
        solar_claim = _claims_amount(inp.claims, "solar_panel_relief")
    solar_applied = min(solar_claim, solar_cap, running) if solar_claim > 0 else Decimal("0")
    if solar_applied > 0 and solar_entry:
        running = _q(running - solar_applied)
        reliefs_applied.append(_relief_receipt(solar_entry, solar_applied, "solar_panel_relief"))

    rent_applied_amount = Decimal("0")
    rent_entry = entries.get("rental_income_relief")
    # Rent in catalog is often a percent of rental income; claim is absolute LKR from UI.
    rent_claim = _q(inp.rent_relief)
    if rent_claim <= 0:
        rent_claim = _claims_amount(inp.claims, "rental_income_relief")
    if rent_claim > 0 and rent_entry:
        unit = (rent_entry.get("unit") or "lkr").lower()
        if unit == "percent":
            # Cap as percent of investment/rental income head when known.
            pct = _q(rent_entry.get("cap_amount") or 0)
            rent_cap = _q(inp.investment_income * pct / Decimal("100"))
        else:
            rent_cap = _q(rent_entry.get("cap_amount") or 0)
        rent_applied_amount = min(rent_claim, rent_cap, running)
        if rent_applied_amount > 0:
            running = _q(running - rent_applied_amount)
            reliefs_applied.append(
                _relief_receipt(rent_entry, rent_applied_amount, "rental_income_relief")
            )

    senior_applied = Decimal("0")
    senior_entry = entries.get("senior_citizen_interest_relief")
    senior_claim = _q(inp.senior_citizen_interest_relief)
    if senior_claim <= 0:
        senior_claim = _claims_amount(inp.claims, "senior_citizen_interest_relief")
    if senior_claim > 0 and senior_entry:
        senior_cap = _q(senior_entry.get("cap_amount") or 1_500_000)
        # Claim is already capped to interest in the interview; still enforce statutory LKR cap.
        senior_applied = min(senior_claim, senior_cap, running)
        if senior_applied > 0:
            running = _q(running - senior_applied)
            reliefs_applied.append(
                _relief_receipt(
                    senior_entry, senior_applied, "senior_citizen_interest_relief"
                )
            )

    applied_groups = {r["compare_group_id"] for r in reliefs_applied}
    for claim in inp.claims:
        group = claim.compare_group_id
        if not group or group in _DEDICATED_CLAIM_GROUPS or group in applied_groups:
            continue
        entry = entries.get(group)
        if not entry:
            continue
        binding = entry.get("engine_binding") or {}
        kind = binding.get("kind") if isinstance(binding, dict) else None
        if kind not in _EXTRA_CLAIM_KINDS:
            continue
        applied_amt = _capped_claim(entry, _q(claim.amount), running)
        if applied_amt <= 0:
            continue
        running = _q(running - applied_amt)
        reliefs_applied.append(_relief_receipt(entry, applied_amt, group))
        applied_groups.add(group)

    taxable = _q(max(Decimal("0"), running))
    total_tax, band_slices = _allocate_catalog_slabs(taxable, bands)

    claims_need_manual = any(
        bool(r.get("needs_manual_verification")) for r in reliefs_applied
    )
    needs_manual = rates_need_manual or claims_need_manual
    verification_badge = {
        "show": needs_manual,
        "label": (
            "extracted from source, not independently verified"
            if needs_manual
            else "catalog rates spot-checked"
        ),
        "needs_manual_verification": needs_manual,
        "cleared": not needs_manual,
    }

    # Expandable receipts: every band slice + reliefs used.
    receipts = [
        *[
            {
                "kind": "relief",
                "label": r["display_name"],
                "amount_lkr": r["amount_lkr"],
                "act_name": r["act_name"],
                "section_ref": r["section_ref"],
                "quote": r["quote"],
                "source_doc_id": r["source_doc_id"],
            }
            for r in reliefs_applied
        ],
        *[
            {
                "kind": "rate_band",
                "label": s["band_label"],
                "amount_lkr": s["tax_slice_lkr"],
                "act_name": s["act_name"],
                "section_ref": s["section_ref"],
                "quote": s["quote"],
                "source_doc_id": s["source_doc_id"],
            }
            for s in band_slices
        ],
    ]

    return {
        "spec_version": "1.0.0",
        "engine": "catalog_rates_v1",
        "assessment_year": ya,
        "currency": rates.get("currency") or "LKR",
        "needs_manual_verification": needs_manual,
        "verification_badge": verification_badge,
        "gross_income_lkr": _money(gross),
        "personal_relief_lkr": _money(personal_applied),
        "solar_panel_relief_lkr": _money(solar_applied),
        "rent_relief_lkr": _money(rent_applied_amount),
        "senior_citizen_interest_relief_lkr": _money(senior_applied),
        "taxable_income_lkr": _money(taxable),
        "final_tax_lkr": _money(total_tax),
        "tax_payable_lkr": _money(total_tax),
        "reliefs_applied": reliefs_applied,
        "band_slices": band_slices,
        "receipts": receipts,
        "rates_provenance": rates.get("provenance") or {},
        "notes": (
            "Phase 8 catalog engine. Progressive slabs read from rates/{ya}.json. "
            "For 2024/25 and 2025/26 this is an additional extracted estimate — "
            "POST /calculate remains the verified figure."
        ),
    }


def _relief_receipt(entry: dict[str, Any], amount: Decimal, group: str) -> dict[str, Any]:
    return {
        "compare_group_id": group,
        "display_name": entry.get("display_name") or group,
        "amount_lkr": _money(amount),
        "cap_amount": entry.get("cap_amount"),
        "act_name": entry.get("act_name") or "",
        "section_ref": entry.get("section_ref") or "",
        "quote": entry.get("quote") or "",
        "source_doc_id": entry.get("source_doc_id") or "",
        "needs_manual_verification": bool(entry.get("needs_manual_verification")),
    }


def _allocate_catalog_slabs(
    taxable: Decimal, bands: list[dict[str, Any]]
) -> tuple[Decimal, list[dict[str, Any]]]:
    remaining = _q(taxable)
    total = Decimal("0")
    slices: list[dict[str, Any]] = []
    if remaining <= 0:
        return Decimal("0"), slices

    for band in bands:
        if remaining <= 0:
            break
        lower = int(band["lower_norm"])
        upper = band["upper_norm"]
        width = _band_width(lower, upper)
        chunk = remaining if width is None else min(remaining, width)
        rate = Decimal(str(band["rate"]))
        tax_slice = _q(chunk * rate)
        total += tax_slice
        remaining = _q(remaining - chunk)
        slices.append(
            {
                "band_index": band.get("band_index"),
                "band_label": band.get("band_label") or "",
                "lower": lower,
                "upper": upper,
                "rate_percent": float(Decimal(str(band.get("rate_percent") or 0))),
                "taxable_in_slice_lkr": _money(chunk),
                "tax_slice_lkr": _money(tax_slice),
                "act_name": band.get("act_name") or "",
                "section_ref": band.get("section_ref") or "",
                "quote": band.get("quote") or "",
                "source_doc_id": band.get("source_doc_id") or "",
            }
        )
        if width is None:
            break
    return _q(total), slices
