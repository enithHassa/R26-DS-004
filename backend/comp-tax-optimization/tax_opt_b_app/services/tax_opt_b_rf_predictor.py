"""RF tax predictor — load model artifact and run inference + SHAP for the 2025/26 calculator."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import shap

from tax_opt_b_app.tax_opt_b_schemas_rf_tax_v1 import (
    RF_FEATURE_NAMES,
    RF_FEATURE_VERSION,
    TaxOptBRfTaxPredictRequestV1,
)
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import (
    TaxOptBShapExplanationV1,
    TaxOptBShapFeatureContributionV1,
)

logger = logging.getLogger(__name__)

_EMPLOYMENT_ORDER = ["employee", "self_employed", "business_owner", "other"]


class RfModelBundle:
    """Holds the loaded estimator and its summary metadata."""

    def __init__(self, estimator: Any, summary: dict) -> None:
        self.estimator = estimator
        self.model_id: str = summary["model_id"]
        self.feature_version: str = summary["feature_version"]
        self.artifact_sha256: str = summary["artifact_sha256"]


def load_rf_bundle(artifacts_dir: Path) -> RfModelBundle:
    summary_path = artifacts_dir / "rf_tax_2025_26_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(
            f"RF model summary not found at {summary_path}. "
            "Run tax_opt_b_rf_train.py first to generate the model artifact."
        )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    joblib_path = artifacts_dir / summary["estimator_joblib"]
    if not joblib_path.exists():
        raise FileNotFoundError(f"RF model joblib not found at {joblib_path}.")

    # Checksum validation
    actual_sha = hashlib.sha256(joblib_path.read_bytes()).hexdigest()
    if actual_sha != summary["artifact_sha256"]:
        raise ValueError(
            f"RF model checksum mismatch. Expected {summary['artifact_sha256']}, got {actual_sha}. "
            "Re-run the training script."
        )

    estimator = joblib.load(joblib_path)
    logger.info("RF tax model loaded (model_id=%s, feature_version=%s)", summary["model_id"], summary["feature_version"])
    return RfModelBundle(estimator=estimator, summary=summary)


def _build_feature_vector(req: TaxOptBRfTaxPredictRequestV1) -> np.ndarray:
    salary = float(req.annual_salary_income)
    business = float(req.annual_business_income)
    investment = float(req.annual_investment_income)
    other = float(req.annual_other_income)
    gross = salary + business + investment + other

    emp_code = float(_EMPLOYMENT_ORDER.index(req.employment_type.value))

    reliefs = [
        float(req.relief_life_insurance_premium),
        float(req.relief_health_insurance_premium),
        float(req.relief_home_loan_interest),
        float(req.relief_rent),
        float(req.relief_charitable_donations),
        float(req.relief_retirement_contribution),
    ]
    total_relief = sum(reliefs)

    vector = [
        salary,
        business,
        investment,
        other,
        float(req.dependents),
        emp_code,
        *reliefs,
        gross,
        total_relief,
    ]
    return np.array([vector], dtype=np.float64)  # shape (1, 14)


def _compute_shap(estimator: Any, X: np.ndarray, predicted: float) -> TaxOptBShapExplanationV1:
    explainer = shap.TreeExplainer(estimator)
    shap_vals = explainer.shap_values(X)
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[0]
    shap_row = np.asarray(shap_vals, dtype=np.float64)[0]  # shape (n_features,)

    base_value = float(
        explainer.expected_value[0]
        if hasattr(explainer.expected_value, "__len__")
        else explainer.expected_value
    )

    contributions = [
        TaxOptBShapFeatureContributionV1(
            feature_name=name,
            shap_value=float(sv),
            feature_value=float(X[0, i]),
        )
        for i, (name, sv) in enumerate(zip(RF_FEATURE_NAMES, shap_row))
    ]
    contributions.sort(key=lambda c: abs(c.shap_value), reverse=True)

    return TaxOptBShapExplanationV1(
        base_value=base_value,
        predicted_value=predicted,
        feature_contributions=contributions,
        explainer_type="TreeExplainer",
        shap_version=shap.__version__,
    )


def predict_rf_tax(
    req: TaxOptBRfTaxPredictRequestV1,
    bundle: RfModelBundle,
) -> tuple[float, TaxOptBShapExplanationV1]:
    """Return ``(predicted_tax_lkr, shap_explanation)``."""
    if bundle.feature_version != RF_FEATURE_VERSION:
        raise ValueError(
            f"Feature version mismatch: model has '{bundle.feature_version}', "
            f"code expects '{RF_FEATURE_VERSION}'."
        )
    X = _build_feature_vector(req)
    raw = float(bundle.estimator.predict(X)[0])
    predicted_tax = max(0.0, round(raw))
    shap_explanation = _compute_shap(bundle.estimator, X, predicted_tax)
    return predicted_tax, shap_explanation


__all__ = ["RfModelBundle", "load_rf_bundle", "predict_rf_tax"]
