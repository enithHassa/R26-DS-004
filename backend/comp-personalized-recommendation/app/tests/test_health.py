"""Smoke tests for the recommendation component."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["component"] == "personalized-recommendation"


def test_openapi(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]

    for p in [
        "/api/v1/profiles",
        "/api/v1/strategies/generate",
        "/api/v1/recommendations",
        "/api/v1/impact/simulate",
    ]:
        assert p in paths, f"missing route {p}"


def test_not_implemented_stubs_respond(client: TestClient) -> None:
    resp = client.post("/api/v1/strategies/generate", json={"profile_id": "x"})
    assert resp.status_code in (422, 501)
