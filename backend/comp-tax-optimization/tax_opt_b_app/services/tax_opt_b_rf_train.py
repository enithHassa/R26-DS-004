"""Offline training script — Random Forest tax predictor for 2025/26 assessment year.

Run from the repo root:
    python -m tax_opt_b_app.services.tax_opt_b_rf_train

Generates:
    models/tax-optimization/artifacts/rf_tax_2025_26.joblib
    models/tax-optimization/artifacts/rf_tax_2025_26_summary.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score

# Ensure project root on path when run as __main__
_REPO_ROOT = Path(__file__).resolve().parents[6]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tax_opt_b_app.config import component_settings
from tax_opt_b_app.services.tax_opt_b_compliance_engine import evaluate_compliance
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from tax_opt_b_app.services.tax_opt_b_tax_computation import compute_apit_liability
from tax_opt_b_app.tax_opt_b_schemas_profile_v1 import TaxOptBEmploymentTypeV1, TaxOptBProfileV1
from tax_opt_b_app.tax_opt_b_schemas_rf_tax_v1 import RF_FEATURE_NAMES, RF_FEATURE_VERSION
from tax_opt_b_app.tax_opt_b_schemas_strategy_v1 import TaxOptBReliefClaimV1, TaxOptBStrategyProposalV1

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TAX_YEAR = "2025_26"
N_SAMPLES = 25_000
RANDOM_SEED = 42
MODEL_ID = f"rf_tax_{TAX_YEAR}_v1"

_EMPLOYMENT_TYPES = list(TaxOptBEmploymentTypeV1)
_RELIEF_CODES = [
    "life_insurance_premium",
    "health_insurance_premium",
    "home_loan_interest",
    "rent_relief",
    "charitable_donations",
    "retirement_contribution",
]
_RELIEF_FIELD_MAP = {
    "life_insurance_premium": "relief_life_insurance_premium",
    "health_insurance_premium": "relief_health_insurance_premium",
    "home_loan_interest": "relief_home_loan_interest",
    "rent_relief": "relief_rent",
    "charitable_donations": "relief_charitable_donations",
    "retirement_contribution": "relief_retirement_contribution",
}


def _employment_code(et: TaxOptBEmploymentTypeV1) -> int:
    return _EMPLOYMENT_TYPES.index(et)


def _generate_synthetic_row(rng: np.random.Generator) -> dict:
    """Draw one random financial profile."""
    salary = float(np.clip(rng.lognormal(mean=13.5, sigma=1.2), 0, 12_000_000))
    business = float(np.clip(rng.lognormal(mean=12.5, sigma=1.5), 0, 8_000_000)) if rng.random() < 0.4 else 0.0
    investment = float(np.clip(rng.lognormal(mean=11.5, sigma=1.3), 0, 5_000_000)) if rng.random() < 0.3 else 0.0
    other = float(np.clip(rng.lognormal(mean=10.5, sigma=1.0), 0, 2_000_000)) if rng.random() < 0.2 else 0.0

    reliefs: dict[str, float] = {}
    for code in _RELIEF_CODES:
        # ~60% chance of claiming, random amount up to 600k
        reliefs[code] = float(rng.uniform(0, 600_000)) if rng.random() < 0.6 else 0.0

    dependents = int(rng.integers(0, 6))
    emp_type = rng.choice(_EMPLOYMENT_TYPES)

    return {
        "salary": salary,
        "business": business,
        "investment": investment,
        "other": other,
        "reliefs": reliefs,
        "dependents": dependents,
        "employment_type": emp_type,
    }


def _compute_label(row: dict, pack) -> float | None:
    """Run the deterministic engine to get the true tax for this profile."""
    gross = row["salary"] + row["business"] + row["investment"] + row["other"]
    profile = TaxOptBProfileV1(
        tax_year=TAX_YEAR,
        employment_type=row["employment_type"],
        dependents=row["dependents"],
        annual_gross_income=Decimal(str(round(gross))),
    )
    claims = [
        TaxOptBReliefClaimV1(
            relief_code=code,
            claimed_amount_annual=Decimal(str(round(amount))),
        )
        for code, amount in row["reliefs"].items()
        if amount > 0
    ]
    strategy = TaxOptBStrategyProposalV1(claims=claims)
    compliance = evaluate_compliance(profile, strategy, pack=pack)
    if not compliance.passed:
        # Still compute tax with empty relief if compliance fails (edge case)
        compliance_empty = evaluate_compliance(profile, TaxOptBStrategyProposalV1(claims=[]), pack=pack)
        if not compliance_empty.passed:
            return None
        tax = compute_apit_liability(profile=profile, applied_relief=compliance_empty.applied_relief, pack=pack)
    else:
        tax = compute_apit_liability(profile=profile, applied_relief=compliance.applied_relief, pack=pack)
    return float(tax.total_tax)


def _build_feature_vector(row: dict) -> list[float]:
    salary = row["salary"]
    business = row["business"]
    investment = row["investment"]
    other = row["other"]
    gross = salary + business + investment + other
    total_relief = sum(row["reliefs"].values())

    return [
        salary,
        business,
        investment,
        other,
        float(row["dependents"]),
        float(_employment_code(row["employment_type"])),
        row["reliefs"].get("life_insurance_premium", 0.0),
        row["reliefs"].get("health_insurance_premium", 0.0),
        row["reliefs"].get("home_loan_interest", 0.0),
        row["reliefs"].get("rent_relief", 0.0),
        row["reliefs"].get("charitable_donations", 0.0),
        row["reliefs"].get("retirement_contribution", 0.0),
        gross,
        total_relief,
    ]


def generate_dataset(pack, n: int = N_SAMPLES) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(RANDOM_SEED)
    X_rows: list[list[float]] = []
    y_rows: list[float] = []
    skipped = 0

    logger.info("Generating %d synthetic samples…", n)
    attempts = 0
    while len(X_rows) < n:
        attempts += 1
        row = _generate_synthetic_row(rng)
        label = _compute_label(row, pack)
        if label is None:
            skipped += 1
            continue
        X_rows.append(_build_feature_vector(row))
        y_rows.append(label)
        if len(X_rows) % 5_000 == 0:
            logger.info("  %d / %d rows generated (attempts=%d, skipped=%d)", len(X_rows), n, attempts, skipped)

    logger.info("Dataset complete: %d rows, %d skipped out of %d attempts", n, skipped, attempts)
    return np.array(X_rows, dtype=np.float64), np.array(y_rows, dtype=np.float64)


def train(X: np.ndarray, y: np.ndarray) -> RandomForestRegressor:
    logger.info("Training RandomForestRegressor(n_estimators=200) on %d samples…", len(X))
    model = RandomForestRegressor(n_estimators=200, n_jobs=-1, random_state=RANDOM_SEED)
    scores = cross_val_score(model, X, y, cv=5, scoring="r2")
    logger.info("5-fold CV R² scores: %s  mean=%.4f", scores.round(4), scores.mean())
    model.fit(X, y)
    logger.info("Training complete.")
    return model


def save_artifacts(model: RandomForestRegressor, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib_path = output_dir / "rf_tax_2025_26.joblib"
    joblib.dump(model, joblib_path)

    sha256 = hashlib.sha256(joblib_path.read_bytes()).hexdigest()

    summary = {
        "model_id": MODEL_ID,
        "feature_version": RF_FEATURE_VERSION,
        "feature_names": list(RF_FEATURE_NAMES),
        "training_timestamp": datetime.now(UTC).isoformat(),
        "n_training_rows": N_SAMPLES,
        "tax_year": TAX_YEAR,
        "estimator_joblib": "rf_tax_2025_26.joblib",
        "artifact_sha256": sha256,
        "model_type": "RandomForestRegressor",
        "n_estimators": 200,
    }
    summary_path = output_dir / "rf_tax_2025_26_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Saved model  → %s", joblib_path)
    logger.info("Saved summary → %s", summary_path)
    logger.info("SHA-256: %s", sha256)


if __name__ == "__main__":
    rules_path = component_settings.COMP_OPTIMIZATION_RULES_PATH
    logger.info("Loading rules from %s", rules_path)
    pack = load_tax_opt_b_rules(rules_path)

    X, y = generate_dataset(pack, N_SAMPLES)
    model = train(X, y)

    output_dir = component_settings.COMP_ML_ARTIFACTS_PATH
    save_artifacts(model, output_dir)
    logger.info("Done.")
