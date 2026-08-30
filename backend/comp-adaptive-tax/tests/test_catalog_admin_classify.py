"""Catalog-admin Step 4: harvest_act suggestions; kind_human stays unset until a human sets it."""

from __future__ import annotations

import hashlib
import json
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
from adaptive_tax_app.services.catalog_admin_store import HARVEST_CORPUS_JSON, catalog_admin_paths
from adaptive_tax_app.services.catalog_classify import (
    live_confirmed_yas,
    match_harvest_record,
    suggest_kind,
    suggest_provision,
)
from adaptive_tax_app.services.catalog_extract import join_extract

TOKEN = "test-catalog-admin-token"
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "Vidumini",
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
        "Inland Revenue (Amendment) Act, No. 88 of 2098\nCLASSIFY EXTRACT BODY 7a1"
    )
    resp = client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("classify-act.pdf", pdf, "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["case"] == "none"
    return resp.json()


def _fake_proposal(*rows: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    sid = kwargs["source_doc_id"]
    included = list(rows) if rows else [
        {
            "entry_id": f"{sid}:52:relief:0",
            "included": True,
            "row_kind": "relief",
            "display_name": "Personal relief",
            "section_ref": "52",
            "effective_from": "2024-04-01",
            "quote": "Rs. 1,200,000 for each year of assessment commencing on April 1, 2024",
            "quote_ok_full_doc": True,
            "provenance_complete": True,
            "quote_long_enough": True,
        }
    ]
    return {
        "spec_version": "1.0.0",
        "phase": 6,
        "source_doc_id": sid,
        "act_title": kwargs.get("act_title") or "Act",
        "pdf_file_name": Path(kwargs["pdf_path"]).name,
        "extracted_at": "2026-08-22T12:00:00+00:00",
        "sections": [
            {
                "section_key": "52",
                "status": "ok",
                "row_count": len(included),
                "included_count": len(included),
                "rows": included,
            }
        ],
        "rows": included,
        "row_count": len(included),
        "included_count": len(included),
    }


def _empty_harvest(source_doc_id: str, pdf_path: Path, max_pages: int) -> SimpleNamespace:
    assert max_pages == 16
    return SimpleNamespace(
        source_doc_id=source_doc_id,
        file_name=pdf_path.name,
        pages_scanned=4,
        notes=["No commencement / Column III dates recovered in scanned pages."],
        records=[],
    )


def test_mixed_dates_suggest_per_row_not_one_pdf_label() -> None:
    live = set(live_confirmed_yas())
    max_ya = "2025_26"
    update_row = suggest_provision(
        {
            "entry_id": "a:relief:0",
            "included": True,
            "display_name": "Personal relief",
            "section_ref": "52",
            "effective_from": "2024-04-01",
            "quote": "cap from April 1, 2024",
        },
        harvest_records=[],
        live_yas=live,
        max_in_scope_ya=max_ya,
    )
    new_year_row = suggest_provision(
        {
            "entry_id": "a:relief:1",
            "included": True,
            "display_name": "Personal relief 2026",
            "section_ref": "52",
            "effective_from": "2026-04-01",
            "quote": "cap from April 1, 2026",
        },
        harvest_records=[],
        live_yas=live,
        max_in_scope_ya=max_ya,
    )
    assert update_row["kind_suggested"] == "UPDATE"
    assert update_row["derived_assessment_year"] == "2024_25"
    assert update_row["kind_human"] is None
    assert update_row["commencement_parse_kind"] == "row_effective_from"
    assert new_year_row["kind_suggested"] == "NEW_YEAR"
    assert new_year_row["derived_assessment_year"] == "2026_27"
    assert new_year_row["kind_human"] is None
    assert "2024_25" in live
    assert suggest_kind("2026_27", live, max_ya) == "NEW_YEAR"


def test_missing_effective_from_uses_harvest_section_ref() -> None:
    harvest = [
        {
            "section_ref": "s.5 amending 52",
            "operation_date": "2023-04-01",
            "derived_assessment_year": "2023_24",
            "quote": "5 52 01.04.2023",
            "parse_kind": "column_iii_row",
        }
    ]
    provision = suggest_provision(
        {
            "entry_id": "a:relief:0",
            "section_ref": "52",
            "effective_from": "",
            "quote": "row quote without a date",
        },
        harvest_records=harvest,
        live_yas={"2023_24"},
        max_in_scope_ya="2025_26",
    )
    assert provision["kind_suggested"] == "UPDATE"
    assert provision["commencement_quote"] == "5 52 01.04.2023"
    assert provision["commencement_parse_kind"] == "column_iii_row"
    assert provision["kind_human"] is None


def test_empty_harvest_still_requires_human_from_row_quote() -> None:
    provision = suggest_provision(
        {
            "entry_id": "a:relief:0",
            "section_ref": "Fifth Schedule",
            "effective_from": "",
            "quote": "Rs. 2,000,000 commencing on or after April 1, 2026",
        },
        harvest_records=[],
        live_yas=set(live_confirmed_yas()),
        max_in_scope_ya="2025_26",
    )
    assert provision["kind_suggested"] is None
    assert provision["kind_human"] is None
    assert provision["commencement_quote"].startswith("Rs. 2,000,000")
    assert provision["note"]
    assert match_harvest_record("52", []) is None


def test_extract_attaches_classification_and_does_not_write_corpus_harvest(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(
            {
                "entry_id": f"{kwargs['source_doc_id']}:52:relief:0",
                "included": True,
                "row_kind": "relief",
                "display_name": "Cap 2024",
                "section_ref": "52",
                "effective_from": "2024-04-01",
                "quote": "April 1, 2024 quote",
            },
            {
                "entry_id": f"{kwargs['source_doc_id']}:52:relief:1",
                "included": True,
                "row_kind": "relief",
                "display_name": "Cap 2026",
                "section_ref": "52",
                "effective_from": "2026-04-01",
                "quote": "April 1, 2026 quote",
            },
            **kwargs,
        ),
    )
    before = (
        hashlib.sha256(HARVEST_CORPUS_JSON.read_bytes()).hexdigest()
        if HARVEST_CORPUS_JSON.is_file()
        else None
    )
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    sid = uploaded["suggested_source_doc_id"]
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    after = (
        hashlib.sha256(HARVEST_CORPUS_JSON.read_bytes()).hexdigest()
        if HARVEST_CORPUS_JSON.is_file()
        else None
    )
    assert after == before

    paths = catalog_admin_paths()
    sidecar = paths.harvest_sidecar_dir / f"{sid}.json"
    assert sidecar.is_file()
    assert json.loads(sidecar.read_text(encoding="utf-8"))["corpus_harvest_written"] is False

    got = admin_client.get(f"/api/v1/catalog-admin/proposed/{sid}", headers=HEADERS_TOKEN)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["classification_complete"] is False
    assert body["promote_enabled"] is False
    provisions = body["proposal"]["classification"]["provisions"]
    assert [p["kind_suggested"] for p in provisions] == ["UPDATE", "NEW_YEAR"]
    assert all(p["kind_human"] is None for p in provisions)
    assert body["proposal"]["classification"]["pages_scanned"] == 4
    assert body["proposal"]["classification"]["harvest_notes"]


def test_set_kind_human_is_per_row_and_does_not_select_the_suggestion(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(
            {
                "entry_id": f"{kwargs['source_doc_id']}:52:relief:0",
                "included": True,
                "display_name": "Cap 2024",
                "section_ref": "52",
                "effective_from": "2024-04-01",
                "quote": "April 1, 2024 quote",
            },
            {
                "entry_id": f"{kwargs['source_doc_id']}:52:relief:1",
                "included": True,
                "display_name": "Cap 2026",
                "section_ref": "52",
                "effective_from": "2026-04-01",
                "quote": "April 1, 2026 quote",
            },
            **kwargs,
        ),
    )
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    sid = uploaded["suggested_source_doc_id"]
    admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    join_extract(job_id, timeout=10)
    row0 = f"{sid}:52:relief:0"
    row1 = f"{sid}:52:relief:1"

    first = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": row0, "kind_human": "UPDATE"},
    )
    assert first.status_code == 200, first.text
    provisions = first.json()["proposal"]["classification"]["provisions"]
    assert provisions[0]["kind_human"] == "UPDATE"
    assert provisions[0]["kind_set_by"] == "Vidumini"
    assert provisions[0]["kind_set_at"]
    assert provisions[1]["kind_human"] is None
    assert first.json()["classification_complete"] is False

    other = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "B. Reviewer"}
    second = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=other,
        json={"row_id": row1, "kind_human": "NEW_YEAR"},
    )
    assert second.status_code == 200
    provisions = second.json()["proposal"]["classification"]["provisions"]
    assert provisions[0]["kind_set_by"] == "Vidumini"
    assert provisions[1]["kind_human"] == "NEW_YEAR"
    assert provisions[1]["kind_set_by"] == "B. Reviewer"
    assert second.json()["classification_complete"] is True
    assert second.json()["proposal"]["classification"]["status"] == "complete"
    assert second.json()["promote_enabled"] is False


