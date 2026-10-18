#!/usr/bin/env python3
"""Generate a synthetic 40-taxpayer OE Engine kappa label set.

Not real taxpayer data — a demo / proxy panel set with intentional,
explainable disagreements (film minimum, solar over-claim, cinema, etc.).
"""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # models/opt-explain-engine
OUT = ROOT / "evaluation" / "fixtures" / "kappa_40_taxpayers.csv"

YA = "2025_26"

# Persona archetypes cycle across 40 users so disagreements are patterned, not random.
# Each row after personal: (compare_group_id, display_name, system, expert, note)
ARCHETYPES: list[list[tuple[str, str, str, str, str]]] = [
    # 0 — salary + solar OK; film spend too low (system wrongly claims)
    [
        ("solar_panel_relief", "Solar panel relief", "claim", "claim", "has solar spend"),
        (
            "qp_film_production",
            "Expenditure on film production",
            "claim",
            "do_not_claim",
            "system ignored 5M minimum; expert rejects",
        ),
        ("donation_to_charitable_institution", "Charitable donations", "claim", "claim", ""),
    ],
    # 1 — rents + solar; expert still wants solar when system skipped
    [
        ("rental_income_relief", "Rental income relief", "claim", "claim", "has rental income"),
        (
            "solar_panel_relief",
            "Solar panel relief",
            "do_not_claim",
            "claim",
            "expert: qualifying solar present; system missed",
        ),
        ("qp_cinema_construction", "Cinema construction", "do_not_claim", "do_not_claim", "no cinema spend"),
    ],
    # 2 — senior citizen path; cinema over-claim by system
    [
        (
            "senior_citizen_interest_income_relief",
            "Senior citizen interest",
            "claim",
            "claim",
            "age 60+ with interest",
        ),
        (
            "qp_cinema_construction",
            "Cinema construction",
            "claim",
            "do_not_claim",
            "system applied small outlay; expert: not a new cinema",
        ),
        ("donation_to_charitable_institution", "Charitable donations", "do_not_claim", "do_not_claim", ""),
    ],
    # 3 — clean agreement set
    [
        ("solar_panel_relief", "Solar panel relief", "claim", "claim", ""),
        ("rental_income_relief", "Rental income relief", "do_not_claim", "do_not_claim", "no rents"),
        (
            "qp_film_production",
            "Expenditure on film production",
            "claim",
            "claim",
            "spend >= 5M — both claim",
        ),
    ],
    # 4 — system over-claims solar without evidence
    [
        (
            "solar_panel_relief",
            "Solar panel relief",
            "claim",
            "do_not_claim",
            "system over-claimed; no invoice",
        ),
        ("donation_to_charitable_institution", "Charitable donations", "claim", "claim", ""),
        ("rental_income_relief", "Rental income relief", "claim", "claim", ""),
    ],
    # 5 — film correctly rejected by both; donation mismatch
    [
        (
            "qp_film_production",
            "Expenditure on film production",
            "do_not_claim",
            "do_not_claim",
            "below 5M — both reject",
        ),
        (
            "donation_to_charitable_institution",
            "Charitable donations",
            "do_not_claim",
            "claim",
            "expert accepts approved charity receipt",
        ),
        ("solar_panel_relief", "Solar panel relief", "do_not_claim", "do_not_claim", ""),
    ],
    # 6 — business-heavy; cinema genuine claim
    [
        ("qp_cinema_construction", "Cinema construction", "claim", "claim", "new cinema within 25M cap"),
        ("solar_panel_relief", "Solar panel relief", "claim", "claim", ""),
        (
            "senior_citizen_interest_income_relief",
            "Senior citizen interest",
            "claim",
            "do_not_claim",
            "system used wrong age; under 60",
        ),
    ],
    # 7 — mostly agree, one film edge case where expert is stricter
    [
        ("rental_income_relief", "Rental income relief", "claim", "claim", ""),
        (
            "qp_film_production",
            "Expenditure on film production",
            "claim",
            "do_not_claim",
            "promotional only; expert says incomplete film cost",
        ),
        ("donation_to_charitable_institution", "Charitable donations", "claim", "claim", ""),
    ],
]


def main() -> None:
    rows: list[dict[str, str]] = []
    case_id = 1
    for i in range(1, 41):
        pid = f"Taxpayer_{i:04d}"
        # Personal relief — always claim / claim (statutory)
        rows.append(
            {
                "case_id": str(case_id),
                "profile_id": pid,
                "assessment_year": YA,
                "compare_group_id": "personal_relief",
                "display_name": "Personal Relief",
                "system_label": "claim",
                "expert_label": "claim",
                "notes": "auto statutory — both claim",
            }
        )
        case_id += 1

        for group, name, sys_lab, exp_lab, note in ARCHETYPES[(i - 1) % len(ARCHETYPES)]:
            rows.append(
                {
                    "case_id": str(case_id),
                    "profile_id": pid,
                    "assessment_year": YA,
                    "compare_group_id": group,
                    "display_name": name,
                    "system_label": sys_lab,
                    "expert_label": exp_lab,
                    "notes": note,
                }
            )
            case_id += 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "profile_id",
                "assessment_year",
                "compare_group_id",
                "display_name",
                "system_label",
                "expert_label",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    disagree = sum(1 for r in rows if r["system_label"] != r["expert_label"])
    print(f"Wrote {OUT}")
    print(f"Taxpayers: 40  pairs: {len(rows)}  disagreements: {disagree}")


if __name__ == "__main__":
    main()
