"""Catalog-admin Step 5: stage proposed/ only via Phase 6 save_proposed."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fitz
import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.main import create_app
from adaptive_tax_app.services import catalog_classify, catalog_extract
from adaptive_tax_app.services.catalog_admin_store import (
    APPROVED_DIR,
    MANIFEST_PATH,
    catalog_admin_paths,
)
from adaptive_tax_app.services.catalog_classify import load_proposed, save_proposed
from adaptive_tax_app.services.catalog_duplicate import p6
from adaptive_tax_app.services.catalog_extract import join_extract
from adaptive_tax_app.services.catalog_stage import set_engine_binding, set_proposed_year

TOKEN = "test-catalog-admin-token"
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "A. Classifier",
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


def _empty_harvest(source_doc_id: str, pdf_path: Path, max_pages: int) -> SimpleNamespace:
    return SimpleNamespace(
        source_doc_id=source_doc_id,
        file_name=pdf_path.name,
        pages_scanned=2,
        notes=["No commencement / Column III dates recovered in scanned pages."],
        records=[],
    )


def _fake_proposal(**kwargs: Any) -> dict[str, Any]:
    sid = kwargs["source_doc_id"]
    row = {
        "entry_id": f"{sid}:52:relief:0",
        "included": True,
        "row_kind": "relief",
        "display_name": "Personal relief",
        "section_ref": "52",
        "effective_from": "2024-04-01",
        "quote": "April 1, 2024 quote",
    }
    return {
        "spec_version": "1.0.0",
        "phase": 6,
        "source_doc_id": sid,
        "act_title": kwargs.get("act_title") or "Act",
        "pdf_file_name": Path(kwargs["pdf_path"]).name,
        "extracted_at": "2026-08-22T12:00:00+00:00",
        "rows": [row],
        "sections": [
            {
                "section_key": "52",
                "status": "ok",
                "rows": [row],
                "row_count": 1,
                "included_count": 1,
            }
        ],
        "row_count": 1,
        "included_count": 1,
    }


def _tree_fingerprint(directory: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.json")):
        out[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _extract_ready(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> tuple[str, str]:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", _fake_proposal)
    pdf = _pdf_bytes(
        "Inland Revenue (Amendment) Act, No. 77 of 2097\nSTAGE EXTRACT BODY 9f"
    )
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("stage-act.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    return job_id, sid


def test_stage_uses_phase6_save_proposed_and_skips_approved_rates_manifest(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    watcher = p6()
    real_save = watcher.save_proposed
    calls: list[str] = []

    def spy(payload: dict[str, Any]) -> Path:
        calls.append(str(payload["source_doc_id"]))
        return real_save(payload)

    monkeypatch.setattr(watcher, "save_proposed", spy)
    approved_before = _tree_fingerprint(APPROVED_DIR)
    rates_before = _tree_fingerprint(APPROVED_DIR.parent / "rates")
    manifest_before = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()

    _job_id, sid = _extract_ready(admin_client, monkeypatch)
    assert calls == [sid]

    paths = catalog_admin_paths()
    proposed = paths.proposed_dir / f"{sid}.json"
    assert proposed.is_file()
    payload = load_proposed(sid, paths)
    identity = payload["act_identity"]
    assert identity["parsed_from"]
    assert "quote" in identity
    assert payload["job_id"]
    assert payload["text_sha256"]
    assert payload["duplicate_check"]["outcome"] == "clear"
    provision = payload["classification"]["provisions"][0]
    assert provision["kind_human"] is None
    assert provision["kind_set_by"] is None
    assert provision["engine_binding"] is None
    assert provision["engine_binding_set_by"] is None
    assert provision["provenance"]["reviewed_by"] is None
    assert payload["proposed_year_set_by"] is None
    assert approved_before == _tree_fingerprint(APPROVED_DIR)
    assert rates_before == _tree_fingerprint(APPROVED_DIR.parent / "rates")
    assert manifest_before == hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    assert not (APPROVED_DIR / f"{sid}.json").is_file()


def test_attribution_fields_do_not_overwrite_each_other(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _job_id, sid = _extract_ready(admin_client, monkeypatch)
    paths = catalog_admin_paths()
    proposal = load_proposed(sid, paths)
    row = proposal["classification"]["provisions"][0]
    row["engine_binding"] = {"kind": "none"}
    row["engine_binding_set_by"] = "B. Binder"
    row["engine_binding_set_at"] = "2026-01-01T00:00:00+00:00"
    row["provenance"] = {
        "reviewed_by": "C. Approver",
        "reviewed_at": "2026-01-02T00:00:00+00:00",
    }
    save_proposed(proposal, paths)

    classified = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": row["row_id"], "kind_human": "UPDATE"},
    )
    assert classified.status_code == 200, classified.text
    after_body = classified.json()["proposal"]
    after = after_body["classification"]["provisions"][0]
    assert after["kind_human"] == "UPDATE"
    assert after["kind_set_by"] == "A. Classifier"
    assert after["engine_binding_set_by"] == "B. Binder"
    assert after["engine_binding"] == {"kind": "none"}
    assert after["provenance"]["reviewed_by"] == "C. Approver"

    rebound = set_engine_binding(after, kind="solar_panel_relief", reviewer="D. Binder")
    assert rebound["kind_set_by"] == "A. Classifier"
    assert rebound["engine_binding_set_by"] == "D. Binder"
    assert rebound["provenance"]["reviewed_by"] == "C. Approver"

    yeared = set_proposed_year(after_body, assessment_year="2026_27", reviewer="E. Year")
    assert yeared["proposed_year_set_by"] == "E. Year"
    assert yeared["classification"]["provisions"][0]["kind_set_by"] == "A. Classifier"
    assert yeared["classification"]["provisions"][0]["engine_binding_set_by"] == "D. Binder"
