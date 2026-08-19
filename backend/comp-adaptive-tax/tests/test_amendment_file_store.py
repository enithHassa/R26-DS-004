"""File-store amendment pipeline: upload → extract → get → approve/reject (no Postgres)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.main import create_app
from adaptive_tax_app.services.amendment_file_store import load_job


@pytest.fixture()
def file_store_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    upload_root = tmp_path / "uploads"
    store_dir = tmp_path / "amendment-jobs"
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_AMENDMENT_STORE", "file")
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_AMENDMENT_STORE_DIR", str(store_dir))
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_UPLOAD_ROOT", str(upload_root))
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "fixture")
    get_adaptive_tax_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        yield client
    get_adaptive_tax_settings.cache_clear()


def _pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def test_upload_extract_get_approve_file_store(file_store_client: TestClient) -> None:
    pdf = _pdf_bytes(
        "Section 52 of the principal enactment is hereby amended by the substitution "
        "for the words one million two hundred thousand of the words one million "
        "eight hundred thousand relating to qualifying payments."
    )
    upload = file_store_client.post(
        "/api/v1/admin/amendments/upload",
        files={"file": ("IR_Act_No_02-2025_E.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    job_id = uuid.UUID(upload.json()["id"])
    assert upload.json()["file_hash"]
    assert upload.json()["storage_path"]
    assert upload.json()["status"] == "uploaded"

    extract = file_store_client.post(f"/api/v1/admin/amendments/{job_id}/extract")
    assert extract.status_code == 200, extract.text
    extract_body = extract.json()
    assert extract_body["mode"] == "fixture"
    assert extract_body["rule_count"] >= 1
    assert extract_body["job"]["status"] == "extracted"
    assert all(row["source_quote"] for row in extract_body["job"]["rule_sources"])

    detail = file_store_client.get(f"/api/v1/admin/amendments/{job_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == str(job_id)
    assert body["status"] == "extracted"
    assert isinstance(body["extracted_rules"], dict)
    assert body["rule_sources"]
    assert body["rule_sources"][0]["source_quote"]
    assert body["rule_sources"][0]["status"] == "pending"

    approve = file_store_client.post(f"/api/v1/admin/amendments/{job_id}/approve")
    assert approve.status_code == 200, approve.text
    approved = approve.json()
    assert approved["job"]["status"] == "approved"
    assert approved["merge"]["reason"] in {"ok", "partial", "neo4j_unavailable"}
    assert len(approved["rule_version_ids"]) >= 1

    stored = load_job(job_id)
    assert stored is not None
    assert stored.status == "approved"
    assert len(stored.rule_versions) >= 1
    assert any((v.params.get("section") or "").strip() for v in stored.rule_versions)
    assert all(r.status == "approved" for r in stored.rule_sources)


def test_upload_extract_reject_file_store(file_store_client: TestClient) -> None:
    pdf = _pdf_bytes("Section 52 of the principal enactment is hereby amended.")
    upload = file_store_client.post(
        "/api/v1/admin/amendments/upload",
        files={"file": ("reject_demo.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    job_id = uuid.UUID(upload.json()["id"])

    extract = file_store_client.post(f"/api/v1/admin/amendments/{job_id}/extract")
    assert extract.status_code == 200, extract.text

    rejected = file_store_client.post(
        f"/api/v1/admin/amendments/{job_id}/reject",
        json={"reason": "source quote does not match PDF"},
    )
    assert rejected.status_code == 200, rejected.text
    body = rejected.json()
    assert body["status"] == "rejected"
    assert body["job"]["status"] == "rejected"
    assert body["job"]["rejection_reason"] == "source quote does not match PDF"

    stored = load_job(job_id)
    assert stored is not None
    assert stored.status == "rejected"
    assert stored.rejection_reason == "source quote does not match PDF"
