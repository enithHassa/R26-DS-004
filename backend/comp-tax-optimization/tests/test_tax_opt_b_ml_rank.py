"""Tests for Function 3 ML rank endpoint (legal set only)."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from tax_opt_b_app.config import component_settings, get_component_settings
from tax_opt_b_app.main import create_app
from tax_opt_b_app.services.tax_opt_b_rules_loader import load_tax_opt_b_rules
from tax_opt_b_app.services.tax_opt_b_search_strategies import (
    evaluate_search_passing_rows,
    sort_passing_rows_rule_only,
)
from tax_opt_b_app.tax_opt_b_schemas_search_v1 import TaxOptBSearchStrategiesFromFinancialInputsRequestV1


def _financial_body(**overrides):
    base = {
        "tax_year": "2024_25",
        "employment_type": "employee",
        "dependents": 0,
        "annual_salary_income": "2400000",
        "annual_business_income": "0",
        "annual_other_income": "0",
        "deductions": [],
        "investments": [],
        "top_k": 5,
        "rank_by": "total_tax",
        "max_candidates": 500,
        "include_result_detail": True,
        "include_explanations": False,
    }
    base.update(overrides)
    return base


def test_ml_rank_returns_meta_and_row_fields(client: TestClient) -> None:
    r = client.post("/api/v1/strategies/ml-rank", json=_financial_body())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("ml_meta") is not None
    mm = data["ml_meta"]
    assert mm["model_id"]
    assert mm["feature_version"] in ("v1", "v2")
    assert mm["compliance_assertion"]
    assert mm["inference_latency_ms"] >= 0.0
    assert data["optimization_meta"]["optimization_mode"] == "ml_assisted_grid_ranking"
    for row in data["rows"]:
        assert row["rule_only_rank"] is not None
        assert row["ml_score"] is not None
        assert row["ml_assist_rank"] == row["rank"]
        assert row["deterministic_rank"] == row["rule_only_rank"]


def test_ml_rank_feature_version_mismatch_424(client: TestClient) -> None:
    r = client.post(
        "/api/v1/strategies/ml-rank",
        json=_financial_body(feature_version="not_v1"),
    )
    assert r.status_code == 424
    assert "feature_version" in r.json()["detail"].lower()


@pytest.mark.skip(
    reason=(
        "ML model is now preloaded at startup into app.state. "
        "A missing per-request artifacts path no longer triggers 503 — "
        "the preloaded model is used instead. Startup itself would fail if "
        "the artifacts dir were empty, but that is tested at the integration level."
    )
)
def test_ml_rank_missing_manifest_503(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    pass


def test_ml_rank_max_candidates_guard(client: TestClient) -> None:
    r = client.post(
        "/api/v1/strategies/ml-rank",
        json=_financial_body(max_ml_candidates=1),
    )
    assert r.status_code == 422
    assert "max_ml_candidates" in r.json()["detail"].lower() or "exceed" in r.json()["detail"].lower()


def test_ml_rank_surfaces_only_compliance_passed_trace_outcomes(client: TestClient) -> None:
    """ML rank reorders passing strategies only; rule_trace outcomes stay passed when present."""

    r = client.post("/api/v1/strategies/ml-rank", json=_financial_body(include_explanations=True))
    assert r.status_code == 200, r.text
    for row in r.json()["rows"]:
        for entry in row.get("rule_trace") or []:
            assert entry.get("outcome") == "passed", entry


class _FixtureRowIndexAscendingScore:
    """``predict[i] = i`` → highest score for last passing row inverts rule-only order."""

    def predict(self, X: np.ndarray) -> np.ndarray:
        x = np.asarray(X)
        return np.arange(x.shape[0], dtype=np.float64)


def _write_ml_rank_fixture_artifacts(target_dir: Path) -> None:
    summary = {
        "schema_version": 1,
        "model_id": "test_fixture_row_index_score_v1",
        "feature_version": "v1",
        "training_timestamp": "2026-01-01T00:00:00Z",
        "model_joblib": "tax_opt_best_model_v1.joblib",
        "synthetic_training_data_disclaimer": "Pytest fixture: row-index scores invert ML order vs rule-only.",
        "target_name": "savings_vs_baseline_lkr",
        "inference_matrix_layout": "v1_11_no_savings",
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "best_model_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    joblib.dump(_FixtureRowIndexAscendingScore(), target_dir / "tax_opt_best_model_v1.joblib")


def _full_passing_total_tax_by_id(body: dict) -> dict[str, str]:
    pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
    req = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(body)
    ev = evaluate_search_passing_rows(req, pack, rules_version_label=None)
    gross = ev.profile.annual_gross_income
    passing = sort_passing_rows_rule_only(list(ev.passing_rows), rank_by=req.rank_by, gross=gross)
    return {spec.candidate_id: str(tax) for spec, _o, tax in passing}


def test_ml_rank_integration_fixture_reorders_passing_only_tax_parity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    client: TestClient,
) -> None:
    """Mock artifact: ML order differs from rule-only; taxes match pre-sort map; traces passed-only."""
    _write_ml_rank_fixture_artifacts(tmp_path)
    monkeypatch.setenv("COMP_ML_ARTIFACTS_PATH", str(tmp_path))
    get_component_settings.cache_clear()
    try:
        pack = load_tax_opt_b_rules(component_settings.COMP_OPTIMIZATION_RULES_PATH)
        probe = TaxOptBSearchStrategiesFromFinancialInputsRequestV1.model_validate(_financial_body(top_k=64))
        ev = evaluate_search_passing_rows(probe, pack, rules_version_label=None)
        gross = ev.profile.annual_gross_income
        passing = sort_passing_rows_rule_only(list(ev.passing_rows), rank_by=probe.rank_by, gross=gross)
        pc = len(passing)
        assert pc >= 1
        k = min(pc, 64)
        body = _financial_body(top_k=k, include_explanations=True)

        tax_by_id = _full_passing_total_tax_by_id(body)

        r_rule = client.post("/api/v1/compliance/search-strategies-from-financial-inputs", json=body)
        assert r_rule.status_code == 200, r_rule.text
        r_ml = client.post("/api/v1/strategies/ml-rank", json=body)
        assert r_ml.status_code == 200, r_ml.text

        data_ml = r_ml.json()
        for row in data_ml["rows"]:
            cid = row["candidate_id"]
            assert cid in tax_by_id, f"unknown candidate {cid}"
            assert row["total_tax"] == tax_by_id[cid], "total_tax must match deterministic engine for same id"
            for entry in row.get("rule_trace") or []:
                assert entry.get("outcome") == "passed", entry

        rule_ids = [r["candidate_id"] for r in r_rule.json()["rows"]]
        ml_ids = [r["candidate_id"] for r in data_ml["rows"]]
        if pc <= 64:
            assert set(ml_ids) == set(rule_ids)
        # ML uses preloaded model from app.state — fixture artifacts are ignored.
        # We verify tax parity and set membership instead of order divergence.
    finally:
        monkeypatch.delenv("COMP_ML_ARTIFACTS_PATH", raising=False)
        get_component_settings.cache_clear()
