"""Human-readable labels and tier blurbs for FR5 template explanations (still deterministic)."""

from __future__ import annotations

from typing import Literal

ExplanationDetail = Literal["summary", "detailed"]

# MVP relief codes — extend when rules pack adds codes.
RELIEF_DISPLAY_LABELS: dict[str, str] = {
    "life_insurance_premium": "Life insurance premiums",
    "health_insurance_premium": "Health insurance premiums",
    "home_loan_interest": "Housing loan interest",
    "rent_relief": "Rent relief",
    "charitable_donations": "Charitable donations",
    "retirement_contribution": "Approved retirement / pension contributions",
}


def relief_display_name(relief_code: str) -> str:
    code = (relief_code or "").strip()
    if not code:
        return relief_code or ""
    return RELIEF_DISPLAY_LABELS.get(code, code.replace("_", " ").title())


def narrative_tier_blurb_compute(detail: ExplanationDetail) -> str:
    if detail == "summary":
        return (
            "Summary narrative — amounts match the engine; progressive tax bands are rolled into a single line "
            "below. Pick detailed to see each slab step and fuller relief breakdowns."
        )
    return (
        "Detailed narrative — each progressive tax band is listed, reliefs show claimed vs cap vs allowed, "
        "and compliance issues cite rule ids (with references where provided)."
    )


def narrative_tier_blurb_compare(detail: ExplanationDetail) -> str:
    if detail == "summary":
        return (
            "Summary comparison — scenario ranking and deltas are in plain numbers; "
            "per-scenario tax walk-throughs stay compact."
        )
    return (
        "Detailed comparison — adds taxable basis hints per passing scenario and a dedicated section "
        "for failed variants when any exist."
    )


__all__ = [
    "ExplanationDetail",
    "RELIEF_DISPLAY_LABELS",
    "narrative_tier_blurb_compare",
    "narrative_tier_blurb_compute",
    "relief_display_name",
]
