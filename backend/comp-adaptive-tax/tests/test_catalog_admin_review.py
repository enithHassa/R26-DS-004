"""Catalog-admin Step 6: Phase 5 review wrapper, engine_binding, impact preview."""

from __future__ import annotations

import hashlib
import json
import shutil
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
    DEFAULT_LEDGER_PATH,
    catalog_admin_paths,
)
from adaptive_tax_app.services.catalog_classify import load_proposed
from adaptive_tax_app.services.catalog_extract import join_extract
from adaptive_tax_app.services.catalog_duplicate import p5
from adaptive_tax_app.services.catalog_review import resolve_catalog_compare_group, tax_effect_copy

TOKEN = "test-catalog-admin-token"
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "A. Classifier",
}
HEADERS_TOKEN = {"X-Catalog-Admin-Token": TOKEN}
BINDER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "B. Binder"}
APPROVER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "C. Approver"}


def _seed_year_catalog() -> None:
    paths = catalog_admin_paths()
    if not paths.approved_dir.exists():
        shutil.copytree(APPROVED_DIR, paths.approved_dir)
    rates_src = APPROVED_DIR.parent / "rates"
    if rates_src.is_dir() and not paths.rates_dir.exists():
        shutil.copytree(rates_src, paths.rates_dir)
    phase5 = p5()
    for directory in (paths.approved_dir, paths.rates_dir):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["content_sha256"] = phase5.canonical_sha256(payload)
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    included = {
        "entry_id": f"{sid}:52:relief:0",
        "included": True,
        "row_kind": "relief",
        "display_name": "Employment income relief",
        "compare_group_id": "employment_income_relief",
        "section_ref": "52",
        "effective_from": "2024-04-01",
        "cap_amount": "700000",
        "quote": "April 1, 2024 quote",
        "quote_ok_full_doc": True,
        "pass2_verbatim": True,
    }
    excluded = {
        "entry_id": f"{sid}:52:relief:gate",
        "included": False,
        "row_kind": "relief",
        "display_name": "Gate fail row",
        "compare_group_id": "employment_income_relief",
        "section_ref": "52",
        "effective_from": "2024-04-01",
        "cap_amount": "1",
        "quote": "not a substring",
        "quote_ok_full_doc": False,
        "pass2_verbatim": False,
    }
    return {
        "spec_version": "1.0.0",
        "phase": 6,
        "source_doc_id": sid,
        "act_title": kwargs.get("act_title") or "Act",
        "pdf_file_name": Path(kwargs["pdf_path"]).name,
        "extracted_at": "2026-08-22T12:00:00+00:00",
        "rows": [included, excluded],
        "sections": [
            {
                "section_key": "52",
                "status": "ok",
                "rows": [included, excluded],
                "row_count": 2,
                "included_count": 1,
            }
        ],
        "row_count": 2,
        "included_count": 1,
    }


def _ready(admin_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, str, str]:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", _fake_proposal)
    pdf = _pdf_bytes("Inland Revenue (Amendment) Act, No. 61 of 2096\nREVIEW EXTRACT BODY 6c")
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("review-act.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    included = f"{sid}:52:relief:0"
    excluded = f"{sid}:52:relief:gate"
    return job_id, sid, included, excluded


def test_tax_effect_copy_unset_none_and_reducing() -> None:
    assert "cannot be approved" in tax_effect_copy(None)
    assert "will NOT affect" in tax_effect_copy("none")
    text = tax_effect_copy("solar_panel_relief")
    assert "WILL reduce calculated tax" in text
    assert "official calculate()" in text
    assert "catalog estimate" in text
    assert "component_id required" in tax_effect_copy("filing_line")


def test_gate_fail_cannot_approve(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _job, sid, included, excluded = _ready(admin_client, monkeypatch)
    blocked = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{excluded}/approve",
        headers=APPROVER,
    )
    assert blocked.status_code == 400
    assert "Gate-fail" in blocked.json()["detail"]

    unset = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
    )
    assert unset.status_code == 400
    assert "classification" in unset.json()["detail"].lower()


