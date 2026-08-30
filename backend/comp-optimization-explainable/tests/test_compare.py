"""Phase 8 — cross-year compare from RAG + regression locks."""

from __future__ import annotations

from unittest.mock import patch

from opt_explain_app.config import get_oe_settings
from opt_explain_app.services.explain import explain_from_calculation

TYPICAL_INCOME = {
    "employment": 1_800_000,
    "business": 0,
    "investment": 2_000_000,
    "other": 0,
    "interest": 2_000_000,
    "rents": 0,
}


def _personal_series(series: list[dict]) -> dict[str, str | None]:
    return {row["assessment_year"]: row.get("cap_amount") for row in series}


def test_compare_lists_years_from_rag_not_hardcoded(client) -> None:
    client.post("/api/v1/index/refresh")
    response = client.get("/api/v1/compare")
    assert response.status_code == 200
    body = response.json()
    years = body["assessment_years"]
    assert "2018_19" in years
    assert "2025_26" in years
    assert "2026_27" not in years
    assert years == sorted(years, key=lambda ya: ya.split("_"))
    assert body["group_count"] >= 1
    assert any(g["compare_group_id"] == "personal_relief" for g in body["groups"])


def test_compare_personal_relief_caps_across_years(client) -> None:
    """Checkpoint: personal relief 500k → … → 1.8M across indexed years."""
    client.post("/api/v1/index/refresh")
    response = client.get(
        "/api/v1/compare",
        params={"compare_group_id": "personal_relief"},
    )
    assert response.status_code == 200
    body = response.json()
    caps = _personal_series(body["series"])
    assert caps["2018_19"] == "500000"
    assert caps["2019_20"] == "500000"
    assert caps["2020_21"] == "3000000"
    assert caps["2021_22"] == "3000000"
    assert caps["2022_23"] == "2250000"
    assert caps["2023_24"] == "1200000"
    assert caps["2024_25"] == "1200000"
    assert caps["2025_26"] == "1800000"
    assert caps["2018_19"] != caps["2025_26"]


def test_compare_exclude_act_falls_back_personal_cap(client) -> None:
    client.post("/api/v1/index/refresh")
    included = client.get(
        "/api/v1/compare",
        params={"compare_group_id": "personal_relief"},
    ).json()
    assert _personal_series(included["series"])["2025_26"] == "1800000"

    excluded = client.get(
        "/api/v1/compare",
        params={
            "compare_group_id": "personal_relief",
            "exclude_source_doc_id": "ird-amend-2025-02",
        },
    )
    assert excluded.status_code == 200
    caps = _personal_series(excluded.json()["series"])
    assert caps["2025_26"] == "1200000"
    assert excluded.json()["exclude_source_doc_id"] == "ird-amend-2025-02"


def test_compare_group_filter_limits_year_entries(client) -> None:
    client.post("/api/v1/index/refresh")
    all_groups = client.get("/api/v1/compare").json()
    filtered = client.get(
        "/api/v1/compare",
        params={"compare_group_id": "personal_relief"},
    ).json()
    for bucket in filtered["years"]:
        assert bucket["entry_count"] <= 1
        for entry in bucket["entries"]:
            assert entry["compare_group_id"] == "personal_relief"
    assert filtered["compare_group_id"] == "personal_relief"
    assert filtered["group_count"] == all_groups["group_count"]


def test_calculate_uses_rag_slabs_regression(client) -> None:
    client.post("/api/v1/index/refresh")
    response = client.post(
        "/api/v1/calculate",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tax_payable"] == 270_000
    assert body["slab_lines"][0]["rate_percent"] == 6.0


def test_unpublished_questions_hidden_from_reliefs_regression(client, tmp_path) -> None:
    from opt_explain_app.config import OptimizationExplainableSettings
    from opt_explain_app.services import rag_index

    approved = tmp_path / "approved"
    rates = tmp_path / "rates"
    index = tmp_path / "index"
    approved.mkdir()
    rates.mkdir()
    (approved / "2025_26.json").write_text(
        __import__("json").dumps(
            {
                "assessment_year": "2025_26",
                "entries": [
                    {
                        "entry_id": "live-only",
                        "compare_group_id": "personal_relief",
                        "display_name": "Personal relief",
                        "question_prompt": "Published question.",
                        "input_kind": "notice",
                        "auto_applied": True,
                        "cap_amount": "1800000",
                        "unit": "lkr",
                        "engine_binding": {"kind": "none"},
                        "act_name": "Act",
                        "section_ref": "Fifth Schedule",
                        "quote": "Rs. 1,800,000",
                        "source_doc_id": "ird-amend-2025-02",
                        "sort_order": 10,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    cfg = OptimizationExplainableSettings(
        COMP_OPTIMIZATION_EXPLAINABLE_APPROVED_DIR=str(approved),
        COMP_OPTIMIZATION_EXPLAINABLE_RATES_DIR=str(rates),
        COMP_OPTIMIZATION_EXPLAINABLE_INDEX_DIR=str(index),
    )
    try:
        rag_index.refresh_index(cfg)
        reliefs = client.get("/api/v1/reliefs/2025_26").json()["entries"]
        prompts = {e["question_prompt"] for e in reliefs}
        assert "Published question." in prompts
        assert "Secret draft question" not in prompts
        assert all(e["entry_id"] != "rejected-draft" for e in reliefs)
    finally:
        rag_index.refresh_index()


def test_explain_cannot_change_engine_amounts_regression(client, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    get_oe_settings.cache_clear()
    client.post("/api/v1/index/refresh")

    calc = client.post(
        "/api/v1/calculate",
        json={"assessment_year": "2025_26", "income": TYPICAL_INCOME, "claims": []},
    ).json()

    def fake_complete(user_prompt: str, settings) -> dict:
        return {
            "narrative": "Tax payable is 9,999,999 LKR in this sentence.",
            "cited_sections": ["Fifth Schedule"],
        }

    with patch("opt_explain_app.services.explain._complete_openai", side_effect=fake_complete):
        explained = explain_from_calculation(calc)

    get_oe_settings.cache_clear()
    assert explained["tax_payable"] == calc["tax_payable"] == 270_000
    assert explained["tax_payable"] != 9_999_999
