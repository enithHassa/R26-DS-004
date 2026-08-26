"""Health and empty-catalog probes for Phase 1."""

from __future__ import annotations


def test_health_root(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["component"] == "optimization-explainable-engine"
    assert payload["phase"] == "7"


def test_ready(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["api_bootstrap"] is True
    assert payload["checks"]["chunk_coverage"] is True
    assert payload["checks"]["promoted_without_chunks"] == []


def test_health_api_v1(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["component"] == "optimization-explainable-engine"


def test_years_empty(client) -> None:
    response = client.get("/years")
    assert response.status_code == 200
    payload = response.json()
    assert payload["assessment_years"] == []
    assert payload["year_count"] == 0


def test_years_empty_api_v1(client) -> None:
    response = client.get("/api/v1/years")
    assert response.status_code == 200
    assert response.json()["year_count"] == 0


def test_acts_empty(client) -> None:
    response = client.get("/acts/2025_26")
    assert response.status_code == 200
    assert response.json()["act_count"] == 0


def test_reliefs_empty(client) -> None:
    response = client.get("/reliefs/2025_26")
    assert response.status_code == 200
    assert response.json()["entry_count"] == 0


def test_rates_empty(client) -> None:
    response = client.get("/rates/2025_26")
    assert response.status_code == 200
    assert response.json()["band_count"] == 0


def test_compare_empty(client) -> None:
    response = client.get("/compare")
    assert response.status_code == 200
    payload = response.json()
    assert payload["assessment_years"] == []
    assert payload["group_count"] == 0


def test_calculate_404_until_promoted(client) -> None:
    response = client.post(
        "/calculate",
        json={
            "assessment_year": "2025_26",
            "income": {
                "employment": 0,
                "business": 0,
                "investment": 0,
                "other": 0,
                "interest": 0,
                "rents": 0,
            },
            "claims": [],
        },
    )
    assert response.status_code == 404


def test_explain_404_until_promoted(client) -> None:
    response = client.post(
        "/explain",
        json={
            "assessment_year": "2025_26",
            "income": {
                "employment": 0,
                "business": 0,
                "investment": 0,
                "other": 0,
                "interest": 0,
                "rents": 0,
            },
            "claims": [],
        },
    )
    assert response.status_code == 404


def test_retrieve_empty_query_ok(client, monkeypatch) -> None:
    monkeypatch.setattr("oe_engine_app.routers.retrieve._query_embedding", lambda _q: None)
    response = client.get("/retrieve", params={"q": "solar panels"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "solar panels"
    assert "hits" in payload
