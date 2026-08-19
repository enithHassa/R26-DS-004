"""Normalize CalculateTaxRequestV1: catalog-keyed filing_lines → head scalars.

Phase 6.1–6.5: employment (Sec 5), business (Sec 6/11/16), investment (Sec 7),
other income (Sec 8 residual), qualifying payments / donations (Sec 52 /
Fifth Schedule), and tax credits (Sec 89). When any enabled-head
``filing_lines`` have amount > 0, they win over that head's scalar fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from adaptive_tax_app.config import AdaptiveTaxSettings, get_adaptive_tax_settings
from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1, FilingLineV1
from adaptive_tax_app.services.filing_catalog import (
    is_component_active_for_year,
    load_filing_catalog,
)

Treatment = Literal["include", "exempt", "final_withholding", "deduct", "credit"]

_ENABLED_CARDS = frozenset(
    {
        "employment",
        "business",
        "investment",
        "other_income",
        "qualifying_payments",
        "tax_credits",
        "statutory_reliefs",
    }
)

_BIZ_NET_ID = "biz_net_profits"
_BIZ_GROSS_ID = "biz_gross"
_BIZ_DED_ID = "biz_deductions"
_BIZ_CA_ID = "biz_capital_allowances"


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@dataclass
class ComponentTraceRow:
    component_id: str
    display_name: str
    amount: Decimal
    treatment_applied: Treatment
    section: str | None = None
    paragraph: str | None = None
    reason_short: str | None = None
    rule_source_ids: list[str] = field(default_factory=list)
    included_in_assessable: bool = False
    legal_confidence: str | None = None
    card_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "display_name": self.display_name,
            "amount": str(_q1(self.amount)),
            "treatment_applied": self.treatment_applied,
            "section": self.section,
            "paragraph": self.paragraph,
            "reason_short": self.reason_short,
            "rule_source_ids": list(self.rule_source_ids),
            "included_in_assessable": self.included_in_assessable,
            "legal_confidence": self.legal_confidence,
            "card_id": self.card_id,
        }


@dataclass
class NormalizeResult:
    request: CalculateTaxRequestV1
    component_trace: list[ComponentTraceRow] = field(default_factory=list)
    head_subtotals: dict[str, Decimal] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    used_filing_lines: bool = False


@dataclass
class _HeadBucket:
    include: Decimal = Decimal("0")
    exempt: Decimal = Decimal("0")
    final_wht: Decimal = Decimal("0")
    deduct: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    brought_forward: Decimal = Decimal("0")
    gross: Decimal = Decimal("0")
    capital_allowances: Decimal = Decimal("0")
    touched: bool = False


def normalize_request(
    request: CalculateTaxRequestV1,
    *,
    settings: AdaptiveTaxSettings | None = None,
) -> NormalizeResult:
    """Return a request copy with head scalars derived from filing_lines when present."""
    cfg = settings or get_adaptive_tax_settings()
    warnings: list[str] = []
    lines = list(request.filing_lines or [])

    # Fold legacy Donations card / scalar into Fifth Sch 1(a) QP line.
    has_1a_line = any(
        ln.component_id.startswith("don_")
        or ln.component_id in {"don_approved_charitable", "qp_approved_charitable"}
        for ln in lines
    )
    if _q1(request.donations) > 0 and not has_1a_line:
        lines.append(
            FilingLineV1(
                component_id="qp_approved_charitable",
                amount=request.donations,  # type: ignore[arg-type]
            )
        )
        warnings.append("scalar_donations_mapped_to_qp_approved_charitable")
    if _q1(request.donations) > 0:
        request = request.model_copy(update={"donations": Decimal("0")})

    mapped_lines: list[FilingLineV1] = []
    for line in lines:
        cid = line.component_id
        if cid.startswith("don_") or cid == "don_approved_charitable":
            warnings.append(f"legacy_{cid}_mapped_to_qp_approved_charitable")
            mapped_lines.append(
                line.model_copy(update={"component_id": "qp_approved_charitable"})
            )
        else:
            mapped_lines.append(line)
    lines = mapped_lines

    if not lines:
        return NormalizeResult(request=request, warnings=warnings)

    catalog = load_filing_catalog(settings=cfg)
    by_id = {c.component_id: c for c in catalog.components}

    buckets: dict[str, _HeadBucket] = {
        "employment": _HeadBucket(),
        "business": _HeadBucket(),
        "investment": _HeadBucket(),
        "other_income": _HeadBucket(),
        "qualifying_payments": _HeadBucket(),
        "tax_credits": _HeadBucket(),
        "statutory_reliefs": _HeadBucket(),
    }
    trace: list[ComponentTraceRow] = []

    for line in lines:
        amount = _q1(line.amount)
        if amount <= 0:
            continue

        # Legacy aggregate Other → review-only (never auto-deduct).
        if line.component_id == "qp_other_sec52":
            warnings.append("legacy_qp_other_mapped_to_unclassified_review")
            buckets["qualifying_payments"].touched = True
            trace.append(
                ComponentTraceRow(
                    component_id="qp_unclassified_review",
                    display_name="Unclassified / Other Payment — Requires Review",
                    amount=amount,
                    treatment_applied="deduct",
                    section="52",
                    paragraph=None,
                    reason_short=(
                        "Legacy qp_other_sec52 cannot be auto-classified to a "
                        "Fifth Schedule paragraph."
                    ),
                    rule_source_ids=[],
                    included_in_assessable=False,
                    legal_confidence="medium",
                    card_id="qualifying_payments",
                )
            )
            continue

        # Legacy combined 1(b) / funds lines — map without inventing CF eligibility.
        effective_id = line.component_id
        if effective_id in {"qp_gov_local_university_funds", "qp_gov_local_authority"}:
            warnings.append(
                f"legacy_{effective_id}_mapped_to_qp_government_sri_lanka"
            )
            effective_id = "qp_government_sri_lanka"
        elif effective_id == "qp_approved_funds":
            warnings.append("legacy_qp_approved_funds_mapped_to_qp_other_listed_funds")
            effective_id = "qp_other_listed_funds"

        row = by_id.get(effective_id)
        if row is None:
            warnings.append(f"unknown_component_id:{line.component_id}")
            continue
        if row.card_id not in _ENABLED_CARDS:
            warnings.append(f"head_not_enabled_yet:{row.card_id}:{line.component_id}")
            continue
        if row.status in {"inactive", "pending_unsupported"} or row.engine_support == "unsupported":
            warnings.append(f"unsupported_ignored:{line.component_id}")
            continue
        if row.legal_confidence in {"pending", "low"}:
            warnings.append(f"low_confidence_ignored:{line.component_id}")
            continue
        if not is_component_active_for_year(row, request.assessment_year):
            warnings.append(
                f"ya_inactive_ignored:{line.component_id}:{request.assessment_year}"
            )
            continue

        treatment: Treatment
        if line.treatment is not None:
            treatment = line.treatment  # type: ignore[assignment]
        else:
            treatment = row.default_treatment  # type: ignore[assignment]

        bucket = buckets[row.card_id]
        included = treatment == "include"

        # Phase 6.4 — map business catalog lines onto Sec 6/11/16 scalars.
        if row.card_id == "business":
            if row.component_id == _BIZ_NET_ID:
                bucket.include += amount
                included = True
                treatment = "include"
            elif row.component_id == _BIZ_GROSS_ID:
                bucket.gross += amount
                included = False
                treatment = "include"
            elif row.component_id == _BIZ_DED_ID:
                bucket.deduct += amount
                included = False
                treatment = "deduct"
            elif row.component_id == _BIZ_CA_ID:
                bucket.capital_allowances += amount
                included = False
                treatment = "deduct"
            else:
                warnings.append(f"unknown_business_component:{line.component_id}")
                continue
            bucket.touched = True
            sources = [sid for sid in (row.rule_source_id, row.source_doc_id) if sid]
            trace.append(
                ComponentTraceRow(
                    component_id=row.component_id,
                    display_name=line.label_override or row.display_name,
                    amount=amount,
                    treatment_applied=treatment,
                    section=row.section,
                    paragraph=row.paragraph,
                    reason_short=row.reason_short,
                    rule_source_ids=sources,
                    included_in_assessable=included,
                    legal_confidence=row.legal_confidence,
                    card_id=row.card_id,
                )
            )
            continue

        # Sec 52(4) brought-forward is a separate scalar, not current-year QP claim.
        if row.component_id == "qp_brought_forward":
            bucket.brought_forward += amount
            bucket.touched = True
            sources = [sid for sid in (row.rule_source_id, row.source_doc_id) if sid]
            trace.append(
                ComponentTraceRow(
                    component_id=row.component_id,
                    display_name=line.label_override or row.display_name,
                    amount=amount,
                    treatment_applied=treatment,
                    section=row.section,
                    paragraph=row.paragraph,
                    reason_short=row.reason_short,
                    rule_source_ids=sources,
                    included_in_assessable=False,
                    legal_confidence=row.legal_confidence,
                    card_id=row.card_id,
                )
            )
            continue

        # Unclassified QP — audit only; never inflate Sec 52 scalar claim.
        if row.component_id == "qp_unclassified_review":
            bucket.touched = True
            warnings.append("qp_unclassified_needs_review")
            sources = [sid for sid in (row.rule_source_id, row.source_doc_id) if sid]
            trace.append(
                ComponentTraceRow(
                    component_id=row.component_id,
                    display_name=line.label_override or row.display_name,
                    amount=amount,
                    treatment_applied=treatment,
                    section=row.section,
                    paragraph=row.paragraph,
                    reason_short=row.reason_short
                    or "Requires Fifth Schedule classification before deduction.",
                    rule_source_ids=sources,
                    included_in_assessable=False,
                    legal_confidence=row.legal_confidence,
                    card_id=row.card_id,
                )
            )
            continue

        if treatment == "include":
            bucket.include += amount
        elif treatment == "exempt":
            bucket.exempt += amount
        elif treatment == "final_withholding":
            bucket.final_wht += amount
        elif treatment == "deduct":
            bucket.deduct += amount
        elif treatment == "credit":
            bucket.credit += amount
        else:
            warnings.append(f"treatment_ignored:{line.component_id}:{treatment}")
            continue

        bucket.touched = True
        sources = [sid for sid in (row.rule_source_id, row.source_doc_id) if sid]
        trace.append(
            ComponentTraceRow(
                component_id=row.component_id,
                display_name=line.label_override or row.display_name,
                amount=amount,
                treatment_applied=treatment,
                section=row.section,
                paragraph=row.paragraph,
                reason_short=row.reason_short,
                rule_source_ids=sources,
                included_in_assessable=included,
                legal_confidence=row.legal_confidence,
                card_id=row.card_id,
            )
        )

    if not any(b.touched for b in buckets.values()):
        return NormalizeResult(request=request, warnings=warnings, component_trace=trace)

    warnings.append("input_precedence=components")
    updates: dict[str, Any] = {}
    head_subtotals: dict[str, Decimal] = {}

    emp = buckets["employment"]
    if emp.touched:
        updates["employment_income"] = emp.include
        updates["employment_final_withholding"] = emp.final_wht
        head_subtotals["employment_include"] = emp.include
        head_subtotals["employment_exempt"] = emp.exempt
        head_subtotals["employment_final_withholding"] = emp.final_wht
        head_subtotals["employment_net_for_assessable"] = emp.include

    biz = buckets["business"]
    if biz.touched:
        if biz.gross > 0 and biz.include > 0:
            warnings.append("business_net_ignored_when_gross_present")
        if biz.gross > 0:
            updates["business_gross"] = biz.gross
            updates["business_deductions"] = biz.deduct
            updates["capital_allowances"] = biz.capital_allowances
            updates["business_income"] = Decimal("0")
        else:
            updates["business_income"] = biz.include
            updates["business_gross"] = Decimal("0")
            updates["business_deductions"] = Decimal("0")
            updates["capital_allowances"] = Decimal("0")
        head_subtotals["business_net"] = biz.include
        head_subtotals["business_gross"] = biz.gross
        head_subtotals["business_deductions"] = biz.deduct
        head_subtotals["business_capital_allowances"] = biz.capital_allowances

    inv = buckets["investment"]
    if inv.touched:
        updates["investment_income"] = inv.include
        updates["investment_final_withholding"] = inv.final_wht
        head_subtotals["investment_include"] = inv.include
        head_subtotals["investment_exempt"] = inv.exempt
        head_subtotals["investment_final_withholding"] = inv.final_wht
        head_subtotals["investment_net_for_assessable"] = inv.include

    oth = buckets["other_income"]
    if oth.touched:
        updates["other_income"] = oth.include
        updates["other_final_withholding"] = oth.final_wht
        head_subtotals["other_include"] = oth.include
        head_subtotals["other_exempt"] = oth.exempt
        head_subtotals["other_final_withholding"] = oth.final_wht
        head_subtotals["other_net_for_assessable"] = oth.include

    qp = buckets["qualifying_payments"]
    if qp.touched:
        updates["qualifying_payments"] = qp.deduct
        if qp.brought_forward > 0:
            updates["qualifying_payment_brought_forward"] = qp.brought_forward
        head_subtotals["qualifying_payments_claimed"] = qp.deduct
        head_subtotals["qualifying_payment_brought_forward"] = qp.brought_forward

    cred = buckets["tax_credits"]
    if cred.touched:
        updates["apit_already_paid"] = cred.credit
        head_subtotals["apit_already_paid"] = cred.credit

    # Decision 1b: Fifth Sch 2(c) 25% base is the included inv_rents line
    # (gross rents entered as include). Do not net out head-level FWH.
    inv_rents = sum(
        (row.amount for row in trace if row.component_id == "inv_rents" and row.included_in_assessable),
        Decimal("0"),
    )
    if inv_rents > 0:
        head_subtotals["inv_rents"] = inv_rents

    relief = buckets["statutory_reliefs"]
    if relief.touched:
        solar = sum(
            (row.amount for row in trace if row.component_id == "relief_solar_panel"),
            Decimal("0"),
        )
        rent = sum(
            (row.amount for row in trace if row.component_id == "relief_rent"),
            Decimal("0"),
        )
        if solar > 0:
            updates["solar_panel_relief"] = solar
            head_subtotals["solar_panel_relief"] = solar
        if rent > 0:
            updates["rent_relief"] = rent
            head_subtotals["rent_relief"] = rent

    updated = request.model_copy(update=updates)
    return NormalizeResult(
        request=updated,
        component_trace=trace,
        head_subtotals=head_subtotals,
        warnings=warnings,
        used_filing_lines=True,
    )


def filing_lines_from_mapping(amounts: dict[str, str | Decimal]) -> list[FilingLineV1]:
    """Test helper: build filing_lines from component_id → amount."""
    out: list[FilingLineV1] = []
    for cid, raw in amounts.items():
        out.append(FilingLineV1(component_id=str(cid), amount=raw))  # type: ignore[arg-type]
    return out
