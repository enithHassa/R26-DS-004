"""Catalog-admin Step 3: background extract_proposal, failure, retry, delete."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import fitz
import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.main import create_app
from adaptive_tax_app.services import catalog_extract
from adaptive_tax_app.services.catalog_admin_store import catalog_admin_paths
from adaptive_tax_app.services.catalog_extract import join_extract

TOKEN = "test-catalog-admin-token"
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "A. Reviewer",
}
HEADERS_TOKEN = {"X-Catalog-Admin-Token": TOKEN}


@pytest.fixture()
def admin_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CATALOG_ADMIN_WORK_DIR", str(tmp_path))
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


def _upload_clear(client: TestClient) -> dict[str, Any]:
    pdf = _pdf_bytes(
        "Inland Revenue (Amendment) Act, No. 99 of 2099\nUNIQUE EXTRACT BODY 4c2e"
    )
    resp = client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("brand-new-act.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case"] == "none"
    assert body["job_id"]
    return body


def _fake_proposal(**kwargs: Any) -> dict[str, Any]:
    assert kwargs["only_sections"] is None
    assert kwargs["dry_run"] is False
    assert kwargs["model"] == "gpt-4o"
    sid = kwargs["source_doc_id"]
    return {
        "spec_version": "1.0.0",
        "phase": 6,
        "run_id": "test-run",
        "model": "gpt-4o",
        "temperature": 0,
        "source_doc_id": sid,
        "act_title": kwargs["act_title"],
        "pdf_file_name": Path(kwargs["pdf_path"]).name,
        "pdf_sha256": "abc",
        "extracted_at": "2026-08-22T12:00:00+00:00",
        "sections": [
            {
                "section_key": "52",
                "status": "ok",
                "focus_chars": 12,
                "row_count": 1,
                "included_count": 1,
                "rows": [
                    {
                        "entry_id": f"{sid}:52:relief:0",
                        "included": True,
                        "quote_ok_full_doc": True,
                        "provenance_complete": True,
                        "quote_long_enough": True,
                        "quote": "qualifying payment of two million",
                    }
                ],
            },
            {"section_key": "5", "status": "skipped_empty_focus", "rows": []},
        ],
        "rows": [
            {
                "entry_id": f"{sid}:52:relief:0",
                "included": True,
                "quote_ok_full_doc": True,
                "provenance_complete": True,
                "quote_long_enough": True,
            }
        ],
        "row_count": 1,
        "included_count": 1,
        "diff": {"reliefs": {"new": [], "changed": [], "unchanged": []}},
    }


def test_extract_returns_before_llm_and_writes_only_on_success(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    released = threading_event()

    def slow_ok(**kwargs: Any) -> dict[str, Any]:
        released.wait(timeout=2)
        time.sleep(0.15)
        return _fake_proposal(**kwargs)

    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", slow_ok)
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    t0 = time.perf_counter()
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    elapsed = time.perf_counter() - t0
    assert start.status_code == 202, start.text
    assert start.json()["status"] == "extracting"
    assert elapsed < 1.0
    paths = catalog_admin_paths()
    sid = start.json()["source_doc_id"]
    assert not (paths.proposed_dir / f"{sid}.json").is_file()
    released.set()
    join_extract(job_id, timeout=10)
    done = admin_client.get(f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_TOKEN)
    assert done.status_code == 200
    assert done.json()["status"] == "extracted"
    proposed = paths.proposed_dir / f"{sid}.json"
    assert proposed.is_file()
    payload = json.loads(proposed.read_text(encoding="utf-8"))
    assert payload["job_id"] == job_id
    assert payload["text_sha256"] == uploaded["text_sha256"]
    assert payload["duplicate_check"]["outcome"] == "clear"
    assert payload["classification"]["status"] == "pending_human"
    assert payload["classification"]["corpus_harvest_written"] is False
    assert payload["classification"]["provisions"][0]["kind_human"] is None
    assert (paths.extracted_dir / f"{sid}__52.json").is_file()
    assert not (paths.extracted_dir / f"{sid}__5.json").is_file()
    queue = admin_client.get("/api/v1/catalog-admin/queue", headers=HEADERS_TOKEN)
    ids = {row["source_doc_id"] for row in queue.json()["proposals"]}
    assert sid in ids


def threading_event():
    import threading

    return threading.Event()


def test_extract_failure_writes_no_proposal(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("llm timeout")

    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", boom)
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    sid = uploaded["suggested_source_doc_id"]
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    failed = admin_client.get(f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_TOKEN)
    assert failed.json()["status"] == "failed"
    assert "llm timeout" in failed.json()["error"]
    paths = catalog_admin_paths()
    assert not (paths.proposed_dir / f"{sid}.json").is_file()
    assert list(paths.extracted_dir.glob(f"{sid}__*.json")) == []
    queue = admin_client.get("/api/v1/catalog-admin/queue", headers=HEADERS_TOKEN)
    failed_ids = {row["id"] for row in queue.json()["failed_jobs"]}
    assert job_id in failed_ids
    pending = {row["source_doc_id"] for row in queue.json()["proposals"]}
    assert sid not in pending


def test_retry_clears_stray_files_then_succeeds(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def flaky(**kwargs: Any) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("network drop")
        return _fake_proposal(**kwargs)

    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", flaky)
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    sid = uploaded["suggested_source_doc_id"]
    paths = catalog_admin_paths()
    paths.extracted_dir.mkdir(parents=True)
    paths.proposed_dir.mkdir(parents=True)
    stray_ex = paths.extracted_dir / f"{sid}__52.json"
    stray_pr = paths.proposed_dir / f"{sid}.json"
    stray_ex.write_text("{}", encoding="utf-8")
    stray_pr.write_text("{}", encoding="utf-8")

    admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    join_extract(job_id, timeout=10)
    assert admin_client.get(
        f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_TOKEN
    ).json()["status"] == "failed"
    assert not stray_ex.is_file()
    assert not stray_pr.is_file()

    retry = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/retry", headers=HEADERS_BOTH)
    assert retry.status_code == 202
    join_extract(job_id, timeout=10)
    done = admin_client.get(f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_TOKEN)
    assert done.json()["status"] == "extracted"
    assert (paths.proposed_dir / f"{sid}.json").is_file()


def test_paused_rescan_cannot_extract(admin_client: TestClient) -> None:
    pdf = _pdf_bytes(
        "Inland Revenue (Amendment) Act, No. 02 of 2025\nRESCAN extract block 11"
    )
    resp = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("rescanned-copy.pdf", pdf, "application/pdf")},
    )
    assert resp.json()["case"] == "d"
    job_id = resp.json()["job_id"]
    blocked = admin_client.post(
        f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH
    )
    assert blocked.status_code == 400
    assert "paused" in blocked.json()["detail"].lower()


def test_delete_failed_job_removes_pdf_not_manifest(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(**_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("malformed")

    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", boom)
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    join_extract(job_id, timeout=10)
    paths = catalog_admin_paths()
    pdf_path = Path(
        admin_client.get(f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_TOKEN).json()[
            "storage_path"
        ]
    )
    assert pdf_path.is_file()
    deleted = admin_client.delete(f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_BOTH)
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert not pdf_path.is_file()
    missing = admin_client.get(f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_TOKEN)
    assert missing.status_code == 404


def test_remove_proposal_drops_queue_entry(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", _fake_proposal)
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    sid = uploaded["suggested_source_doc_id"]
    admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    join_extract(job_id, timeout=10)
    paths = catalog_admin_paths()
    assert (paths.proposed_dir / f"{sid}.json").is_file()

    removed = admin_client.delete(
        f"/api/v1/catalog-admin/proposed/{sid}",
        headers=HEADERS_BOTH,
    )
    assert removed.status_code == 200, removed.text
    body = removed.json()
    assert body["status"] == "removed"
    assert body["source_doc_id"] == sid
    assert not (paths.proposed_dir / f"{sid}.json").is_file()
    assert list(paths.extracted_dir.glob(f"{sid}__*.json")) == []
    assert admin_client.get(f"/api/v1/catalog-admin/jobs/{job_id}", headers=HEADERS_TOKEN).status_code == 404
    queue = admin_client.get("/api/v1/catalog-admin/queue", headers=HEADERS_TOKEN)
    pending = {row["source_doc_id"] for row in queue.json()["proposals"]}
    assert sid not in pending


def test_pass1_relief_row_drafts_taxpayer_question_fields() -> None:
    from adaptive_tax_app.services.catalog_duplicate import p4

    schema = p4().ReliefRow.model_json_schema()
    required = set(schema.get("required") or [])
    for field in (
        "display_name",
        "question_prompt",
        "input_kind",
        "help",
        "compare_group_id",
        "cap_amount",
        "quote",
    ):
        assert field in schema["properties"]
        assert field in required

