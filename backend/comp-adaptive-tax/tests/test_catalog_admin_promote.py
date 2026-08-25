"""Catalog-admin Step 7a: UPDATE promote writes only changed year files."""

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
from adaptive_tax_app.services.catalog_duplicate import p5, p6
from adaptive_tax_app.services.catalog_extract import join_extract

TOKEN = "test-catalog-admin-token"
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "A. Classifier",
}
BINDER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "B. Binder"}
APPROVER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "C. Approver"}
PROMOTER = {"X-Catalog-Admin-Token": TOKEN, "X-Catalog-Admin-Reviewer": "D. Promoter"}


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


def _year_path(paths: Any, key: str) -> Path:
    label, name = key.split("/", 1)
    directory = paths.approved_dir if label == "approved" else paths.rates_dir
    return directory / name


def _assert_sealed(paths: Any, keys: list[str]) -> None:
    phase5 = p5()
    for key in keys:
        payload = json.loads(_year_path(paths, key).read_text(encoding="utf-8"))
        recorded = payload.get("content_sha256")
        assert recorded, f"{key} missing content_sha256"
        assert recorded == phase5.canonical_sha256(payload)


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
    if kind == "personal":
        row = {
            "entry_id": f"{sid}:Fifth Schedule:relief:0",
            "included": True,
            "row_kind": "relief",
            "display_name": "Personal relief",
            "compare_group_id": "fifth_schedule_paragraph_2_a",
            "baseline_compare_group_id": "personal_relief",
            "section_ref": "Fifth Schedule",
            "effective_from": "2024-04-01",
            "cap_amount": cap,
            "quote": "Rs. personal-relief test quote",
            "quote_ok_full_doc": True,
            "pass2_verbatim": True,
        }
        section = "Fifth Schedule"
    elif kind == "rule":
        row = {
            "entry_id": f"{sid}:First Schedule:rule:0",
            "included": True,
            "row_kind": "rule",
            "display_name": "Tax rate for dividends",
            "description": "Tax rate for dividends second six months",
            "rule_id": "dividend-15",
            "rule_kind": "rate_rule",
            "value": "15",
            "section_ref": "First Schedule",
            "effective_from": "2022-10-01",
            "quote": "such gains and profits shall be taxed at the rate of 15%",
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
            "question_prompt": "Employment income relief is applied automatically against your employment income.",
            "input_kind": "notice",
            "help": "Extract-draft help for employment.",
            "compare_group_id": "employment_income_relief",
            "section_ref": "52",
            "effective_from": "2024-04-01",
            "cap_amount": cap,
            "quote": "April 1, 2024 employment quote",
            "quote_ok_full_doc": True,
            "pass2_verbatim": True,
        }
        section = "52"
    rows = [row]
    extra_row = None
    if kwargs.pop("with_unpublished", False) and kind == "employment":
        extra_row = {
            "entry_id": f"{sid}:Fifth Schedule:relief:new",
            "included": True,
            "row_kind": "relief",
            "display_name": "Unpublished solar bonus",
            "question_prompt": "Should this unpublished relief appear?",
            "input_kind": "yes_no_amount",
            "help": "Must stay invisible if rejected.",
            "compare_group_id": "unpublished_solar_bonus",
            "section_ref": "Fifth Schedule",
            "effective_from": "2024-04-01",
            "cap_amount": "250000",
            "quote": "unpublished bonus quote for reject test",
            "quote_ok_full_doc": True,
            "pass2_verbatim": True,
        }
        rows.append(extra_row)
    return {
        "spec_version": "1.0.0",
        "phase": 6,
        "source_doc_id": sid,
        "act_title": kwargs.get("act_title") or "Act",
        "pdf_file_name": Path(kwargs["pdf_path"]).name,
        "extracted_at": "2026-08-22T12:00:00+00:00",
        "rows": rows,
        "sections": [
            {
                "section_key": section,
                "status": "ok",
                "rows": [row],
                "row_count": 1,
                "included_count": 1,
            }
        ]
        + (
            [
                {
                    "section_key": "Fifth Schedule",
                    "status": "ok",
                    "rows": [extra_row],
                    "row_count": 1,
                    "included_count": 1,
                }
            ]
            if extra_row
            else []
        ),
        "row_count": len(rows),
        "included_count": len(rows),
    }