def test_classification_rejects_invalid_kind_and_missing_proposal(
    admin_client: TestClient,
) -> None:
    missing = admin_client.get(
        "/api/v1/catalog-admin/proposed/does-not-exist", headers=HEADERS_TOKEN
    )
    assert missing.status_code == 404
    bad = admin_client.post(
        "/api/v1/catalog-admin/proposed/does-not-exist/classification",
        headers=HEADERS_BOTH,
        json={"row_id": "x", "kind_human": "MAYBE"},
    )
    assert bad.status_code == 400


def test_refresh_classification_on_existing_proposal(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(**kwargs),
    )
    uploaded = _upload_clear(admin_client)
    job_id = uploaded["job_id"]
    sid = uploaded["suggested_source_doc_id"]
    admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    join_extract(job_id, timeout=10)
    paths = catalog_admin_paths()
    proposed = paths.proposed_dir / f"{sid}.json"
    payload = json.loads(proposed.read_text(encoding="utf-8"))
    del payload["classification"]
    proposed.write_text(json.dumps(payload), encoding="utf-8")
    ran = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classify",
        headers=HEADERS_BOTH,
    )
    assert ran.status_code == 200, ran.text
    assert ran.json()["proposal"]["classification"]["provisions"]
    assert ran.json()["proposal"]["classification"]["provisions"][0]["kind_human"] is None
    assert ran.json()["proposal"]["classification"]["harvest_run_by"] == "Vidumini"