def test_approve_writes_ledger_reviewer_only_and_isolates_work_dir(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_before = (
        hashlib.sha256(DEFAULT_LEDGER_PATH.read_bytes()).hexdigest()
        if DEFAULT_LEDGER_PATH.is_file()
        else None
    )
    _job, sid, included, _excluded = _ready(admin_client, monkeypatch)
    classified = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": included, "kind_human": "UPDATE"},
    )
    assert classified.status_code == 200, classified.text
    bound = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
        headers=BINDER,
        json={"row_id": included, "kind": "none"},
    )
    assert bound.status_code == 200, bound.text
    provision = bound.json()["proposal"]["classification"]["provisions"][0]
    assert provision["kind_set_by"] == "A. Classifier"
    assert provision["engine_binding_set_by"] == "B. Binder"
    assert provision["provenance"]["reviewed_by"] is None

    approved = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
    )
    assert approved.status_code == 200, approved.text
    after = approved.json()["proposal"]["classification"]["provisions"][0]
    assert after["kind_set_by"] == "A. Classifier"
    assert after["engine_binding_set_by"] == "B. Binder"
    assert after["engine_binding"] == {"kind": "none"}
    assert after["provenance"]["reviewed_by"] == "C. Approver"
    relief = next(r for r in approved.json()["relief_rows"] if r["entry_id"] == included)
    assert relief["decision_status"] == "approved"
    assert relief["tax_effect"] and "will NOT affect" in relief["tax_effect"]

    paths = catalog_admin_paths()
    ledger = paths.ledger_path
    assert ledger.is_file()
    assert "C. Approver" in ledger.read_text(encoding="utf-8")
    ledger_payload = json.loads(ledger.read_text(encoding="utf-8"))
    decision = next(iter((ledger_payload.get("decisions") or {}).values()))
    assert decision["compare_group_id"] == "employment_income_relief"
    live_after = (
        hashlib.sha256(DEFAULT_LEDGER_PATH.read_bytes()).hexdigest()
        if DEFAULT_LEDGER_PATH.is_file()
        else None
    )
    assert live_after == live_before
    assert ledger.resolve() != DEFAULT_LEDGER_PATH.resolve()

    rebound = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
        headers=BINDER,
        json={"row_id": included, "kind": "solar_panel_relief"},
    )
    assert rebound.status_code == 200
    rebound_row = rebound.json()["proposal"]["classification"]["provisions"][0]
    assert rebound_row["kind_set_by"] == "A. Classifier"
    assert rebound_row["engine_binding_set_by"] == "B. Binder"
    assert rebound_row["provenance"]["reviewed_by"] == "C. Approver"
    assert rebound_row["engine_binding"]["kind"] == "solar_panel_relief"


def test_unset_binding_blocks_approve_and_preview(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _job, sid, included, _excluded = _ready(admin_client, monkeypatch)
    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": included, "kind_human": "UPDATE"},
    )
    got = admin_client.get(f"/api/v1/catalog-admin/proposed/{sid}", headers=HEADERS_TOKEN)
    body = got.json()
    assert body["bindings_complete"] is False
    assert body["preview_ready"] is False
    relief = next(r for r in body["relief_rows"] if r["entry_id"] == included)
    assert relief["engine_binding"] is None
    assert "Tax effect not chosen" in relief["tax_effect"]
    assert relief["can_approve"] is False

    blocked = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
    )
    assert blocked.status_code == 400
    assert "Tax effect not chosen" in blocked.json()["detail"]

    preview = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-preview",
        headers=APPROVER,
    )
    assert preview.status_code == 400


def test_preview_fingerprint_changes_when_none_binding_list_changes(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _job, sid, included, _excluded = _ready(admin_client, monkeypatch)
    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": included, "kind_human": "UPDATE"},
    )
    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
        headers=BINDER,
        json={"row_id": included, "kind": "solar_panel_relief"},
    )
    approved = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
    )
    assert approved.status_code == 200, approved.text
    first = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-preview",
        headers=APPROVER,
    )
    assert first.status_code == 200, first.text
    solar = first.json()
    assert solar["tax_inert_rows"] == []
    assert solar["preview_fingerprint"]
    assert any(g["needs_gap_ack"] for g in solar["groups"])
    assert all(g["gap_banner"] for g in solar["groups"] if g["needs_gap_ack"])

    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
        headers=BINDER,
        json={"row_id": included, "kind": "none"},
    )
    second = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-preview",
        headers=APPROVER,
    )
    assert second.status_code == 200
    none_body = second.json()
    assert none_body["tax_inert_rows"]
    assert none_body["tax_inert_rows"][0]["note"] == "interview-visible, tax-inert"
    assert none_body["preview_fingerprint"] != solar["preview_fingerprint"]

    again = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-preview",
        headers=APPROVER,
    )
    assert again.json()["preview_fingerprint"] == none_body["preview_fingerprint"]


