"""Catalog-admin Step 7b: confirm new year, then Phase 6 cmd_promote."""

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
from adaptive_tax_app.services.catalog_admin_store import APPROVED_DIR, MANIFEST_PATH, catalog_admin_paths
from adaptive_tax_app.services.catalog_duplicate import p5
from adaptive_tax_app.services.catalog_extract import join_extract

TOKEN = "test-catalog-admin-token"
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "A. Classifier",
}
BINDER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "B. Binder"}
APPROVER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "C. Approver"}
PROMOTER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "D. Promoter"}
NEW_YA = "2027_28"


@pytest.fixture()
def admin_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("COMP_ADAPTIVE_TAX_CATALOG_ADMIN_WORK_DIR", str(tmp_path))
    get_adaptive_tax_settings.cache_clear()
    monkeypatch.setattr(
        "adaptive_tax_app.services.catalog_promote.notify_oe_index_refresh",
        lambda: {"ok": True, "url": "http://test/api/v1/index/refresh", "mocked": True},
    )
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


def _tree_fingerprint(root: Path) -> str:
    hasher = hashlib.sha256()
    if not root.is_dir():
        return hasher.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        hasher.update(path.relative_to(root).as_posix().encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def _reseal_year_dir(directory: Path) -> None:
    if not directory.is_dir():
        return
    phase5 = p5()
    for path in directory.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["content_sha256"] = phase5.canonical_sha256(payload)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _seed_year_catalog() -> None:
    paths = catalog_admin_paths()
    if not paths.approved_dir.exists():
        shutil.copytree(APPROVED_DIR, paths.approved_dir)
    rates_src = APPROVED_DIR.parent / "rates"
    if rates_src.is_dir() and not paths.rates_dir.exists():
        shutil.copytree(rates_src, paths.rates_dir)
    _reseal_year_dir(paths.approved_dir)
    _reseal_year_dir(paths.rates_dir)


def _fake_proposal(*, cap: str = "800000", kind: str = "employment", **kwargs: Any) -> dict[str, Any]:
    sid = kwargs["source_doc_id"]
    effective = kwargs.get("effective_from") or "2027-04-01"
    if kind == "rule":
        row = {
            "entry_id": f"{sid}:First Schedule:rule:0",
            "included": True,
            "row_kind": "rule",
            "display_name": "Tax rate for dividends",
            "description": "Tax rate for dividends",
            "value": "15%",
            "quote": "such gains and profits shall be taxed at the rate of 15%",
            "section_ref": "First Schedule",
            "effective_from": effective,
            "quote_ok_full_doc": True,
            "pass2_verbatim": True,
        }
        section = "First Schedule"
    else:
        row = {
            "entry_id": f"{sid}:52:relief:0",
            "included": True,
            "row_kind": "relief",
            "display_name": "Employment income relief",
            "compare_group_id": "employment_income_relief",
            "section_ref": "52",
            "effective_from": effective,
            "cap_amount": cap,
            "quote": "April 1, 2027 employment quote",
            "quote_ok_full_doc": True,
            "pass2_verbatim": True,
        }
        section = "52"
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
                "section_key": section,
                "status": "ok",
                "rows": [row],
                "row_count": 1,
                "included_count": 1,
            }
        ],
        "row_count": 1,
        "included_count": 1,
    }


def _ready(
    admin_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    kind: str = "employment",
) -> tuple[str, str]:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(kind=kind, effective_from="2027-04-01", **kwargs),
    )
    pdf = _pdf_bytes("Inland Revenue (Amendment) Act, No. 99 of 2027\nNEW YEAR BODY")
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("new-year-act.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    _seed_year_catalog()
    included = f"{sid}:First Schedule:rule:0" if kind == "rule" else f"{sid}:52:relief:0"
    classified = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": included, "kind_human": "NEW_YEAR"},
    )
    assert classified.status_code == 200, classified.text
    if kind != "rule":
        bound = admin_client.post(
            f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
            headers=BINDER,
            json={"row_id": included, "kind": "none"},
        )
        assert bound.status_code == 200, bound.text
    approved = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
        json={"sole_check": kind == "rule"},
    )
    assert approved.status_code == 200, approved.text
    return sid, included


def test_confirm_is_required_before_year_files_exist(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch)
    paths = catalog_admin_paths()
    assert not (paths.approved_dir / f"{NEW_YA}.json").is_file()
    got = admin_client.get(
        f"/api/v1/catalog-admin/proposed/{sid}",
        headers={"X-Catalog-Admin-Token": TOKEN},
    )
    assert got.status_code == 200
    body = got.json()
    assert body["suggested_new_year"] == NEW_YA
    assert body["new_year_confirmed"] is False
    assert "confirm before creating" in (body["new_year_confirm_message"] or "").lower()
    silent = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/confirm-new-year",
        headers=PROMOTER,
        json={"assessment_year": NEW_YA, "confirmed": False},
    )
    assert silent.status_code == 400
    assert not (paths.approved_dir / f"{NEW_YA}.json").is_file()


