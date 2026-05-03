"""Pure-function tax rules engine for Sri Lanka APIT.

Loads a versioned YAML rule pack (e.g. ``sl_tax_2024_25.yaml``) and exposes
small functions that compute the annual tax liability for a given annual
taxable income, plus a deductions helper used by the strategy generator.

The engine has no dependency on the FastAPI app or the database. It is safe
to call from notebooks, scripts, and the offline data generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class TaxRules:
    version: str
    currency: str
    personal_relief_annual: float
    apit_slabs: tuple[tuple[float | None, float], ...]
    deductions: dict[str, float]
    provident: dict[str, float]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TaxRules:
        slabs = tuple(
            (
                None if slab.get("upper") is None else float(slab["upper"]),
                float(slab["rate"]),
            )
            for slab in raw["apit_slabs"]
        )
        return cls(
            version=str(raw["version"]),
            currency=str(raw.get("currency", "LKR")),
            personal_relief_annual=float(raw["personal_relief_annual"]),
            apit_slabs=slabs,
            deductions={k: float(v) for k, v in raw.get("deductions", {}).items()},
            provident={k: float(v) for k, v in raw.get("provident", {}).items()},
        )


def load_tax_rules(path: str | Path) -> TaxRules:
    """Load and validate a YAML rule pack."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Tax rule pack at {path} did not parse to a dict")
    return TaxRules.from_dict(raw)


def compute_annual_tax(annual_taxable_income: float, rules: TaxRules) -> float:
    """Compute total APIT for an *annual* taxable income.

    ``apit_slabs`` are interpreted as bracket *widths* in LKR
    (with the final entry's ``upper=null`` meaning "all remaining income").
    Personal relief is subtracted before the slabs apply.
    """
    if annual_taxable_income <= 0:
        return 0.0

    remaining = max(0.0, annual_taxable_income - rules.personal_relief_annual)
    if remaining <= 0:
        return 0.0

    tax = 0.0
    for upper, rate in rules.apit_slabs:
        if upper is None:
            tax += remaining * rate
            remaining = 0.0
            break
        bracket = min(remaining, upper)
        tax += bracket * rate
        remaining -= bracket
        if remaining <= 0:
            break
    return round(tax, 2)


def apply_deductions(
    *,
    annual_income: float,
    rules: TaxRules,
    rent_paid_annual: float = 0.0,
    life_insurance_premium_annual: float = 0.0,
    health_insurance_premium_annual: float = 0.0,
    home_loan_interest_annual: float = 0.0,
    donations_annual: float = 0.0,
    retirement_contribution_annual: float = 0.0,
) -> float:
    """Return the *taxable* annual income after applying capped deductions.

    Each deduction is clamped at the cap declared in the YAML pack. The
    returned value never goes below zero.
    """
    d = rules.deductions
    rent_relief = min(rent_paid_annual * d.get("rent_relief_pct", 0.0), d.get("rent_relief_cap_annual", 0.0))
    life_relief = min(life_insurance_premium_annual, d.get("life_insurance_premium_cap_annual", 0.0))
    health_relief = min(health_insurance_premium_annual, d.get("health_insurance_premium_cap_annual", 0.0))
    home_loan_relief = min(home_loan_interest_annual, d.get("home_loan_interest_cap_annual", 0.0))
    donations_relief = min(donations_annual, annual_income * d.get("charitable_donations_cap_pct_of_taxable", 0.0))
    retirement_relief = min(
        retirement_contribution_annual,
        annual_income * d.get("retirement_contribution_cap_pct_of_income", 0.0),
        d.get("retirement_contribution_cap_annual", 0.0),
    )
    total_relief = (
        rent_relief
        + life_relief
        + health_relief
        + home_loan_relief
        + donations_relief
        + retirement_relief
    )
    return max(0.0, annual_income - total_relief)


__all__ = ["TaxRules", "apply_deductions", "compute_annual_tax", "load_tax_rules"]