def test_harvest_act_on_lone_pdf_without_manifest_sibling(tmp_path: Path) -> None:
    """Phase 1 harvest_act runs on a single PDF; no corpus_manifest sibling required."""
    pdf_path = tmp_path / "IR_Act_No._99_2099_E.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Inland Revenue (Amendment) Act, No. 99 of 2099\n"
        "Column III Date of operation\n"
        "5 52 01.04.2026\n"
        "The provisions of this Act shall come into operation on 1st of April, 2026.\n",
        fontsize=11,
    )
    pdf_path.write_bytes(doc.tobytes())
    doc.close()
    assert not pdf_path.with_suffix(".json").is_file()
    before = HARVEST_CORPUS_JSON.read_bytes() if HARVEST_CORPUS_JSON.is_file() else None
    harvest = catalog_classify.p1().harvest_act(
        "ird-amend-lone-2099", pdf_path, max_pages=4
    )
    after = HARVEST_CORPUS_JSON.read_bytes() if HARVEST_CORPUS_JSON.is_file() else None
    assert after == before
    assert harvest.pages_scanned >= 1
    assert harvest.file_name == pdf_path.name
    assert harvest.records


def test_extract_calls_harvest_act_on_uploaded_pdf(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(
            {
                "entry_id": f"{kwargs['source_doc_id']}:52:relief:0",
                "included": True,
                "row_kind": "relief",
                "display_name": "Cap 2026",
                "section_ref": "52",
                "effective_from": "2026-04-01",
                "quote": "April 1, 2026 quote",
            },
            **kwargs,
        ),
    )
    pdf = _pdf_bytes(
        "Inland Revenue (Amendment) Act, No. 77 of 2097\n"
        "The provisions of this Act shall come into operation on 1st of April, 2026.\n"
        "HARVEST EXTRACT BODY"
    )
    before = (
        hashlib.sha256(HARVEST_CORPUS_JSON.read_bytes()).hexdigest()
        if HARVEST_CORPUS_JSON.is_file()
        else None
    )
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("harvest-lone.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    start = admin_client.post(
        f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH
    )
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    after = (
        hashlib.sha256(HARVEST_CORPUS_JSON.read_bytes()).hexdigest()
        if HARVEST_CORPUS_JSON.is_file()
        else None
    )
    assert after == before
    paths = catalog_admin_paths()
    assert (paths.proposed_dir / f"{sid}.json").is_file()
    sidecar = json.loads(
        (paths.harvest_sidecar_dir / f"{sid}.json").read_text(encoding="utf-8")
    )
    assert sidecar["corpus_harvest_written"] is False
    got = admin_client.get(f"/api/v1/catalog-admin/proposed/{sid}", headers=HEADERS_TOKEN)
    assert got.status_code == 200, got.text
    notes = got.json()["proposal"]["classification"].get("harvest_notes") or []
    provisions = got.json()["proposal"]["classification"]["provisions"]
    assert provisions
    assert all(p["kind_human"] is None for p in provisions)
    assert notes is not None