def test_confirm_writes_empty_skeleton_and_set_year(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_approved = _tree_fingerprint(APPROVED_DIR)
    sid, _included = _ready(admin_client, monkeypatch)
    paths = catalog_admin_paths()
    wrong = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/confirm-new-year",
        headers=PROMOTER,
        json={"assessment_year": "2028_29", "confirmed": True},
    )
    assert wrong.status_code == 400
    confirmed = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/confirm-new-year",
        headers=PROMOTER,
        json={"assessment_year": NEW_YA, "confirmed": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    approved = json.loads((paths.approved_dir / f"{NEW_YA}.json").read_text(encoding="utf-8"))
    rates = json.loads((paths.rates_dir / f"{NEW_YA}.json").read_text(encoding="utf-8"))
    assert approved["entries"] == []
    assert approved["phase1_empty_skeleton"] is True
    assert rates["needs_manual_verification"] is True
    assert rates["phase1_empty_skeleton"] is True
    body = confirmed.json()
    assert body["new_year_confirmed"] is True
    assert body["proposal"]["proposed_for_assessment_year"] == NEW_YA
    assert body["proposal"]["proposed_year_set_by"] == "D. Promoter"
    assert _tree_fingerprint(APPROVED_DIR) == live_approved
    phase5 = p5()
    assert approved.get("content_sha256")
    assert approved["content_sha256"] == phase5.canonical_sha256(approved)
    assert rates.get("content_sha256")
    assert rates["content_sha256"] == phase5.canonical_sha256(rates)


def test_confirm_refuses_live_year(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch)
    refused = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/confirm-new-year",
        headers=PROMOTER,
        json={"assessment_year": "2024_25", "confirmed": True},
    )
    assert refused.status_code == 400


def test_promote_without_confirm_is_blocked(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch)
    refused = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-new-year",
        headers=PROMOTER,
    )
    assert refused.status_code == 400
    assert "confirm" in refused.json()["detail"].lower()


def test_promote_new_year_overlays_latest_and_leaves_live_catalog(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_approved = _tree_fingerprint(APPROVED_DIR)
    live_rates = _tree_fingerprint(APPROVED_DIR.parent / "rates")
    manifest_before = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    sid, _included = _ready(admin_client, monkeypatch)
    paths = catalog_admin_paths()
    frozen_2025 = hashlib.sha256((paths.approved_dir / "2025_26.json").read_bytes()).hexdigest()
    confirm = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/confirm-new-year",
        headers=PROMOTER,
        json={"assessment_year": NEW_YA, "confirmed": True},
    )
    assert confirm.status_code == 200, confirm.text
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-new-year",
        headers=PROMOTER,
    )
    assert promoted.status_code == 200, promoted.text
    payload = json.loads((paths.approved_dir / f"{NEW_YA}.json").read_text(encoding="utf-8"))
    assert payload.get("entries")
    groups = {e["compare_group_id"] for e in payload["entries"]}
    assert "employment_income_relief" in groups
    rates = json.loads((paths.rates_dir / f"{NEW_YA}.json").read_text(encoding="utf-8"))
    assert rates["needs_manual_verification"] is True
    assert hashlib.sha256((paths.approved_dir / "2025_26.json").read_bytes()).hexdigest() == frozen_2025
    assert _tree_fingerprint(APPROVED_DIR) == live_approved
    assert _tree_fingerprint(APPROVED_DIR.parent / "rates") == live_rates
    assert hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() == manifest_before
    from adaptive_tax_app.routers import relief_interview
    from adaptive_tax_app.services import catalog_rate_engine

    assert "2027_28" not in relief_interview.SUPPORTED_YAS
    assert "2027_28" not in catalog_rate_engine.CATALOG_YAS
    phase5 = p5()
    assert payload.get("content_sha256")
    assert payload["content_sha256"] == phase5.canonical_sha256(payload)
    assert rates.get("content_sha256")
    assert rates["content_sha256"] == phase5.canonical_sha256(rates)


def test_new_year_rate_requires_sole_check(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(kind="rule", effective_from="2027-04-01", **kwargs),
    )
    pdf = _pdf_bytes("Inland Revenue (Amendment) Act, No. 99 of 2027\nRATE NEW YEAR")
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("new-year-rate.pdf", pdf, "application/pdf")},
    )
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    join_extract(job_id, timeout=10)
    _seed_year_catalog()
    included = f"{sid}:First Schedule:rule:0"
    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": included, "kind_human": "NEW_YEAR"},
    )
    routine = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
        json={},
    )
    assert routine.status_code == 400
    assert "sole-check" in routine.json()["detail"].lower()
    ok = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
        json={"sole_check": True},
    )
    assert ok.status_code == 200, ok.text
    confirm = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/confirm-new-year",
        headers=PROMOTER,
        json={"assessment_year": NEW_YA, "confirmed": True},
    )
    assert confirm.status_code == 200, confirm.text
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-new-year",
        headers=PROMOTER,
    )
    assert promoted.status_code == 200, promoted.text
    paths = catalog_admin_paths()
    rates = json.loads((paths.rates_dir / f"{NEW_YA}.json").read_text(encoding="utf-8"))
    assert rates["needs_manual_verification"] is True
    quotes = [str(item.get("quote") or "") for item in rates.get("special_formulas") or []]
    assert any("15%" in q for q in quotes)