def _ready(
    admin_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    cap: str = "800000",
    kind: str = "employment",
    classify_as: str = "UPDATE",
) -> tuple[str, str]:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(cap=cap, kind=kind, **kwargs),
    )
    pdf = _pdf_bytes("Inland Revenue (Amendment) Act, No. 62 of 2096\nPROMOTE UPDATE BODY")
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("promote-act.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    _seed_year_catalog()
    included = (
        f"{sid}:Fifth Schedule:relief:0"
        if kind == "personal"
        else f"{sid}:First Schedule:rule:0"
        if kind == "rule"
        else f"{sid}:52:relief:0"
    )
    classified = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/classification",
        headers=HEADERS_BOTH,
        json={"row_id": included, "kind_human": classify_as},
    )
    assert classified.status_code == 200, classified.text
    bound = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
        headers=BINDER,
        json={"row_id": included, "kind": "none"},
    )
    assert bound.status_code == 200, bound.text
    approved = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
    )
    assert approved.status_code == 200, approved.text
    return sid, included


def _preview(admin_client: TestClient, sid: str) -> dict[str, Any]:
    resp = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote-preview",
        headers=PROMOTER,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_update_writes_only_changed_years_and_leaves_live_catalog(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    live_approved = _tree_fingerprint(APPROVED_DIR)
    live_rates = _tree_fingerprint(APPROVED_DIR.parent / "rates")
    manifest_before = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
    sid, _included = _ready(admin_client, monkeypatch)
    paths = catalog_admin_paths()
    frozen_before = hashlib.sha256((paths.approved_dir / "2023_24.json").read_bytes()).hexdigest()
    engine_before = hashlib.sha256((paths.approved_dir / "2024_25.json").read_bytes()).hexdigest()

    called = {"p5": 0, "p6": 0}
    monkeypatch.setattr(p5(), "cmd_promote", lambda *_a, **_k: called.__setitem__("p5", called["p5"] + 1))
    monkeypatch.setattr(p6(), "cmd_promote", lambda *_a, **_k: called.__setitem__("p6", called["p6"] + 1))

    preview = _preview(admin_client, sid)
    assert "approved/2024_25.json" in preview["year_files_that_would_be_written"]
    assert "approved/2023_24.json" not in preview["year_files_that_would_be_written"]
    assert any(n["assessment_year"] == "2024_25" for n in preview.get("engine_year_notes") or [])
    assert "catalog estimate" in (preview.get("engine_year_note") or "")
    assert "official engine" in (preview.get("engine_year_note") or "")
    assert preview["blocks_promote"] is False

    missing = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": [],
        },
    )
    assert missing.status_code == 400
    assert "Acknowledge" in missing.json()["detail"]

    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    body = promoted.json()
    assert body["promotion"]["status"] == "promoted"
    assert body["promotion"]["corpus_manifest_updated"] is False
    assert "approved/2024_25.json" in body["promotion"]["written"]
    assert "approved/2023_24.json" not in body["promotion"]["written"]
    assert called == {"p5": 0, "p6": 0}

    after_2024 = json.loads((paths.approved_dir / "2024_25.json").read_text(encoding="utf-8"))
    employment = next(
        e for e in after_2024["entries"] if e["compare_group_id"] == "employment_income_relief"
    )
    assert str(employment["cap_amount"]) == "800000"
    assert employment["source_doc_id"] == sid
    assert hashlib.sha256((paths.approved_dir / "2023_24.json").read_bytes()).hexdigest() == frozen_before
    assert hashlib.sha256((paths.approved_dir / "2024_25.json").read_bytes()).hexdigest() != engine_before
    assert _tree_fingerprint(APPROVED_DIR) == live_approved
    assert _tree_fingerprint(APPROVED_DIR.parent / "rates") == live_rates
    assert hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest() == manifest_before


def test_promote_preview_frozen_years_do_not_drift(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch)
    paths = catalog_admin_paths()
    preview = _preview(admin_client, sid)
    frozen = preview["year_files_frozen"]
    written_preview = preview["year_files_that_would_be_written"]
    assert "approved/2023_24.json" in frozen
    assert "approved/2024_25.json" in written_preview
    assert "approved/2024_25.json" not in frozen
    before = {
        key: hashlib.sha256(_year_path(paths, key).read_bytes()).hexdigest()
        for key in frozen
    }
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    after = {
        key: hashlib.sha256(_year_path(paths, key).read_bytes()).hexdigest()
        for key in frozen
    }
    assert before == after
    _assert_sealed(paths, promoted.json()["promotion"]["written"])


