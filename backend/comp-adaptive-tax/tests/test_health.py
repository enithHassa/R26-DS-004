"""Health probe tests for Adaptive Tax."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_root(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["component"] == "adaptive-tax"


def test_ready(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in ("ok", "degraded")
    assert "checks" in payload
    assert payload["checks"]["api_bootstrap"] is True


def test_health_api_v1(client: TestClient) -> None:
    """Gateway rewrites /api/v1/adaptive-tax/health → /api/v1/health upstream."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["component"] == "adaptive-tax"


def test_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["info"]["title"] == "AI Tax Advisory — Adaptive Tax"
