"""Deterministic APIT-style tax computation (Phase B) — research / MVP.

Uses ``applied_relief`` from a **passing** :func:`evaluate_compliance` run so capped
deduction amounts match compliance exactly.

**Algorithm (progressive slabs):** Let ``T`` be taxable income after personal relief and
after total allowed deductions. For each slab row in order, each finite ``upper`` is the
**width** of that band (LKR), not a cumulative threshold. Tax for the band is
``min(remaining_T, width) * rate``. The last row uses ``upper is None`` as the remainder
band: tax ``remaining_T * rate``, then stop.

Personal relief is subtracted from the income basis **before** slabs. Income basis is
``profile.estimated_annual_taxable_income`` when set, else ``profile.annual_gross_income``
(aligned with charitable donation cap basis in compliance). **Structured financial**
intake always leaves ``estimated_annual_taxable_income`` unset so basis is gross only.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from tax_opt_b_app.services.tax_opt_b_compliance_engine import evaluate_compliance
from tax_opt_b_app.services.tax_opt_b_rules_loader import TaxOptBApitSlab, TaxOptBRulePack
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBStrategyProposalV1
from tax_opt_b_app.tax_opt_b_schemas_tax_computation_v1 import (
    TaxOptBComputeTaxResponseV1,
    TaxOptBSlabTaxSliceV1,
    TaxOptBTaxComputationV1,
)


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


RESEARCH_DISCLAIMER = (
    "This tax figure is produced by a research / MVP rules pack and deterministic "
    "calculator. It is not legal or filing advice. Verify all thresholds, slabs, and "
    "reliefs against current Inland Revenue notices and the Act before any real use."
)


def income_basis_before_personal_relief(profile: TaxOptBProfileV1) -> Decimal:
    if profile.estimated_annual_taxable_income is not None:
        return profile.estimated_annual_taxable_income
    return profile.annual_gross_income


def sum_allowed_deductions_from_applied(applied_relief: dict[str, Any]) -> Decimal:
    total = Decimal("0")
    for _key, payload in applied_relief.items():
        if not isinstance(payload, dict):
            continue
        raw = payload.get("allowed")
        if raw is None:
            continue
        total += Decimal(str(raw))
    return _q1(total)


def allocate_progressive_slabs(
    taxable: Decimal,
    slabs: tuple[TaxOptBApitSlab, ...],
) -> tuple[Decimal, list[TaxOptBSlabTaxSliceV1]]:
    """Return ``(total_tax, per-slab breakdown)`` for non-negative ``taxable``."""
    if taxable < 0:
        raise ValueError("taxable must be non-negative")
    remaining = _q1(taxable)
    if remaining <= 0:
        return Decimal("0"), []
    total_tax = Decimal("0")
    out: list[TaxOptBSlabTaxSliceV1] = []
    for idx, slab in enumerate(slabs):
        if remaining <= 0:
            break
        if slab.upper is None:
            chunk = remaining
            tax_slice = _q1(chunk * slab.rate)
            total_tax += tax_slice
            out.append(
                TaxOptBSlabTaxSliceV1(
                    slab_index=idx,
                    rate=str(slab.rate),
                    slice_width_cap=None,
                    taxable_in_slice=str(chunk),
                    tax_in_slice=str(tax_slice),
                )
            )
            remaining = Decimal("0")
            break
        width = Decimal(int(slab.upper))
        chunk = min(remaining, width)
        tax_slice = _q1(chunk * slab.rate)
        total_tax += tax_slice
        out.append(
            TaxOptBSlabTaxSliceV1(
                slab_index=idx,
                rate=str(slab.rate),
                slice_width_cap=str(width),
                taxable_in_slice=str(chunk),
                tax_in_slice=str(tax_slice),
            )
        )
        remaining = _q1(remaining - chunk)
    return _q1(total_tax), out


def compute_apit_liability(
    *,
    profile: TaxOptBProfileV1,
    applied_relief: dict[str, Any],
    pack: TaxOptBRulePack,
) -> TaxOptBTaxComputationV1:
    """Compute MVP APIT-style liability from profile and **post-compliance** ``applied_relief``.

    Preconditions: ``applied_relief`` must reflect a passing compliance evaluation
    (capped ``allowed`` amounts per relief code). Empty dict means no deductions claimed.
    """
    basis = _q1(income_basis_before_personal_relief(profile))
    pr = _q1(pack.thresholds.personal_relief_annual)
    after_pr = _q1(max(Decimal("0"), basis - pr))
    total_ded = sum_allowed_deductions_from_applied(applied_relief)
    after_ded = _q1(max(Decimal("0"), after_pr - total_ded))
    total_tax, slab_slices = allocate_progressive_slabs(after_ded, pack.thresholds.apit_slabs)

    per_deduction: list[dict[str, Any]] = []
    for relief_code in sorted(applied_relief.keys()):
        payload = applied_relief[relief_code]
        if isinstance(payload, dict):
            per_deduction.append({"relief_code": relief_code, **{k: str(v) for k, v in payload.items()}})

    algo = (
        "Income basis = estimated_annual_taxable_income if set on profile (manual/API), "
        "else annual_gross_income. Structured financial intake uses salary + business + investment + other income as gross. "
        "Taxable after personal relief = max(0, basis - personal_relief_annual). "
        "Taxable after deductions = max(0, that - sum of allowed amounts in applied_relief). "
        "Slabs: each finite upper is band width; allocate remaining taxable left-to-right; "
        "last band upper null taxes all remainder at that rate."
    )

    return TaxOptBTaxComputationV1(
        income_basis_before_personal_relief=str(basis),
        annual_gross_income=str(profile.annual_gross_income),
        estimated_annual_taxable_income=(
            str(profile.estimated_annual_taxable_income)
            if profile.estimated_annual_taxable_income is not None
            else None
        ),
        personal_relief_annual=str(pr),
        taxable_after_personal_relief=str(after_pr),
        total_allowed_deductions=str(total_ded),
        per_deduction_allowed=per_deduction,
        taxable_after_deductions=str(after_ded),
        slab_slices=slab_slices,
        total_tax=str(total_tax),
        algorithm_documentation=algo,
    )


def run_compliance_and_compute_tax(
    profile: TaxOptBProfileV1,
    strategy: TaxOptBStrategyProposalV1,
    pack: TaxOptBRulePack,
    *,
    rules_version_label: str | None = None,
) -> TaxOptBComputeTaxResponseV1:
    compliance = evaluate_compliance(
        profile,
        strategy,
        pack=pack,
        rules_version_label=rules_version_label,
    )
    if not compliance.passed:
        return TaxOptBComputeTaxResponseV1(
            compliance=compliance,
            tax_computation=None,
            research_disclaimer=RESEARCH_DISCLAIMER,
        )
    tax = compute_apit_liability(
        profile=profile,
        applied_relief=compliance.applied_relief,
        pack=pack,
    )
    return TaxOptBComputeTaxResponseV1(
        compliance=compliance,
        tax_computation=tax,
        research_disclaimer=RESEARCH_DISCLAIMER,
    )


__all__ = [
    "RESEARCH_DISCLAIMER",
    "allocate_progressive_slabs",
    "compute_apit_liability",
    "income_basis_before_personal_relief",
    "run_compliance_and_compute_tax",
    "sum_allowed_deductions_from_applied",
]