def test_update_does_not_open_frozen_years_for_write(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch)
    preview = _preview(admin_client, sid)
    from adaptive_tax_app.services import catalog_promote as promote_mod

    opened: list[str] = []
    real = promote_mod._write_year_file

    def spy(mod: Any, path: Path, payload: dict[str, Any]) -> None:
        opened.append(f"{path.parent.name}/{path.name}")
        return real(mod, path, payload)

    monkeypatch.setattr(promote_mod, "_write_year_file", spy)
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    assert opened
    assert "approved/2023_24.json" not in opened
    assert "approved/2024_25.json" in opened
    for key in preview["year_files_frozen"]:
        assert key not in opened


def test_stale_fingerprint_is_409(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, included = _ready(admin_client, monkeypatch)
    preview = _preview(admin_client, sid)
    stale = preview["preview_fingerprint"]
    rebound = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
        headers=BINDER,
        json={"row_id": included, "kind": "solar_panel_relief"},
    )
    assert rebound.status_code == 200
    conflict = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": stale,
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert conflict.status_code == 409
    assert "stale" in conflict.json()["detail"].lower()


def test_personal_relief_drift_blocks_promote(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch, cap="999999", kind="personal")
    preview = _preview(admin_client, sid)
    assert preview["blocks_promote"] is True
    group = preview["groups"][0]
    assert group["compare_group_id"] == "personal_relief"
    assert group["known_table_ok"] is False
    blocked = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": [],
        },
    )
    assert blocked.status_code == 400
    assert "blocked" in blocked.json()["detail"].lower()


def test_new_year_only_does_not_use_update_promote(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch, classify_as="NEW_YEAR")
    got = admin_client.get(
        f"/api/v1/catalog-admin/proposed/{sid}",
        headers={"X-Catalog-Admin-Token": TOKEN},
    )
    assert got.status_code == 200
    assert got.json()["promote_enabled"] is False
    assert "7b" in got.json()["promote_blocked_reason"]
    refused = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={"preview_fingerprint": "nope", "acknowledged_group_ids": []},
    )
    assert refused.status_code == 400


def test_rule_update_writes_rates_year_file(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch, kind="rule")
    paths = catalog_admin_paths()
    live_rates = _tree_fingerprint(APPROVED_DIR.parent / "rates")
    preview = _preview(admin_client, sid)
    assert "rates/2022_23.json" in preview["year_files_that_would_be_written"]
    assert "approved/2022_23.json" not in preview["year_files_that_would_be_written"]
    assert any(g["compare_group_id"] == "rate_rules" for g in preview["groups"])
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    assert "rates/2022_23.json" in promoted.json()["promotion"]["written"]
    data = json.loads((paths.rates_dir / "2022_23.json").read_text(encoding="utf-8"))
    quotes = [str(item.get("quote") or "") for item in data.get("special_formulas") or []]
    assert any("taxed at the rate of 15%" in q for q in quotes)
    assert _tree_fingerprint(APPROVED_DIR.parent / "rates") == live_rates


