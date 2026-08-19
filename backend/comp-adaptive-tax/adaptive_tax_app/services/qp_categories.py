"""Fifth Schedule / Sec 52 category-level qualifying-payment rules (Phase 6.3).

Each typed QP component is evaluated for claimed → allowable under Fifth Sch
para 1 per-category limits; there is no fictional aggregate Sec 52 pool.
Sec 52(1) deducts the sum of allowables; Sec 52(4) carry-forward applies to
eligible undeducted amounts only.

Notes on assessable vs taxable for 1(a)/1(f):
Category caps use **assessable income** (research convention) to avoid a
circular taxable-income dependency before personal relief. Statutory wording
may refer to taxable income; this engine applies the 1/3 base on assessable
income deliberately — do not change without reconciling the full deduct path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Literal

CategoryStatus = Literal[
    "allowed",
    "partially_allowed",
    "disallowed",
    "needs_review",
    "not_applicable",
]

# Fifth Sch 1(b)(i) and 1(b)(v) — Sec 52(4) CF eligible for YA 2025/26.
SEC52_4_COMPONENT_IDS = frozenset(
    {
        "qp_government_sri_lanka",
        "qp_government_fund",
    }
)

_FILM_1F_ORDER = (
    "qp_film_production",
    "qp_cinema_construction",
    "qp_cinema_upgrading",
)

_NO_CEILING_IDS = frozenset(
    {
        "qp_government_sri_lanka",
        "qp_local_authority",
        "qp_university_hei",
        "qp_government_fund",
        "qp_other_listed_funds",
        "qp_gov_local_authority",  # legacy
        "qp_gov_local_university_funds",  # legacy
        "qp_approved_funds",  # legacy → other listed
        "qp_samurdhi_shop",
    }
)


def _q1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _floor1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_DOWN)


@dataclass(frozen=True)
class CategoryEval:
    component_id: str
    display_name: str
    claimed: Decimal
    allowable: Decimal
    disallowed: Decimal
    status: CategoryStatus
    legal_reference: str
    section: str
    paragraph: str | None
    reason: str
    formula: str
    include_in_sec52_aggregate: bool
    legal_confidence: str | None = None
    rule_source_ids: tuple[str, ...] = ()
    deducted_this_year: Decimal = Decimal("0")
    undeducted_amount: Decimal = Decimal("0")
    sec52_4_eligible: bool = False
    carry_forward_amount: Decimal = Decimal("0")
    carry_forward_basis: str = "none"

    def as_dict(self) -> dict[str, str | bool | None | list[str]]:
        return {
            "component_id": self.component_id,
            "display_name": self.display_name,
            "claimed": str(_q1(self.claimed)),
            "allowable": str(_q1(self.allowable)),
            "disallowed": str(_q1(self.disallowed)),
            "status": self.status,
            "legal_reference": self.legal_reference,
            "section": self.section,
            "paragraph": self.paragraph,
            "reason": self.reason,
            "formula": self.formula,
            "include_in_sec52_aggregate": self.include_in_sec52_aggregate,
            "legal_confidence": self.legal_confidence,
            "rule_source_ids": list(self.rule_source_ids),
            "claimed_amount": str(_q1(self.claimed)),
            "allowable_amount": str(_q1(self.allowable)),
            "deducted_this_year": str(_q1(self.deducted_this_year)),
            "undeducted_amount": str(_q1(self.undeducted_amount)),
            "sec52_4_eligible": self.sec52_4_eligible,
            "carry_forward_amount": str(_q1(self.carry_forward_amount)),
            "carry_forward_basis": self.carry_forward_basis,
        }


def _status(claimed: Decimal, allowable: Decimal) -> CategoryStatus:
    if claimed <= 0:
        return "allowed"
    if allowable <= 0:
        return "disallowed"
    if allowable < claimed:
        return "partially_allowed"
    return "allowed"


def is_sec52_4_eligible(component_id: str, assessment_year: str) -> bool:
    return assessment_year == "2025_26" and component_id in SEC52_4_COMPONENT_IDS


def evaluate_qp_category(
    *,
    component_id: str,
    display_name: str,
    claimed: Decimal,
    assessable: Decimal,
    assessment_year: str,
    section: str | None,
    paragraph: str | None,
    legal_confidence: str | None,
    rule_source_ids: list[str],
) -> CategoryEval:
    """Return claimed/allowable for one Fifth Schedule QP component."""
    claimed = _q1(max(Decimal("0"), claimed))
    assessable = _q1(max(Decimal("0"), assessable))
    section = section or "52"
    sources = tuple(sid for sid in rule_source_ids if sid)
    cf_basis = "none"
    if component_id in _FILM_1F_ORDER:
        cf_basis = "fifth_sch_1f"
    elif component_id in SEC52_4_COMPONENT_IDS:
        cf_basis = "sec52_4"

    if component_id == "qp_unclassified_review":
        return CategoryEval(
            component_id=component_id,
            display_name=display_name,
            claimed=claimed,
            allowable=Decimal("0"),
            disallowed=claimed,
            status="needs_review",
            legal_reference="Fifth Schedule — classification required",
            section=section,
            paragraph=paragraph,
            reason=(
                "Unclassified amount cannot be treated as a qualifying payment "
                "until matched to an applicable Fifth Schedule provision."
            ),
            formula="allowable = 0 (needs_review)",
            include_in_sec52_aggregate=False,
            legal_confidence=legal_confidence or "medium",
            rule_source_ids=sources,
            undeducted_amount=claimed,
            sec52_4_eligible=False,
            carry_forward_basis="none",
        )

    if component_id == "qp_approved_charitable":
        ti_third = _floor1(assessable / Decimal("3"))
        ceiling = min(Decimal("75000"), ti_third)
        allowable = min(claimed, ceiling)
        return CategoryEval(
            component_id=component_id,
            display_name=display_name,
            claimed=claimed,
            allowable=allowable,
            disallowed=_q1(claimed - allowable),
            status=_status(claimed, allowable),
            legal_reference="Fifth Schedule paragraph 1(a)",
            section=section,
            paragraph=paragraph or "Fifth Sch 1(a)",
            reason=(
                "Individual approved-charity donations limited to the lesser of "
                "Rs 75,000 and one-third of assessable income (Act text: taxable "
                "income; engine uses assessable to avoid circularity)."
            ),
            formula=(
                f"allowable = min(claimed, 75000, floor(assessable/3)={ti_third})"
            ),
            include_in_sec52_aggregate=True,
            legal_confidence=legal_confidence or "high",
            rule_source_ids=sources
            or ("bootstrap:qp_approved_charitable", "ird-ira-2017-base"),
            undeducted_amount=allowable,
            sec52_4_eligible=False,
            carry_forward_basis="none",
        )

    if component_id in _FILM_1F_ORDER:
        labels = {
            "qp_film_production": "Fifth Schedule paragraph 1(f)(i)",
            "qp_cinema_construction": "Fifth Schedule paragraph 1(f)(ii)",
            "qp_cinema_upgrading": "Fifth Schedule paragraph 1(f)(iii)",
        }
        if component_id == "qp_film_production" and claimed > 0 and claimed < Decimal(
            "5000000"
        ):
            return CategoryEval(
                component_id=component_id,
                display_name=display_name,
                claimed=claimed,
                allowable=Decimal("0"),
                disallowed=claimed,
                status="disallowed",
                legal_reference=labels[component_id],
                section=section,
                paragraph=paragraph or "Fifth Sch 1(f)(i)",
                reason=(
                    "Film production QP requires cost (including promotion) of not "
                    "less than Rs 5,000,000."
                ),
                formula="allowable = 0 (below Rs 5M film cost gate)",
                include_in_sec52_aggregate=True,
                legal_confidence=legal_confidence or "high",
                rule_source_ids=sources or ("ird-amend-2021-10", "ird-ira-2017-base"),
                undeducted_amount=Decimal("0"),
                sec52_4_eligible=False,
                carry_forward_basis="fifth_sch_1f",
            )
        item_ceiling = {
            "qp_film_production": claimed,
            "qp_cinema_construction": Decimal("25000000"),
            "qp_cinema_upgrading": Decimal("10000000"),
        }[component_id]
        provisional = min(claimed, item_ceiling)
        return CategoryEval(
            component_id=component_id,
            display_name=display_name,
            claimed=claimed,
            allowable=provisional,
            disallowed=_q1(claimed - provisional),
            status=_status(claimed, provisional),
            legal_reference=labels[component_id],
            section=section,
            paragraph=paragraph or "Fifth Sch 1(f)",
            reason=(
                "Film/cinema QP subject to item cost rules and a shared one-third "
                "of assessable income restriction for subparagraph 1(f). Multi-year "
                "1(f) carry of unused excess is not fully wired into Sec 52(4)."
            ),
            formula=(
                f"provisional = min(claimed, item_ceiling={item_ceiling}); "
                "shared 1/3 pool applied across 1(f) lines"
            ),
            include_in_sec52_aggregate=True,
            legal_confidence=legal_confidence or "high",
            rule_source_ids=sources or ("ird-amend-2021-10", "ird-ira-2017-base"),
            undeducted_amount=provisional,
            sec52_4_eligible=False,
            carry_forward_basis="fifth_sch_1f",
        )

    if component_id in _NO_CEILING_IDS:
        refs = {
            "qp_government_sri_lanka": "Fifth Schedule paragraph 1(b)(i)",
            "qp_local_authority": "Fifth Schedule paragraph 1(b)(ii)",
            "qp_university_hei": "Fifth Schedule paragraph 1(b)(iii)–(iv)",
            "qp_government_fund": "Fifth Schedule paragraph 1(b)(v)",
            "qp_other_listed_funds": "Fifth Schedule paragraph 1(b)(vi)–(x)",
            "qp_gov_local_authority": "Fifth Schedule paragraph 1(b)(i)–(ii)",
            "qp_gov_local_university_funds": "Fifth Schedule paragraph 1(b)",
            "qp_approved_funds": "Fifth Schedule paragraph 1(b)(vi)–(x)",
            "qp_samurdhi_shop": "Fifth Schedule paragraph 1(d)",
        }
        return CategoryEval(
            component_id=component_id,
            display_name=display_name,
            claimed=claimed,
            allowable=claimed,
            disallowed=Decimal("0"),
            status=_status(claimed, claimed),
            legal_reference=refs.get(component_id, "Fifth Schedule paragraph 1"),
            section=section,
            paragraph=paragraph,
            reason=(
                "No separate Fifth Schedule monetary ceiling for this item; "
                "full claimed amount enters the Sec 52 aggregate limitation."
            ),
            formula="allowable = claimed (no category ceiling; Sec 52 aggregate applies)",
            include_in_sec52_aggregate=True,
            legal_confidence=legal_confidence or "high",
            rule_source_ids=sources,
            undeducted_amount=claimed,
            sec52_4_eligible=is_sec52_4_eligible(component_id, assessment_year),
            carry_forward_basis=cf_basis if component_id in SEC52_4_COMPONENT_IDS else "none",
        )

    if component_id == "qp_brought_forward":
        if assessment_year != "2025_26":
            return CategoryEval(
                component_id=component_id,
                display_name=display_name,
                claimed=claimed,
                allowable=Decimal("0"),
                disallowed=claimed,
                status="not_applicable",
                legal_reference="Section 52(4)",
                section=section,
                paragraph="4",
                reason="Sec 52(4) brought-forward is not applicable for this assessment year.",
                formula="allowable = 0 (YA gate)",
                include_in_sec52_aggregate=False,
                legal_confidence=legal_confidence or "high",
                rule_source_ids=sources,
                undeducted_amount=Decimal("0"),
                sec52_4_eligible=False,
                carry_forward_basis="sec52_4",
            )
        return CategoryEval(
            component_id=component_id,
            display_name=display_name,
            claimed=claimed,
            allowable=claimed,
            disallowed=Decimal("0"),
            status=_status(claimed, claimed),
            legal_reference="Section 52(4)",
            section=section,
            paragraph="4",
            reason="Brought-forward amount added under Sec 52(4) before aggregate cap.",
            formula="allowable = claimed (Sec 52(4) brought forward)",
            include_in_sec52_aggregate=False,
            legal_confidence=legal_confidence or "high",
            rule_source_ids=sources,
            undeducted_amount=Decimal("0"),
            sec52_4_eligible=False,
            carry_forward_basis="sec52_4",
        )

    return CategoryEval(
        component_id=component_id,
        display_name=display_name,
        claimed=claimed,
        allowable=Decimal("0"),
        disallowed=claimed,
        status="needs_review",
        legal_reference="Fifth Schedule — unknown component",
        section=section,
        paragraph=paragraph,
        reason=(
            f"No category rule registered for {component_id}; amount held for review."
        ),
        formula="allowable = 0 (unknown category)",
        include_in_sec52_aggregate=False,
        legal_confidence=legal_confidence or "pending",
        rule_source_ids=sources,
        undeducted_amount=claimed,
        sec52_4_eligible=False,
        carry_forward_basis="none",
    )


def _apply_shared_1f_pool(
    evals: list[CategoryEval],
    *,
    assessable: Decimal,
) -> list[CategoryEval]:
    """Fifth Sch 1(f) proviso: total deduction ≤ one-third of assessable (proxy)."""
    pool = _floor1(max(Decimal("0"), assessable) / Decimal("3"))
    remaining = pool
    by_id = {e.component_id: e for e in evals}
    for cid in _FILM_1F_ORDER:
        ev = by_id.get(cid)
        if ev is None or ev.claimed <= 0:
            continue
        take = min(ev.allowable, remaining)
        remaining = _q1(remaining - take)
        by_id[cid] = replace(
            ev,
            allowable=take,
            disallowed=_q1(ev.claimed - take),
            status=_status(ev.claimed, take),
            undeducted_amount=take,
            reason=(
                f"{ev.reason} Shared 1(f) pool = floor(assessable/3)={pool}; "
                f"this line allotted {take}."
            ),
            formula=(
                f"allowable = min(provisional, remaining_1f_pool); "
                f"pool={pool}, allotted={take}"
            ),
        )
    return [by_id.get(e.component_id, e) for e in evals]


def evaluate_qp_filing_rows(
    rows: list[dict],
    *,
    assessable: Decimal,
    assessment_year: str,
) -> list[CategoryEval]:
    """Evaluate a list of QP component dicts (from normalize component_trace)."""
    out: list[CategoryEval] = []
    for row in rows:
        out.append(
            evaluate_qp_category(
                component_id=str(row["component_id"]),
                display_name=str(row.get("display_name") or row["component_id"]),
                claimed=Decimal(str(row.get("amount") or "0")),
                assessable=assessable,
                assessment_year=assessment_year,
                section=row.get("section"),
                paragraph=row.get("paragraph"),
                legal_confidence=row.get("legal_confidence"),
                rule_source_ids=list(row.get("rule_source_ids") or []),
            )
        )
    if any(e.component_id in _FILM_1F_ORDER for e in out):
        out = _apply_shared_1f_pool(out, assessable=assessable)
    # Stamp YA-specific Sec 52(4) eligibility after pool adjustments.
    stamped: list[CategoryEval] = []
    for ev in out:
        eligible = is_sec52_4_eligible(ev.component_id, assessment_year)
        stamped.append(
            replace(
                ev,
                sec52_4_eligible=eligible,
                carry_forward_basis=(
                    "sec52_4"
                    if ev.component_id in SEC52_4_COMPONENT_IDS
                    else ev.carry_forward_basis
                ),
            )
        )
    return stamped


def summarize_category_evals(
    evals: list[CategoryEval],
) -> dict[str, Decimal]:
    """Totals used by Sec 52 aggregate step."""
    claimed = sum((e.claimed for e in evals), Decimal("0"))
    before_sec52 = sum(
        (e.allowable for e in evals if e.include_in_sec52_aggregate),
        Decimal("0"),
    )
    review = sum(
        (e.claimed for e in evals if e.status == "needs_review"),
        Decimal("0"),
    )
    return {
        "total_claimed": _q1(claimed),
        "total_allowable_before_sec52": _q1(before_sec52),
        "total_needs_review": _q1(review),
    }


def allocate_sec52_deduction(
    evals: list[CategoryEval],
    *,
    allowed_for_categories: Decimal,
    assessment_year: str,
) -> tuple[list[CategoryEval], Decimal, Decimal]:
    """Proportionally allocate current-year Sec 52 deduction across category allowables.

    Returns (updated evals, carry_forward_out, carry_forward_not_eligible_undeducted).

    ``carry_forward_out`` = sum of ``carry_forward_amount`` (eligible undeducted only).
    Never equals unused absolute-cap headroom.
    """
    allowed_for_categories = _q1(max(Decimal("0"), allowed_for_categories))
    includable = [e for e in evals if e.include_in_sec52_aggregate and e.allowable > 0]
    total_allowable = sum((e.allowable for e in includable), Decimal("0"))
    if total_allowable <= 0 or allowed_for_categories <= 0:
        updated: list[CategoryEval] = []
        for ev in evals:
            unded = ev.allowable if ev.include_in_sec52_aggregate else Decimal("0")
            eligible = is_sec52_4_eligible(ev.component_id, assessment_year)
            cf_amt = unded if eligible else Decimal("0")
            updated.append(
                replace(
                    ev,
                    deducted_this_year=Decimal("0"),
                    undeducted_amount=_q1(unded),
                    sec52_4_eligible=eligible,
                    carry_forward_amount=_q1(cf_amt),
                )
            )
        cf_out = sum((e.carry_forward_amount for e in updated), Decimal("0"))
        not_elig = sum(
            (
                e.undeducted_amount
                for e in updated
                if e.include_in_sec52_aggregate and not e.sec52_4_eligible
            ),
            Decimal("0"),
        )
        return updated, _q1(cf_out), _q1(not_elig)

    # Proportional shares; last category absorbs rounding residue.
    allocated = Decimal("0")
    shares: dict[str, Decimal] = {}
    ordered = list(includable)
    for i, ev in enumerate(ordered):
        if i == len(ordered) - 1:
            take = _q1(allowed_for_categories - allocated)
        else:
            take = _q1(allowed_for_categories * ev.allowable / total_allowable)
            take = min(take, ev.allowable)
            allocated += take
        shares[ev.component_id] = min(take, ev.allowable)

    updated = []
    for ev in evals:
        if ev.component_id in shares:
            deducted = shares[ev.component_id]
            unded = _q1(max(Decimal("0"), ev.allowable - deducted))
        elif ev.include_in_sec52_aggregate:
            deducted = Decimal("0")
            unded = ev.allowable
        else:
            deducted = Decimal("0")
            unded = Decimal("0")
        eligible = is_sec52_4_eligible(ev.component_id, assessment_year)
        cf_amt = unded if eligible else Decimal("0")
        updated.append(
            replace(
                ev,
                deducted_this_year=_q1(deducted),
                undeducted_amount=_q1(unded),
                sec52_4_eligible=eligible,
                carry_forward_amount=_q1(cf_amt),
            )
        )

    cf_out = sum((e.carry_forward_amount for e in updated), Decimal("0"))
    not_elig = sum(
        (
            e.undeducted_amount
            for e in updated
            if e.include_in_sec52_aggregate and not e.sec52_4_eligible
        ),
        Decimal("0"),
    )
    return updated, _q1(cf_out), _q1(not_elig)
