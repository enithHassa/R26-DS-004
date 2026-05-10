"""Assessment-year scoping for the loaded rules bundle.

The YAML file defines one canonical ``assessment_year`` and baseline thresholds.
For each API request we derive a pack where:

* ``pack.assessment_year`` matches ``profile.tax_year`` / ``body.tax_year`` so the
  year-match compliance rule passes.
* **Personal relief** follows the aggregate relief schedule published by IRD for
  individuals (resident or non-resident citizen), as summarised on the Income Tax
  page (e.g. `ird.gov.lk` — amounts tied to calendar thresholds Jan 2020, Jan 2023,
  Apr 2025). Other caps and slabs remain those encoded in YAML until per-year
  bundles are added.

References (public summary, verify against consolidated Act / notices):

* Prior to 1 Jan 2020: LKR 500,000
* On or after 1 Jan 2020, before 1 Jan 2023: LKR 3,000,000
* On or after 1 Jan 2023, before 1 Apr 2025: LKR 1,200,000
* On or after 1 Apr 2025: LKR 1,800,000

We map these to assessment years by the **calendar year in which the YA begins**
(1 April), consistent with YA labels ``2018_19`` … ``2025_26``.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBRulePack

# First year of assessment in UI / API: 2018/19 (Act assessment after 1 Apr 2018).
_SUPPORTED_ASSESSMENT_YEARS: frozenset[str] = frozenset(
    f"{y}_{(y + 1) % 100:02d}" for y in range(2018, 2026)
)


def supported_assessment_years() -> frozenset[str]:
    return _SUPPORTED_ASSESSMENT_YEARS


def personal_relief_lkr_for_assessment_year(tax_year: str) -> Decimal:
    """IRD-style aggregate personal relief for the given ``YYYY_YY`` assessment code."""
    parts = tax_year.strip().split("_")
    if len(parts) != 2:
        msg = f"Invalid assessment year code {tax_year!r}"
        raise ValueError(msg)
    y_start = int(parts[0])
    # YA beginning 1 April y_start
    if y_start <= 2019:
        return Decimal("500_000")
    if y_start <= 2022:
        return Decimal("3_000_000")
    if y_start <= 2024:
        return Decimal("1_200_000")
    return Decimal("1_800_000")


def rules_pack_for_tax_year(base: TaxOptBRulePack, tax_year: str) -> TaxOptBRulePack:
    """Return a pack for ``tax_year`` with matching label and schedule-based personal relief."""
    key = tax_year.strip()
    if key not in _SUPPORTED_ASSESSMENT_YEARS:
        allowed = ", ".join(sorted(_SUPPORTED_ASSESSMENT_YEARS))
        msg = f"Unsupported assessment_year {key!r}. Allowed: {allowed}"
        raise ValueError(msg)

    relief = personal_relief_lkr_for_assessment_year(key)
    new_thresholds = replace(base.thresholds, personal_relief_annual=relief)

    if key == base.assessment_year and new_thresholds == base.thresholds:
        return base

    return replace(
        base,
        assessment_year=key,
        thresholds=new_thresholds,
    )


__all__ = [
    "personal_relief_lkr_for_assessment_year",
    "rules_pack_for_tax_year",
    "supported_assessment_years",
]
