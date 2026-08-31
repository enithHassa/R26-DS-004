"""Postgres integration: upload → extract (fixture) → get → approve/reject.

Skipped automatically when the configured database is unreachable.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.db_loader import AmendmentJob, RuleSource, RuleVersion
from adaptive_tax_app.main import create_app
from backend.shared.config.database import SessionLocal, engine


def _postgres_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — skip path for offline CI
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _postgres_available(), reason="Postgres unavailable"),
]


@pytest.fixture()
def integration_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_EXTRACTION_MODE", "fixture")
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_UPLOAD_ROOT", str(tmp_path))
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


def _cleanup_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(AmendmentJob, job_id)
        if job is not None:
            db.delete(job)
            db.commit()
    finally:
        db.close()


def test_upload_extract_get_approve_postgres(integration_client: TestClient) -> None:
    pdf = _pdf_bytes(
        "Section 52 of the principal enactment is hereby amended by the substitution "
        "for the words one million two hundred thousand of the words one million "
        "eight hundred thousand relating to qualifying payments."
    )
    upload = integration_client.post(
        "/api/v1/admin/amendments/upload",
        files={"file": ("IR_Act_No_02-2025_E.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    job_id = uuid.UUID(upload.json()["id"])
    assert upload.json()["file_hash"]
    assert upload.json()["storage_path"]

    try:
        extract = integration_client.post(f"/api/v1/admin/amendments/{job_id}/extract")
        assert extract.status_code == 200, extract.text
        extract_body = extract.json()
        assert extract_body["mode"] == "fixture"
        assert extract_body["rule_count"] >= 1
        assert extract_body["job"]["status"] == "extracted"
        assert all(
            row["source_quote"] for row in extract_body["job"]["rule_sources"]
        )

        detail = integration_client.get(f"/api/v1/admin/amendments/{job_id}")
        assert detail.status_code == 200, detail.text
        body = detail.json()
        assert body["id"] == str(job_id)
        assert body["status"] == "extracted"
        assert isinstance(body["extracted_rules"], dict)
        assert body["rule_sources"]
        assert body["rule_sources"][0]["source_quote"]
        assert body["rule_sources"][0]["status"] == "pending"

        approve = integration_client.post(f"/api/v1/admin/amendments/{job_id}/approve")
        assert approve.status_code == 200, approve.text
        approved = approve.json()
        assert approved["job"]["status"] == "approved"
        assert approved["merge"]["reason"] in {"ok", "partial", "neo4j_unavailable"}
        if approved["merge"]["merged"]:
            assert approved["merge"]["reason"] in {"ok", "partial"}
            assert approved["merge"]["details"]["modifies"]
        assert len(approved["rule_version_ids"]) >= 1

        db = SessionLocal()
        try:
            versions = list(
                db.scalars(
                    select(RuleVersion).where(RuleVersion.amendment_job_id == job_id)
                ).all()
            )
            assert len(versions) >= 1
            assert versions[0].params.get("section") == "52"
            sources = list(
                db.scalars(
                    select(RuleSource).where(RuleSource.amendment_job_id == job_id)
                ).all()
            )
            assert all(s.status.value == "approved" for s in sources)
        finally:
            db.close()
    finally:
        _cleanup_job(job_id)


def test_upload_extract_reject_postgres(integration_client: TestClient) -> None:
    pdf = _pdf_bytes("Section 52 of the principal enactment is hereby amended.")
    upload = integration_client.post(
        "/api/v1/admin/amendments/upload",
        files={"file": ("reject_demo.pdf", pdf, "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    job_id = uuid.UUID(upload.json()["id"])

    try:
        extract = integration_client.post(f"/api/v1/admin/amendments/{job_id}/extract")
        assert extract.status_code == 200, extract.text

        rejected = integration_client.post(
            f"/api/v1/admin/amendments/{job_id}/reject",
            json={"reason": "source quote does not match PDF"},
        )
        assert rejected.status_code == 200, rejected.text
        body = rejected.json()
        assert body["status"] == "rejected"
        assert body["job"]["status"] == "rejected"
        assert body["job"]["rejection_reason"] == "source quote does not match PDF"
    finally:
        _cleanup_job(job_id)
