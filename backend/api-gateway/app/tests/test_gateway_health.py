from __future__ import annotations

from fastapi.testclient import TestClient


def test_gateway_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "api-gateway"
