"""Export real backend data into the CSV shape the training scripts expect.

`scripts/train_phase4_ranking_adoption.py` currently derives its adoption
labels synthetically (rules-engine eligibility, or a legacy matcher's
predicted probability) because no real outcome data existed. Now that
`recommendation_feedback` and `behavioural_answers` are populated by the
taxpayer/auditor UIs (see `app/services/feedback_service.py` and
`app/services/behavioural_answer_service.py`), this script turns that real
data into a training CSV with real `adopted__<STRATEGY_CODE>` label columns.

Only profiles with at least one recorded piece of feedback are exported by
default, since a profile with no feedback contributes no real label signal —
use `--include-unlabelled` to also export those (useful for inspecting
feature coverage before enough feedback accumulates).

Known limitations (not fabricated, flagged deliberately):
- A strategy the profile was shown but never gave feedback on is written as
  `adopted__<code>=0` (implicit negative), matching this codebase's existing
  convention of treating "not confirmed positive" as 0 — it is not a claim
  that the user explicitly rejected it.
- `archetype` and `province` are synthetic-only concepts with no real-data
  equivalent here (`FinancialProfile` has `district`, not `province`, and no
  behavioural archetype) — both are written as the literal string "unknown",
  matching the training scripts' own fallback for missing categoricals,
  rather than guessing a value.
- `full_name` and the synthetic CSV's `password` column are intentionally
  never written here — this pulls from a database of live user profiles
  captured via profile creation, not the synthetic generator's fake
  identities.

Usage:
    .venv-backend/bin/python scripts/export_training_data.py \
      --out data/exports/real_training_data.csv [--include-unlabelled]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "comp-personalized-recommendation"))

from app.models.profile import FinancialProfile as FinancialProfileORM  # noqa: E402
from app.models.recommendation import Recommendation as RecommendationORM  # noqa: E402
from app.models.recommendation import RecommendationItem as RecommendationItemORM  # noqa: E402
from app.models.recommendation_feedback import (  # noqa: E402
    RecommendationFeedback as RecommendationFeedbackORM,
)
from app.models.strategy import TaxStrategy as TaxStrategyORM  # noqa: E402
from app.services.profile_service import compute_derived_features  # noqa: E402
from backend.shared.config.database import SessionLocal  # noqa: E402

# Same feature names `train_phase4_ranking_adoption.py` reads from a CSV row
# (see `row_to_eval_context` / `row_to_user_dict` in that script).
NUM_COLUMNS = [
    "dependents", "years_employed", "gross_monthly_income_lkr", "monthly_expenses_lkr",
    "monthly_debt_service_lkr", "liquid_savings_lkr", "existing_investments_lkr",
    "total_debt_lkr", "epf_balance_lkr", "etf_balance_lkr",
    "life_insurance_premium_annual_lkr", "home_loan_interest_annual_lkr",
    "donations_annual_lkr", "gross_annual_taxable_income_lkr", "baseline_tax_liability_lkr",
    "effective_tax_rate", "disposable_income_monthly_lkr", "savings_rate", "debt_to_income",
]
CAT_COLUMNS = ["gender", "marital_status", "occupation", "risk_tolerance", "archetype", "age_band", "province"]
OTHER_COLUMNS = ["profile_id", "health_insurance", "income_sources_json", "tax_year"]


def _age_band(age: int) -> str:
    lo = max(18, (age // 5) * 5)
    hi = lo + 4
    return f"{lo}-{hi}"


def _profile_to_row(profile: FinancialProfileORM) -> dict:
    derived = compute_derived_features(profile)
    age = derived.age_years
    return {
        "profile_id": str(profile.id),
        "gender": profile.gender,
        "marital_status": profile.marital_status,
        "occupation": profile.occupation,
        "risk_tolerance": profile.risk_tolerance,
        "archetype": "unknown",
        "age_band": _age_band(age),
        "province": "unknown",
        "dependents": profile.dependents,
        "years_employed": profile.years_employed,
        "gross_monthly_income_lkr": float(profile.gross_monthly_income),
        "monthly_expenses_lkr": float(profile.monthly_expenses),
        "monthly_debt_service_lkr": float(profile.monthly_debt_service),
        "liquid_savings_lkr": float(profile.liquid_savings),
        "existing_investments_lkr": float(profile.existing_investments),
        "total_debt_lkr": float(profile.total_debt),
        "epf_balance_lkr": float(profile.epf_balance),
        "etf_balance_lkr": float(profile.etf_balance),
        "health_insurance": bool(profile.health_insurance),
        "life_insurance_premium_annual_lkr": float(profile.life_insurance_premium_annual),
        "home_loan_interest_annual_lkr": float(profile.home_loan_interest_annual),
        "donations_annual_lkr": float(profile.donations_annual),
        "income_sources_json": _income_sources_json(profile),
        "tax_year": profile.tax_year,
        "gross_annual_taxable_income_lkr": float(derived.gross_annual_taxable_income),
        "baseline_tax_liability_lkr": float(derived.baseline_tax_liability_annual),
        "effective_tax_rate": derived.effective_tax_rate,
        "disposable_income_monthly_lkr": float(derived.disposable_income_monthly),
        "savings_rate": derived.savings_rate,
        "debt_to_income": derived.debt_to_income,
    }


def _income_sources_json(profile: FinancialProfileORM) -> str:
    import json

    return json.dumps(profile.income_sources or [])


def export(out_path: Path, include_unlabelled: bool) -> int:
    db = SessionLocal()
    try:
        profiles = db.query(FinancialProfileORM).all()

        # code -> {profile_id: accepted} using the most recent feedback per
        # (profile, strategy) pair.
        feedback_rows = (
            db.query(
                RecommendationORM.profile_id,
                TaxStrategyORM.code,
                RecommendationFeedbackORM.accepted,
                RecommendationFeedbackORM.created_at,
            )
            .join(RecommendationItemORM, RecommendationItemORM.recommendation_id == RecommendationORM.id)
            .join(TaxStrategyORM, TaxStrategyORM.id == RecommendationItemORM.strategy_id)
            .join(
                RecommendationFeedbackORM,
                RecommendationFeedbackORM.recommendation_item_id == RecommendationItemORM.id,
            )
            .all()
        )

        feedback_by_profile: dict = {}
        latest_at: dict = {}
        strategy_codes: set[str] = set()
        for profile_id, code, accepted, created_at in feedback_rows:
            strategy_codes.add(code)
            key = (profile_id, code)
            if key not in latest_at or created_at > latest_at[key]:
                latest_at[key] = created_at
                feedback_by_profile.setdefault(profile_id, {})[code] = accepted

        label_columns = [f"adopted__{code}" for code in sorted(strategy_codes)]
        fieldnames = ["profile_id"] + OTHER_COLUMNS[1:] + CAT_COLUMNS + NUM_COLUMNS + label_columns

        out_path.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for profile in profiles:
                profile_feedback = feedback_by_profile.get(profile.id)
                if not profile_feedback and not include_unlabelled:
                    continue
                row = _profile_to_row(profile)
                for code in sorted(strategy_codes):
                    row[f"adopted__{code}"] = int((profile_feedback or {}).get(code, False))
                writer.writerow(row)
                written += 1
        return written
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Output CSV path")
    parser.add_argument(
        "--include-unlabelled",
        action="store_true",
        help="Also export profiles with no recorded feedback (all adopted__* columns will be 0)",
    )
    args = parser.parse_args()

    count = export(args.out, args.include_unlabelled)
    print(f"Wrote {count} rows to {args.out}")


if __name__ == "__main__":
    main()
