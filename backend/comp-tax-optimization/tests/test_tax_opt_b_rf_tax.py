"""Tests for the 2025/26 RF tax filing predict endpoint."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestRegressor

from tax_opt_b_app.tax_opt_b_schemas_rf_tax_v1 import RF_FEATURE_NAMES, RF_FEATURE_VERSION


def _rf_predict_body(**overrides: object) -> dict:
    base = {
        "tax_year": "2025_26",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2400000",
        "annual_business_income": "0",
        "annual_investment_income": "0",
        "annual_other_income": "0",
        "relief_life_insurance_premium": "50000",
        "relief_health_insurance_premium": "0",
        "relief_home_loan_interest": "0",
        "relief_rent": "0",
        "relief_charitable_donations": "0",
        "relief_retirement_contribution": "0",
    }
    base.update(overrides)
    return base


def _write_rf_fixture_artifacts(target_dir: Path) -> None:
    rng = np.random.default_rng(0)
    n_features = len(RF_FEATURE_NAMES)
    X = rng.uniform(0, 3_000_000, size=(32, n_features))
    y = rng.uniform(50_000, 500_000, size=32)
    model = RandomForestRegressor(n_estimators=5, random_state=0)
    model.fit(X, y)

    target_dir.mkdir(parents=True, exist_ok=True)
    joblib_path = target_dir / "rf_tax_2025_26.joblib"
    joblib.dump(model, joblib_path)
    sha256 = hashlib.sha256(joblib_path.read_bytes()).hexdigest()
    summary = {
        "model_id": "rf_tax_2025_26_test_fixture",
        "feature_version": RF_FEATURE_VERSION,
        "feature_names": list(RF_FEATURE_NAMES),
        "training_timestamp": "2026-01-01T00:00:00+00:00",
        "n_training_rows": 32,
        "tax_year": "2025_26",
        "estimator_joblib": "rf_tax_2025_26.joblib",
        "artifact_sha256": sha256,
        "model_type": "RandomForestRegressor",
        "n_estimators": 5,
    }
    (target_dir / "rf_tax_2025_26_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def test_rf_predict_happy_path_with_loaded_bundle(client: TestClient) -> None:
    r = client.post("/api/v1/tax-filing/rf-predict", json=_rf_predict_body())
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["predicted_tax_lkr"].isdigit()
    assert data["total_gross_income_lkr"] == "2400000"
    assert data["total_relief_claimed_lkr"] == "50000"
    assert data["model_id"]
    assert data["feature_version"] == RF_FEATURE_VERSION
    assert data["disclaimer"]

    shap_exp = data["shap_explanation"]
    assert shap_exp["explainer_type"] == "TreeExplainer"
    assert "base_value" in shap_exp
    assert "predicted_value" in shap_exp
    assert len(shap_exp["feature_contributions"]) == len(RF_FEATURE_NAMES)


def test_rf_predict_shap_structure_with_fixture_bundle(client: TestClient, tmp_path: Path) -> None:
    _write_rf_fixture_artifacts(tmp_path)
    from tax_opt_b_app.services.tax_opt_b_rf_predictor import load_rf_bundle

    client.app.state.rf_tax_bundle = load_rf_bundle(tmp_path)

    r = client.post("/api/v1/tax-filing/rf-predict", json=_rf_predict_body())
    assert r.status_code == 200, r.text
    shap_exp = r.json()["shap_explanation"]
    assert shap_exp["explainer_type"] == "TreeExplainer"
    assert len(shap_exp["feature_contributions"]) == len(RF_FEATURE_NAMES)
    for row in shap_exp["feature_contributions"]:
        assert row["feature_name"] in RF_FEATURE_NAMES
        assert isinstance(row["shap_value"], (int, float))
        assert isinstance(row["feature_value"], (int, float))


def test_rf_predict_503_when_bundle_missing(client: TestClient) -> None:
    client.app.state.rf_tax_bundle = None
    r = client.post("/api/v1/tax-filing/rf-predict", json=_rf_predict_body())
    assert r.status_code == 503, r.text
    assert "RF tax model not loaded" in r.json()["detail"]


def test_rf_predict_rejects_wrong_tax_year(client: TestClient) -> None:
    r = client.post("/api/v1/tax-filing/rf-predict", json=_rf_predict_body(tax_year="2024_25"))
    assert r.status_code == 422, r.text
    assert "2025_26" in r.json()["detail"]


def test_rf_predict_rejects_negative_income(client: TestClient) -> None:
    r = client.post(
        "/api/v1/tax-filing/rf-predict",
        json=_rf_predict_body(annual_salary_income="-1"),
    )
    assert r.status_code == 422, r.text
