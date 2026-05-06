"""Smoke tests for tax optimization service."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["component"] == "tax-optimization"


def test_ready(client: TestClient) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["checks"]["rules_loaded"] is True


def test_openapi_has_compliance(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]
    assert "/api/v1/compliance/check" in paths
    post = paths["/api/v1/compliance/check"]["post"]
    assert "tax-opt-b-compliance" in (post.get("tags") or [])
    assert post.get("summary")
    assert "requestBody" in post
    assert post["responses"].get("200") is not None
