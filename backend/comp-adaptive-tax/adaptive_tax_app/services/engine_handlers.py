"""Phase 5.0b — thin handler registry with provenance checks.

Each executable handler must resolve ≥1 approved Act-backed ``rule_source``
(via :mod:`adaptive_tax_app.services.provenance`) before its numeric effect
is trusted in strict mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from adaptive_tax_app.config import AdaptiveTaxSettings
from adaptive_tax_app.services.provenance import (
    ProvenanceResolution,
    require_provenance,
)

# Stable handler ids used by the rule engine + bootstrap fixture.
HANDLER_SUM_ASSESSABLE = "sum_assessable"
HANDLER_AGGREGATE_EMPLOYMENT = "aggregate_employment_components"
HANDLER_EXCLUDE_EMPLOYMENT_EXEMPT = "exclude_employment_exempt_lines"
HANDLER_AGGREGATE_INVESTMENT = "aggregate_investment_components"
HANDLER_AGGREGATE_BUSINESS = "aggregate_business_components"
HANDLER_AGGREGATE_OTHER = "aggregate_other_income_components"
HANDLER_AGGREGATE_QP = "aggregate_qualifying_payment_components"
HANDLER_AGGREGATE_DONATION = "aggregate_donation_components"
HANDLER_EXCLUDE_FINAL_WHT = "exclude_if_final_wht"
HANDLER_EXCLUDE_INVESTMENT_FINAL_WHT = "exclude_investment_final_wht"
HANDLER_EXCLUDE_OTHER_FINAL_WHT = "exclude_other_final_wht"
HANDLER_COMPUTE_BUSINESS_NET = "compute_business_net"
HANDLER_DEDUCT_BUSINESS_EXPENSES = "deduct_business_expenses"
HANDLER_DEDUCT_CAPITAL_ALLOWANCES = "deduct_capital_allowances"
HANDLER_CAP_QP = "cap_absolute:qualifying_payment_cap"
HANDLER_CAP_DONATION = "cap_percent_assessable:donation_cap"
HANDLER_CAP_SOLAR = "cap_absolute:solar_panel_relief"
HANDLER_CAP_RENT = "cap_rent_relief"
HANDLER_CAP_SENIOR = "cap_senior_citizen_interest_relief"
HANDLER_DEDUCT_QP = "deduct_qualifying_payment"
HANDLER_CARRY_FORWARD_QP = "carry_forward_qp"
HANDLER_DEDUCT_DONATION = "deduct_donation"
HANDLER_DEDUCT_SOLAR = "deduct_solar_panel_relief"
HANDLER_DEDUCT_RENT = "deduct_rent_relief"
HANDLER_DEDUCT_SENIOR = "deduct_senior_citizen_interest_relief"
HANDLER_PERSONAL_RELIEF = "personal_relief_resident"
HANDLER_SLAB_BAND = "slab_band"
HANDLER_FINAL_TAX = "final_tax"
HANDLER_TAX_CREDIT = "tax_credit"


@dataclass(frozen=True)
class HandlerGate:
    handler_id: str
    resolution: ProvenanceResolution


def gate(
    handler_id: str,
    assessment_year: str,
    *,
    settings: AdaptiveTaxSettings | None = None,
    extra_keys: list[str] | None = None,
    executable: bool = True,
) -> HandlerGate:
    """Run provenance check for ``handler_id`` and return the resolution."""
    resolution = require_provenance(
        handler_id,
        assessment_year,
        settings=settings,
        extra_keys=extra_keys,
        executable=executable,
    )
    return HandlerGate(handler_id=handler_id, resolution=resolution)


def income_handler_id(concept_id: str) -> str:
    return f"{HANDLER_SUM_ASSESSABLE}:{concept_id}"


def deduct_handler_id(concept_id: str) -> str:
    return f"deduct_{concept_id}"


def cap_handler_id(cap_concept_id: str) -> str:
    if cap_concept_id == "donation_cap":
        return HANDLER_CAP_DONATION
    if cap_concept_id == "qualifying_payment_cap":
        return HANDLER_CAP_QP
    if cap_concept_id == "solar_panel_relief":
        return HANDLER_CAP_SOLAR
    if cap_concept_id == "rent_relief":
        return HANDLER_CAP_RENT
    if cap_concept_id == "senior_citizen_interest_relief":
        return HANDLER_CAP_SENIOR
    return f"cap_absolute:{cap_concept_id}"


# Registry map (documentation + tests); calculate() calls :func:`gate` directly.
HANDLER_REGISTRY: dict[str, Callable[..., HandlerGate]] = {
    HANDLER_SUM_ASSESSABLE: lambda year, **kw: gate(HANDLER_SUM_ASSESSABLE, year, **kw),
    HANDLER_AGGREGATE_EMPLOYMENT: lambda year, **kw: gate(
        HANDLER_AGGREGATE_EMPLOYMENT, year, **kw
    ),
    HANDLER_EXCLUDE_EMPLOYMENT_EXEMPT: lambda year, **kw: gate(
        HANDLER_EXCLUDE_EMPLOYMENT_EXEMPT, year, **kw
    ),
    HANDLER_AGGREGATE_INVESTMENT: lambda year, **kw: gate(
        HANDLER_AGGREGATE_INVESTMENT, year, **kw
    ),
    HANDLER_AGGREGATE_BUSINESS: lambda year, **kw: gate(
        HANDLER_AGGREGATE_BUSINESS, year, **kw
    ),
    HANDLER_AGGREGATE_OTHER: lambda year, **kw: gate(
        HANDLER_AGGREGATE_OTHER, year, **kw
    ),
    HANDLER_AGGREGATE_QP: lambda year, **kw: gate(HANDLER_AGGREGATE_QP, year, **kw),
    HANDLER_AGGREGATE_DONATION: lambda year, **kw: gate(
        HANDLER_AGGREGATE_DONATION, year, **kw
    ),
    HANDLER_EXCLUDE_FINAL_WHT: lambda year, **kw: gate(
        HANDLER_EXCLUDE_FINAL_WHT, year, **kw
    ),
    HANDLER_EXCLUDE_INVESTMENT_FINAL_WHT: lambda year, **kw: gate(
        HANDLER_EXCLUDE_INVESTMENT_FINAL_WHT, year, **kw
    ),
    HANDLER_EXCLUDE_OTHER_FINAL_WHT: lambda year, **kw: gate(
        HANDLER_EXCLUDE_OTHER_FINAL_WHT, year, **kw
    ),
    HANDLER_COMPUTE_BUSINESS_NET: lambda year, **kw: gate(
        HANDLER_COMPUTE_BUSINESS_NET, year, **kw
    ),
    HANDLER_DEDUCT_BUSINESS_EXPENSES: lambda year, **kw: gate(
        HANDLER_DEDUCT_BUSINESS_EXPENSES, year, **kw
    ),
    HANDLER_DEDUCT_CAPITAL_ALLOWANCES: lambda year, **kw: gate(
        HANDLER_DEDUCT_CAPITAL_ALLOWANCES, year, **kw
    ),
    HANDLER_CAP_QP: lambda year, **kw: gate(HANDLER_CAP_QP, year, **kw),
    HANDLER_CAP_DONATION: lambda year, **kw: gate(HANDLER_CAP_DONATION, year, **kw),
    HANDLER_CAP_SOLAR: lambda year, **kw: gate(HANDLER_CAP_SOLAR, year, **kw),
    HANDLER_CAP_RENT: lambda year, **kw: gate(HANDLER_CAP_RENT, year, **kw),
    HANDLER_CAP_SENIOR: lambda year, **kw: gate(HANDLER_CAP_SENIOR, year, **kw),
    HANDLER_DEDUCT_QP: lambda year, **kw: gate(HANDLER_DEDUCT_QP, year, **kw),
    HANDLER_CARRY_FORWARD_QP: lambda year, **kw: gate(HANDLER_CARRY_FORWARD_QP, year, **kw),
    HANDLER_DEDUCT_DONATION: lambda year, **kw: gate(HANDLER_DEDUCT_DONATION, year, **kw),
    HANDLER_DEDUCT_SOLAR: lambda year, **kw: gate(HANDLER_DEDUCT_SOLAR, year, **kw),
    HANDLER_DEDUCT_RENT: lambda year, **kw: gate(HANDLER_DEDUCT_RENT, year, **kw),
    HANDLER_DEDUCT_SENIOR: lambda year, **kw: gate(HANDLER_DEDUCT_SENIOR, year, **kw),
    HANDLER_PERSONAL_RELIEF: lambda year, **kw: gate(HANDLER_PERSONAL_RELIEF, year, **kw),
    HANDLER_SLAB_BAND: lambda year, **kw: gate(HANDLER_SLAB_BAND, year, **kw),
    HANDLER_FINAL_TAX: lambda year, **kw: gate(HANDLER_FINAL_TAX, year, **kw),
    HANDLER_TAX_CREDIT: lambda year, **kw: gate(HANDLER_TAX_CREDIT, year, **kw),
}
