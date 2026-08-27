"""Map TaxWise tax-return wizard JSON onto flat ``financial_profiles`` scalars.

The 8-section wizard stores rich detail in ``tax_return_detail``; this module
derives the aggregate columns the recommendation ranker already understands.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any


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
    """``2024-2025`` → ``2024_25`` for the profile ``tax_year`` column."""
    cleaned = ya.strip()
    if "_" in cleaned and len(cleaned) == 7:
        return cleaned
    if "-" in cleaned:
        start, end = cleaned.split("-", 1)
        return f"{start}_{end[-2:]}"
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
        "deemed": "dual",
    }
    return mapping.get(value, "resident")


def sync_scalars_from_tax_return(detail: dict[str, Any]) -> dict[str, Any]:
    """Return ORM column updates derived from ``tax_return_detail``."""
    if not detail:
        return {}

    out: dict[str, Any] = {}
    s1 = detail.get("section1") or {}
    s2 = detail.get("section2") or {}
    s3 = detail.get("section3") or {}
    s5 = detail.get("section5") or {}
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
        nat = str(s1["nationality"])
        out["nationality"] = {"lk": "Sri Lankan", "dual": "Dual Citizen", "foreign": "Foreign"}.get(
            nat, nat
        )
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
        out["annual_bonus_lkr"] = bonus_annual
        out["epf_balance"] = epf_annual
        out["etf_balance"] = etf_annual
        out["occupation"] = "employee"

    fds = list(s3.get("fds") or [])
    fd_principal = sum((_dec(fd.get("principal")) for fd in fds), Decimal("0"))
    fd_interest = sum((_dec(fd.get("interest")) for fd in fds), Decimal("0"))
    savings_interest = _dec((s3.get("savings") or {}).get("interest"))
    if fd_principal > 0 or fd_interest > 0 or savings_interest > 0:
        out["existing_investments"] = fd_principal
        if savings_interest > 0:
            out["liquid_savings"] = savings_interest

    props = list(s5.get("properties") or [])
    if props:
        gross_rent = sum((_dec(p.get("gross")) for p in props), Decimal("0"))
        maintenance = sum((_dec(p.get("maintenance")) for p in props), Decimal("0"))
        out["property_value"] = gross_rent
        out["monthly_expenses"] = (maintenance / Decimal("12")).quantize(Decimal("0.01"))

    life = s6.get("life") or {}
    if life.get("premium"):
        out["life_insurance_premium_annual"] = _dec(life["premium"])
        out["health_insurance"] = True
    medical = s6.get("medical") or {}
    if medical.get("premium"):
        out["health_insurance"] = True
    mortgage = s6.get("mortgage") or {}
    if mortgage.get("interest"):
        out["home_loan_interest_annual"] = _dec(mortgage["interest"])
    charitable = s6.get("charitable") or {}
    donations = sum(
        (
            _dec(charitable.get("president")),
            _dec(charitable.get("approved")),
            _dec(charitable.get("religious")),
            _dec(charitable.get("other")),
        ),
        Decimal("0"),
    )
    if donations > 0:
        out["donations_annual"] = donations

    income_sources: list[dict[str, Any]] = []
    if employers and _sum_employer_field(employers, "gross") > 0:
        income_sources.append(
            {
                "kind": "employment",
                "monthly_amount": str(out.get("gross_monthly_income", Decimal("0"))),
                "currency": "LKR",
                "is_taxable": True,
            }
        )
    freelance = s2.get("freelance") or {}
    if _dec(freelance.get("lkr")) > 0:
        income_sources.append(
            {
                "kind": "business",
                "monthly_amount": str((_dec(freelance["lkr"]) / Decimal("12")).quantize(Decimal("0.01"))),
                "currency": "LKR",
                "is_taxable": True,
            }
        )
    if props and sum((_dec(p.get("gross")) for p in props), Decimal("0")) > 0:
        monthly_rent = (
            sum((_dec(p.get("gross")) for p in props), Decimal("0")) / Decimal("12")
        ).quantize(Decimal("0.01"))
        income_sources.append(
            {
                "kind": "rental",
                "monthly_amount": str(monthly_rent),
                "currency": "LKR",
                "is_taxable": True,
            }
        )
    if fd_interest > 0:
        income_sources.append(
            {
                "kind": "interest",
                "monthly_amount": str((fd_interest / Decimal("12")).quantize(Decimal("0.01"))),
                "currency": "LKR",
                "is_taxable": True,
            }
        )
    if income_sources:
        out["income_sources"] = income_sources

    return out
