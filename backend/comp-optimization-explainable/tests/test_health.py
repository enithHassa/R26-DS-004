"""Health probe tests."""

from __future__ import annotations


def test_health_root(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["component"] == "optimization-explainable"
    assert payload["phase"] == "8"


def test_ready(client) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["checks"]["api_bootstrap"] is True


def test_health_api_v1(client) -> None:
    """Gateway rewrites /api/v1/optimization-explainable/health → /api/v1/health."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["component"] == "optimization-explainable"
