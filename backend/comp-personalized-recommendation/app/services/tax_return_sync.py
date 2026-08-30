"""Map TaxWise tax-return wizard JSON onto flat ``financial_profiles`` scalars.

The 8-section wizard stores rich detail in ``tax_return_detail``; this module
derives the aggregate columns the recommendation ranker already understands.

Scalars the auditor sets for recommendations (expenses, debt, risk, income mix,
etc.) are **not** overwritten from the tax-return wizard — only Bucket A fields
that belong on the return itself are synced here.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

# Auditor / intake fields — preserved when taxpayer saves Tax Return Profile.
RECOMMENDATION_ONLY_SCALAR_KEYS = frozenset(
    {
        "monthly_expenses",
        "monthly_debt_service",
        "total_debt",
        "liquid_savings",
        "existing_investments",
        "vehicle_value",
        "property_value",
        "occupation",
        "employment_type",
        "employer_sector",
        "years_employed",
        "risk_tolerance",
        "investment_horizon_years",
        "retirement_age_target",
        "income_sources",
    }
)


def _dec(value: object, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    try:
        return Decimal(str(value).replace(",", ""))
    except Exception:
        return Decimal(default)


def _sum_employer_field(employers: list[dict[str, Any]], key: str) -> Decimal:
    return sum((_dec(e.get(key)) for e in employers), Decimal("0"))


def _ya_to_tax_year(ya: str) -> str:
    """``2024-2025`` / ``2024/25`` → ``2024_25`` for the profile ``tax_year`` column."""
    cleaned = ya.strip().replace(" ", "")
    if "_" in cleaned and len(cleaned) == 7:
        return cleaned
    if "/" in cleaned:
        start, end = cleaned.split("/", 1)
        if start.isdigit() and len(start) == 4 and end:
            return f"{start}_{end[-2:]}"
    if "-" in cleaned:
        start, end = cleaned.split("-", 1)
        if start.isdigit() and len(start) == 4 and end:
            return f"{start}_{end[-2:]}"
    if cleaned.isdigit() and len(cleaned) == 4:
        start = int(cleaned)
        return f"{cleaned}_{str(start + 1)[-2:]}"
    return "2026_27"


def _marital_from_detail(value: str) -> str:
    mapping = {
        "single": "single",
        "married": "married",
        "divorced": "divorced",
        "widowed": "widowed",
    }
    return mapping.get(value, "single")


def _residency_from_detail(value: str) -> str:
    mapping = {
        "resident": "resident",
        "non-resident": "non_resident",
        "dual": "dual",
        "deemed": "dual",
    }
    return mapping.get(value, "resident")


def _nationality_from_detail(value: str) -> str:
    mapping = {
        "lk": "Sri Lankan",
        "dual": "Dual Citizen",
        "foreign": "Foreign",
    }
    return mapping.get(value, value)


def _sum_charitable(s6: dict[str, Any]) -> Decimal:
    return sum(
        (
            _dec(s6.get("charitablePresident")),
            _dec(s6.get("charitableApproved")),
            _dec(s6.get("charitableReligious")),
            _dec(s6.get("charitableOther")),
        ),
        Decimal("0"),
    )


def sync_scalars_from_tax_return(detail: dict[str, Any]) -> dict[str, Any]:
    """Return ORM column updates derived from ``tax_return_detail`` (Bucket A only)."""
    if not detail:
        return {}

    out: dict[str, Any] = {}
    s1 = detail.get("section1") or {}
    s2 = detail.get("section2") or {}
    s6 = detail.get("section6") or {}

    if s1.get("fullName"):
        out["full_name"] = str(s1["fullName"])[:200]
    if s1.get("dob"):
        out["date_of_birth"] = s1["dob"]
    if s1.get("gender"):
        out["gender"] = s1["gender"]
    if s1.get("district"):
        out["district"] = s1["district"]
    if s1.get("marital"):
        out["marital_status"] = _marital_from_detail(str(s1["marital"]))
    if s1.get("residency"):
        out["residency_status"] = _residency_from_detail(str(s1["residency"]))
    if s1.get("nationality"):
        out["nationality"] = _nationality_from_detail(str(s1["nationality"]))
    if s1.get("dependants") not in (None, ""):
        out["dependents"] = int(_dec(s1["dependants"]))
    if s1.get("taxYear"):
        out["tax_year"] = _ya_to_tax_year(str(s1["taxYear"]))

    employers = list(s2.get("employers") or [])
    if employers:
        gross_annual = _sum_employer_field(employers, "gross")
        bonus_annual = _sum_employer_field(employers, "bonus")
        epf_annual = _sum_employer_field(employers, "epf")
        etf_annual = _sum_employer_field(employers, "etf")
        if gross_annual > 0:
            out["gross_monthly_income"] = (gross_annual / Decimal("12")).quantize(Decimal("0.01"))
        if bonus_annual > 0:
            out["annual_bonus_lkr"] = bonus_annual
        if epf_annual > 0:
            out["epf_balance"] = epf_annual
        if etf_annual > 0:
            out["etf_balance"] = etf_annual

    # Section 6 — flat keys (matches frontend ``types.ts``).
    if s6.get("lifePremium"):
        out["life_insurance_premium_annual"] = _dec(s6["lifePremium"])
    if s6.get("hasMedical") or _dec(s6.get("medicalPremium")) > 0:
        out["health_insurance"] = True
    if s6.get("mortgageInterest"):
        out["home_loan_interest_annual"] = _dec(s6["mortgageInterest"])
    donations = _sum_charitable(s6)
    if donations > 0:
        out["donations_annual"] = donations

    return {k: v for k, v in out.items() if k not in RECOMMENDATION_ONLY_SCALAR_KEYS}
