"""Catalog-admin Step 1: token gate + reviewer header on mutating routes."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.config import get_adaptive_tax_settings

TOKEN = "test-catalog-admin-token"
HEADERS_TOKEN = {"X-Catalog-Admin-Token": TOKEN}
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "A. Reviewer",
}


@pytest.fixture()
def catalog_admin_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN", TOKEN)
    get_adaptive_tax_settings.cache_clear()
    yield
    get_adaptive_tax_settings.cache_clear()


def test_empty_token_refuses_to_serve(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN", "")
    get_adaptive_tax_settings.cache_clear()
    resp = client.get("/api/v1/catalog-admin/session")
    assert resp.status_code == 503
    assert "COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN" in resp.json()["detail"]


def test_missing_token_is_401(client: TestClient, catalog_admin_enabled: None) -> None:
    resp = client.get("/api/v1/catalog-admin/session")
    assert resp.status_code == 401


def test_wrong_token_is_401(client: TestClient, catalog_admin_enabled: None) -> None:
    resp = client.get(
        "/api/v1/catalog-admin/session",
        headers={"X-Catalog-Admin-Token": "nope"},
    )
    assert resp.status_code == 401


def test_valid_token_session_ok(client: TestClient, catalog_admin_enabled: None) -> None:
    resp = client.get("/api/v1/catalog-admin/session", headers=HEADERS_TOKEN)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["gate"] == "token"


def test_queue_requires_token_not_reviewer(
    client: TestClient, catalog_admin_enabled: None
) -> None:
    resp = client.get("/api/v1/catalog-admin/queue", headers=HEADERS_TOKEN)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["proposals"], list)
    assert isinstance(body["failed_jobs"], list)


def test_mutating_check_requires_reviewer(
    client: TestClient, catalog_admin_enabled: None
) -> None:
    resp = client.post("/api/v1/catalog-admin/session/check", headers=HEADERS_TOKEN)
    assert resp.status_code == 400
    assert "Reviewer" in resp.json()["detail"]


def test_mutating_check_blank_reviewer_rejected(
    client: TestClient, catalog_admin_enabled: None
) -> None:
    resp = client.post(
        "/api/v1/catalog-admin/session/check",
        headers={**HEADERS_TOKEN, "X-Catalog-Admin-Reviewer": "   "},
    )
    assert resp.status_code == 400


def test_mutating_check_accepts_token_and_reviewer(
    client: TestClient, catalog_admin_enabled: None
) -> None:
    resp = client.post("/api/v1/catalog-admin/session/check", headers=HEADERS_BOTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["reviewer"] == "A. Reviewer"


def test_approve_blank_reviewer_is_400(
    client: TestClient, catalog_admin_enabled: None
) -> None:
    resp = client.post(
        "/api/v1/catalog-admin/proposed/any-doc/rows/any-row/approve",
        headers={**HEADERS_TOKEN, "X-Catalog-Admin-Reviewer": "   "},
    )
    assert resp.status_code == 400
    assert "Reviewer" in resp.json()["detail"]
