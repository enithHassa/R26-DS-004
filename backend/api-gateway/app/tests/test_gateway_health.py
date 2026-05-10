from __future__ import annotations

from fastapi.testclient import TestClient


def test_gateway_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "api-gateway"


def test_gateway_ready_includes_upstream_checks(client: TestClient) -> None:
    r = client.get("/ready")
    assert r.status_code == 200
    data = r.json()
    assert "checks" in data
    assert "recommendation" in data["checks"]
    assert "optimization" in data["checks"]
    assert "transaction" in data["checks"]
    assert "language_model" in data["checks"]
    assert data["checks"]["recommendation"] in (True, False)
    assert data["checks"]["optimization"] in (True, False)
    assert data["checks"]["transaction"] in (True, False)
    assert data["checks"]["language_model"] in (True, False)