def test_get_proposed_includes_identity_and_panels(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _job, sid, included, excluded = _ready(admin_client, monkeypatch)
    got = admin_client.get(f"/api/v1/catalog-admin/proposed/{sid}", headers=HEADERS_TOKEN)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["promote_enabled"] is False
    assert body["source_doc_id"] == sid
    assert body["proposal"]["text_sha256"]
    ids = {r["entry_id"] for r in body["relief_rows"]}
    assert included in ids
    assert excluded in ids
    gate = next(r for r in body["relief_rows"] if r["entry_id"] == excluded)
    assert gate["gate_ok"] is False
    assert gate["can_approve"] is False
    assert load_proposed(sid)["classification"]["provisions"][0]["kind_human"] is None


def test_fifth_schedule_paragraph_2_a_maps_to_personal_relief() -> None:
    got = resolve_catalog_compare_group(
        {
            "compare_group_id": "fifth_schedule_paragraph_2_a",
            "display_name": "Personal relief",
            "baseline_compare_group_id": "personal_relief",
        }
    )
    assert got["catalog_compare_group_id"] == "personal_relief"
    assert got["extract_compare_group_id"] == "fifth_schedule_paragraph_2_a"
    assert got["compare_group_mapped"] is True


def test_preview_maps_paragraph_slug_onto_live_personal_relief(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_proposal(**kwargs: Any) -> dict[str, Any]:
        sid = kwargs["source_doc_id"]
        row = {
            "entry_id": f"{sid}:Fifth Schedule:relief:0",
            "included": True,
            "row_kind": "relief",
            "display_name": "Personal relief",
            "compare_group_id": "fifth_schedule_paragraph_2_a",
            "baseline_compare_group_id": "personal_relief",
            "section_ref": "Fifth Schedule",
            "effective_from": "2020-01-01",
            "cap_amount": "3000000",
            "quote": "Rs. 3,000,000, for each year of assessment",
            "quote_ok_full_doc": True,
            "pass2_verbatim": True,
        }
        return {
            "spec_version": "1.0.0",
            "phase": 6,
            "source_doc_id": sid,
            "act_title": "Act",
            "pdf_file_name": Path(kwargs["pdf_path"]).name,
            "extracted_at": "2026-08-22T12:00:00+00:00",
            "rows": [row],
            "sections": [
                {
                    "section_key": "Fifth Schedule",
                    "status": "ok",
                    "rows": [row],
                    "row_count": 1,
                    "included_count": 1,
                }
            ],
            "row_count": 1,
            "included_count": 1,
        }

    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(catalog_extract, "extract_proposal_impl", fake_proposal)
    pdf = _pdf_bytes("Inland Revenue (Amendment) Act, No. 45 of 2095\nPERSONAL RELIEF MAP 2a")
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("pr-map.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    join_extract(job_id, timeout=10)
    _seed_year_catalog()
    included = f"{sid}:Fifth Schedule:relief:0"
    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": included, "kind_human": "UPDATE"},
    )
    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
        headers=BINDER,
        json={"row_id": included, "kind": "none"},
    )
    approved = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
    )
    assert approved.status_code == 200, approved.text
    preview = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-preview",
        headers=APPROVER,
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert [g["compare_group_id"] for g in body["groups"]] == ["personal_relief"]
    group = body["groups"][0]
    assert group["compare_group_mapped"] is True
    assert "fifth_schedule_paragraph_2_a" in group["extract_compare_group_ids"]
    assert group["known_table"] is True
    assert any(item.get("source_doc_id") for item in group["before"])
    got = admin_client.get(f"/api/v1/catalog-admin/proposed/{sid}", headers=HEADERS_TOKEN)
    relief = next(r for r in got.json()["relief_rows"] if r["entry_id"] == included)
    assert relief["catalog_compare_group_id"] == "personal_relief"
    assert relief["extract_compare_group_id"] == "fifth_schedule_paragraph_2_a"