def test_rule_update_survives_approved_content_hash_drift(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live approved/*.json often have stale content_sha256; that must not block a rates write."""
    sid, _included = _ready(admin_client, monkeypatch, kind="rule")
    paths = catalog_admin_paths()
    drifted = paths.approved_dir / "2018_19.json"
    payload = json.loads(drifted.read_text(encoding="utf-8"))
    payload["content_sha256"] = "0" * 64
    drifted.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    before = drifted.read_bytes()
    preview = _preview(admin_client, sid)
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    assert "rates/2022_23.json" in promoted.json()["promotion"]["written"]
    assert drifted.read_bytes() == before


def test_immutability_failure_rolls_back_writes(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid, _included = _ready(admin_client, monkeypatch)
    paths = catalog_admin_paths()
    before = hashlib.sha256((paths.approved_dir / "2024_25.json").read_bytes()).hexdigest()
    preview = _preview(admin_client, sid)
    from adaptive_tax_app.services import catalog_promote as promote_mod

    real = promote_mod._assert_frozen_unchanged
    calls = {"n": 0}

    def boom(baseline: dict[str, str], paths: Any) -> list[str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return real(baseline, paths)
        return ["approved/2018_19.json hash changed (deadbeef... -> cafebabe...)"]

    monkeypatch.setattr(promote_mod, "_assert_frozen_unchanged", boom)
    failed = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert failed.status_code == 400
    assert "rolled back" in failed.json()["detail"].lower()
    assert hashlib.sha256((paths.approved_dir / "2024_25.json").read_bytes()).hexdigest() == before
    proposal = json.loads((paths.proposed_dir / f"{sid}.json").read_text(encoding="utf-8"))
    assert proposal.get("promotion_status") in (None, "")


def test_promote_refreshes_oe_index_over_http(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []

    def _spy() -> dict[str, Any]:
        payload = {"ok": True, "url": "http://127.0.0.1:8008/api/v1/index/refresh"}
        calls.append(payload)
        return payload

    monkeypatch.setattr(
        "adaptive_tax_app.services.catalog_promote.notify_oe_index_refresh", _spy
    )
    sid, included = _ready(admin_client, monkeypatch)
    admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/question-fields",
        headers=BINDER,
        json={
            "row_id": included,
            "display_name": "Employment relief (accepted)",
            "question_prompt": "Accepted employment question for the taxpayer.",
            "input_kind": "notice",
            "help": "Accepted help.",
            "compare_group_id": "employment_income_relief",
        },
    )
    preview = _preview(admin_client, sid)
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    assert calls, "promote must HTTP-refresh Optimization and Explainable"
    assert promoted.json()["promotion"]["index_refresh"]["ok"] is True
    paths = catalog_admin_paths()
    year = json.loads((paths.approved_dir / "2024_25.json").read_text(encoding="utf-8"))
    employment = next(
        e for e in year["entries"] if e["compare_group_id"] == "employment_income_relief"
    )
    assert employment["question_prompt"] == "Accepted employment question for the taxpayer."
    assert employment["help"] == "Accepted help."
    assert employment["display_name"] == "Employment relief (accepted)"
    assert employment["cap_amount"] == "800000"


def test_rejected_row_never_promoted(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(catalog_classify, "harvest_act_impl", _empty_harvest)
    monkeypatch.setattr(
        catalog_extract,
        "extract_proposal_impl",
        lambda **kwargs: _fake_proposal(with_unpublished=True, **kwargs),
    )
    pdf = _pdf_bytes("Inland Revenue (Amendment) Act, No. 63 of 2096\nREJECT UNPUBLISHED")
    uploaded = admin_client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": ("reject-act.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 200, uploaded.text
    job_id = uploaded.json()["job_id"]
    sid = uploaded.json()["suggested_source_doc_id"]
    start = admin_client.post(f"/api/v1/catalog-admin/jobs/{job_id}/extract", headers=HEADERS_BOTH)
    assert start.status_code == 202
    join_extract(job_id, timeout=10)
    _seed_year_catalog()
    included = f"{sid}:52:relief:0"
    rejected = f"{sid}:Fifth Schedule:relief:new"
    for row_id in (included, rejected):
        classified = admin_client.post(
            f"/api/v1/catalog-admin/proposed/{sid}/classification",
            headers=HEADERS_BOTH,
            json={"row_id": row_id, "kind_human": "UPDATE"},
        )
        assert classified.status_code == 200, classified.text
        bound = admin_client.post(
            f"/api/v1/catalog-admin/proposed/{sid}/engine-binding",
            headers=BINDER,
            json={"row_id": row_id, "kind": "none"},
        )
        assert bound.status_code == 200, bound.text
    approved = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{included}/approve",
        headers=APPROVER,
    )
    assert approved.status_code == 200, approved.text
    refused = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/rows/{rejected}/reject",
        headers=APPROVER,
        json={"reason": "not for the taxpayer"},
    )
    assert refused.status_code == 200, refused.text
    preview = _preview(admin_client, sid)
    promoted = admin_client.post(
        f"/api/v1/catalog-admin/proposed/{sid}/promote",
        headers=PROMOTER,
        json={
            "preview_fingerprint": preview["preview_fingerprint"],
            "acknowledged_group_ids": preview["needs_gap_ack_group_ids"],
        },
    )
    assert promoted.status_code == 200, promoted.text
    paths = catalog_admin_paths()
    for path in paths.approved_dir.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        groups = {e.get("compare_group_id") for e in payload.get("entries") or []}
        assert "unpublished_solar_bonus" not in groups
        prompts = {e.get("question_prompt") for e in payload.get("entries") or []}
        assert "Should this unpublished relief appear?" not in prompts


def test_notify_oe_index_refresh_posts_http(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from adaptive_tax_app.services.catalog_promote import notify_oe_index_refresh

    captured: dict[str, str] = {}

    class _FakeClient:
        def __init__(self, timeout: float | None = None) -> None:
            self.timeout = timeout

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, *_exc: object) -> None:
            return None

        def post(self, url: str) -> httpx.Response:
            captured["url"] = url
            return httpx.Response(200, json={"status": "ok", "years": ["2025_26"]})

    monkeypatch.setattr(httpx, "Client", _FakeClient)
    result = notify_oe_index_refresh()
    assert result["ok"] is True
    assert captured["url"].endswith("/api/v1/index/refresh")
    assert "adaptive_tax_app" not in captured["url"]


