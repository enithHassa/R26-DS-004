"""Admin amendment API route registration + upload validation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_openapi_includes_admin_amendment_routes(client: TestClient) -> None:
    payload = client.get("/openapi.json").json()
    paths = payload["paths"]
    assert "/api/v1/admin/amendments/upload" in paths
    assert "/api/v1/admin/amendments/{job_id}/extract" in paths
    assert "/api/v1/admin/amendments/{job_id}" in paths
    assert "/api/v1/admin/amendments/{job_id}/approve" in paths
    assert "/api/v1/admin/amendments/{job_id}/reject" in paths
    assert "/api/v1/knowledge/graph-stats" in paths
    assert "/api/v1/knowledge/rag/search" in paths


def test_upload_rejects_non_pdf(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/amendments/upload",
        files={"file": ("notes.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"] or "pdf" in response.json()["detail"].lower()


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/amendments/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.integration
def test_get_missing_job_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/admin/amendments/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


def test_reject_requires_reason_body(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/amendments/00000000-0000-0000-0000-000000000001/reject",
        json={"reason": ""},
    )
    assert response.status_code == 422
