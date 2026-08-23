"""Catalog-admin Step 2: hash-first duplicate check (no Pass 1 / LLM)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from adaptive_tax_app.config import get_adaptive_tax_settings
from adaptive_tax_app.main import create_app
from adaptive_tax_app.services.catalog_admin_store import (
    catalog_admin_paths,
    new_job_id,
    now_iso,
    save_job,
)
from adaptive_tax_app.services.catalog_duplicate import (
    ActIdentity,
    classify_duplicate,
    format_act_label,
    map_identity_to_source_doc_ids,
    mint_source_doc_id,
    parse_act_identity,
    sha256_normalized,
)
from backend.shared.config.settings import PROJECT_ROOT

TOKEN = "test-catalog-admin-token"
HEADERS_BOTH = {
    "X-Catalog-Admin-Token": TOKEN,
    "X-Catalog-Admin-Reviewer": "A. Reviewer",
}
MANIFEST = PROJECT_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"


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


def _upload(client: TestClient, pdf: bytes, name: str = "unique-act.pdf"):
    return client.post(
        "/api/v1/catalog-admin/upload",
        headers=HEADERS_BOTH,
        files={"file": (name, pdf, "application/pdf")},
    )


def test_parse_act_identity_header_and_short_title() -> None:
    header = "Inland Revenue (Amendment) Act, No. 2 of 2025\nbody"
    ident = parse_act_identity(header)
    assert ident is not None
    assert ident.act_no == "02"
    assert ident.act_year == "2025"
    assert ident.source == "running_header"
    assert ident.parsed_from == "running_header"
    assert "No. 2 of 2025" in ident.quote
    cited = "This Act may be cited as the Inland Revenue (Amendment) Act, No. 11 of 2026."
    ident2 = parse_act_identity(cited)
    assert ident2 is not None
    assert ident2.source == "short_title"
    assert ident2.parsed_from == "short_title"
    assert ident2.act_no == "11"
    from_file = parse_act_identity("no identity here", filename="IR_Act_No_45-2022_E.pdf")
    assert from_file is not None
    assert from_file.source == "filename"
    assert from_file.act_no == "45"
    assert from_file.act_year == "2022"


def test_map_identity_uses_manifest_title_not_llm() -> None:
    docs = json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]
    ident = ActIdentity(
        act_no="02", act_year="2025", label=format_act_label("02", "2025"), source="t"
    )
    assert map_identity_to_source_doc_ids(ident, docs) == ["ird-amend-2025-02"]
    base = ActIdentity(
        act_no="24", act_year="2017", label=format_act_label("24", "2017"), source="t"
    )
    assert "ird-ira-2017-base" in map_identity_to_source_doc_ids(base, docs)


def test_mint_avoids_existing_and_matched_id() -> None:
    ident = ActIdentity(act_no="02", act_year="2025", label="Act No. 02 of 2025", source="t")
    assert mint_source_doc_id(ident, set()) == "ird-amend-2025-02"
    minted = mint_source_doc_id(
        ident, {"ird-amend-2025-02"}, text_sha256="abcdef12", avoid="ird-amend-2025-02"
    )
    assert minted != "ird-amend-2025-02"
    assert minted.startswith("ird-amend-2025-02-")


def test_classify_hash_corpus_is_case_a() -> None:
    ident = ActIdentity(act_no="02", act_year="2025", label="Act No. 02 of 2025", source="t")
    decision = classify_duplicate(
        text_sha256="aaa",
        tables_sha256="bbb",
        pdf_sha256="ccc",
        filename="other.pdf",
        identity=ident,
        corpus_rows=[
            {
                "source_doc_id": "ird-amend-2025-02",
                "file_name": "IR_Act_No_02-2025_E.pdf",
                "text_sha256": "aaa",
                "extracted_on": "2026-08-21T16:36:19+00:00",
            }
        ],
        proposals=[],
        jobs=[],
        documents=[],
        taken={"ird-amend-2025-02"},
        warnings=[],
        index_stale=False,
    )
    assert decision.case == "a"
    assert decision.match_kind == "text_hash"
    assert "ird-amend-2025-02" in decision.message
    assert "No action taken" in decision.message
    assert decision.suggested_source_doc_id != "ird-amend-2025-02"
    assert "treat_as_new_source" in decision.actions


def test_classify_filename_fallback_is_weaker_case_a() -> None:
    decision = classify_duplicate(
        text_sha256="nomatch",
        tables_sha256="",
        pdf_sha256="",
        filename="IR_Act_No_02-2025_E.pdf",
        identity=None,
        corpus_rows=[
            {
                "source_doc_id": "ird-amend-2025-02",
                "file_name": "IR_Act_No_02-2025_E.pdf",
                "text_sha256": "other",
                "extracted_on": "2026-01-01",
            }
        ],
        proposals=[],
        jobs=[],
        documents=[],
        taken=set(),
        warnings=[],
        index_stale=False,
    )
    assert decision.case == "a"
    assert decision.match_kind == "filename"


def test_classify_proposed_hash_is_case_b_not_failed() -> None:
    ident = ActIdentity(act_no="99", act_year="2099", label="Act No. 99 of 2099", source="t")
    decision = classify_duplicate(
        text_sha256="prop",
        tables_sha256="",
        pdf_sha256="",
        filename="new.pdf",
        identity=ident,
        corpus_rows=[],
        proposals=[
            {
                "source_doc_id": "ird-amend-2099-99",
                "text_sha256": "prop",
                "extracted_at": "2026-08-22T10:00:00+00:00",
            }
        ],
        jobs=[],
        documents=[],
        taken=set(),
        warnings=[],
        index_stale=False,
    )
    assert decision.case == "b"
    assert decision.review_path == "/adaptive-tax/catalog-admin/review/ird-amend-2099-99"


def test_classify_in_flight_is_b2_failed_is_prior_failed() -> None:
    inflight = classify_duplicate(
        text_sha256="jobhash",
        tables_sha256="",
        pdf_sha256="",
        filename="x.pdf",
        identity=None,
        corpus_rows=[],
        proposals=[],
        jobs=[{"id": "j1", "status": "uploaded", "text_sha256": "jobhash", "created_at": "t"}],
        documents=[],
        taken=set(),
        warnings=[],
        index_stale=False,
    )
    assert inflight.case == "b2"
    failed = classify_duplicate(
        text_sha256="jobhash",
        tables_sha256="",
        pdf_sha256="",
        filename="x.pdf",
        identity=None,
        corpus_rows=[],
        proposals=[],
        jobs=[{"id": "j2", "status": "failed", "text_sha256": "jobhash", "created_at": "t"}],
        documents=[],
        taken=set(),
        warnings=[],
        index_stale=False,
    )
    assert failed.case == "prior_failed"
    assert failed.job_id == "j2"


def test_classify_identity_hit_hash_miss_is_case_d() -> None:
    ident = ActIdentity(act_no="02", act_year="2025", label="Act No. 02 of 2025", source="t")
    decision = classify_duplicate(
        text_sha256="different",
        tables_sha256="",
        pdf_sha256="",
        filename="rescanned.pdf",
        identity=ident,
        corpus_rows=[
            {
                "source_doc_id": "ird-amend-2025-02",
                "file_name": "IR_Act_No_02-2025_E.pdf",
                "text_sha256": "original",
                "act_no": "02",
                "act_year": "2025",
            }
        ],
        proposals=[],
        jobs=[],
        documents=[
            {
                "source_doc_id": "ird-amend-2025-02",
                "title": "Inland Revenue Amendment Act No. 02 of 2025",
            }
        ],
        taken={"ird-amend-2025-02"},
        warnings=[],
        index_stale=False,
    )
    assert decision.case == "d"
    assert decision.matched_source_doc_id == "ird-amend-2025-02"
    assert decision.suggested_source_doc_id != "ird-amend-2025-02"
    assert "treat_as_new_source" in decision.actions
    assert "cancel" in decision.actions


def test_upload_case_none_and_missing_token(admin_client: TestClient) -> None:
    denied = admin_client.post(
        "/api/v1/catalog-admin/upload",
        files={"file": ("x.pdf", _pdf_bytes("x"), "application/pdf")},
    )
    assert denied.status_code == 401
    pdf = _pdf_bytes(
        "Inland Revenue (Amendment) Act, No. 99 of 2099\nUNIQUE BODY FOR NONE CASE 7f3a"
    )
    resp = _upload(admin_client, pdf, "brand-new-act.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case"] == "none"
    assert body["suggested_source_doc_id"] == "ird-amend-2099-99"
    assert body["job"]["status"] == "uploaded"
    assert body["text_sha256"]
    assert body["pdf_sha256"]
    assert "edit_source_doc_id" in body["actions"]


def test_upload_case_a_text_hash_from_index(admin_client: TestClient) -> None:
    from adaptive_tax_app.services.catalog_duplicate import fingerprints_from_path

    pdf = _pdf_bytes("corpus clone unique stream ZZZ99")
    paths = catalog_admin_paths()
    paths.uploads_dir.mkdir(parents=True)
    pdf_path = paths.uploads_dir / "clone.pdf"
    pdf_path.write_bytes(pdf)
    text_sha, tables_sha = fingerprints_from_path(pdf_path)
    paths.hash_index.write_text(
        json.dumps(
            {
                "spec_version": "1.0.0",
                "indexed_at": "2099-01-01T00:00:00+00:00",
                "documents": [
                    {
                        "source_doc_id": "ird-amend-2025-02",
                        "file_name": "IR_Act_No_02-2025_E.pdf",
                        "text_sha256": text_sha,
                        "tables_sha256": tables_sha,
                        "act_no": "02",
                        "act_year": "2025",
                        "indexed_at": "2099-01-01T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    resp = _upload(admin_client, pdf, "clone.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case"] == "a"
    assert body["match_kind"] == "text_hash"
    assert body["matched_source_doc_id"] == "ird-amend-2025-02"
    assert body["job"]["status"] == "paused_rescan"
    assert body["job_id"]
    assert "treat_as_new_source" in body["actions"]
    treated = admin_client.post(
        f"/api/v1/catalog-admin/jobs/{body['job_id']}/treat-as-new-source",
        headers=HEADERS_BOTH,
    )
    assert treated.status_code == 200, treated.text
    assert treated.json()["case"] == "none"
    assert treated.json()["suggested_source_doc_id"] != "ird-amend-2025-02"
    assert treated.json()["job"]["status"] == "uploaded"


def test_upload_filename_fallback_corpus(admin_client: TestClient) -> None:
    pdf = _pdf_bytes("unrelated body that will not hash-match the corpus 111")
    resp = _upload(admin_client, pdf, "IR_Act_No_02-2025_E.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case"] == "a"
    assert body["match_kind"] == "filename"
    assert body["matched_source_doc_id"] == "ird-amend-2025-02"
    assert body["job"]["status"] == "paused_rescan"
    assert "treat_as_new_source" in body["actions"]


def test_upload_case_b_complete_proposed(admin_client: TestClient) -> None:
    from adaptive_tax_app.services.catalog_duplicate import p4

    pdf = _pdf_bytes("Watcher-like unique stream for proposed match XYZ")
    paths = catalog_admin_paths()
    paths.proposed_dir.mkdir(parents=True)
    paths.uploads_dir.mkdir(parents=True)
    pdf_path = paths.uploads_dir / "pending.pdf"
    pdf_path.write_bytes(pdf)
    phase4 = p4()
    act = phase4.read_act_text(pdf_path)
    text_sha = sha256_normalized(act.stream, phase4.normalize_for_match)
    (paths.proposed_dir / "ird-amend-2099-01.json").write_text(
        json.dumps(
            {
                "source_doc_id": "ird-amend-2099-01",
                "text_sha256": text_sha,
                "extracted_at": "2026-08-22T12:00:00+00:00",
                "pdf_file_name": "pending.pdf",
            }
        ),
        encoding="utf-8",
    )
    resp = _upload(admin_client, pdf, "pending.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case"] == "b"
    assert body["review_path"] == "/adaptive-tax/catalog-admin/review/ird-amend-2099-01"
    assert body["job"] is None


def test_upload_case_b2_and_failed_excluded(admin_client: TestClient) -> None:
    from adaptive_tax_app.services.catalog_duplicate import p4

    pdf = _pdf_bytes("In-flight unique stream ABCDE")
    paths = catalog_admin_paths()
    paths.uploads_dir.mkdir(parents=True)
    pdf_path = paths.uploads_dir / "inflight.pdf"
    pdf_path.write_bytes(pdf)
    phase4 = p4()
    act = phase4.read_act_text(pdf_path)
    text_sha = sha256_normalized(act.stream, phase4.normalize_for_match)
    job = {
        "id": new_job_id(),
        "status": "uploaded",
        "text_sha256": text_sha,
        "pdf_sha256": "x",
        "original_filename": "inflight.pdf",
        "created_at": now_iso(),
    }
    save_job(job, paths)
    resp = _upload(admin_client, pdf, "inflight-again.pdf")
    assert resp.status_code == 200, resp.text
    assert resp.json()["case"] == "b2"
    assert resp.json()["job_id"] == job["id"]

    failed_pdf = _pdf_bytes("Failed unique stream FGHIJ")
    failed_path = paths.uploads_dir / "failed.pdf"
    failed_path.write_bytes(failed_pdf)
    act_f = phase4.read_act_text(failed_path)
    failed_sha = sha256_normalized(act_f.stream, phase4.normalize_for_match)
    failed = {
        "id": new_job_id(),
        "status": "failed",
        "text_sha256": failed_sha,
        "error": "llm timeout",
        "created_at": now_iso(),
    }
    save_job(failed, paths)
    resp_f = _upload(admin_client, failed_pdf, "failed-again.pdf")
    assert resp_f.status_code == 200, resp_f.text
    assert resp_f.json()["case"] == "prior_failed"
    assert resp_f.json()["job_id"] == failed["id"]
    queue = admin_client.get(
        "/api/v1/catalog-admin/queue",
        headers={"X-Catalog-Admin-Token": TOKEN},
    )
    assert queue.status_code == 200
    failed_ids = {row["id"] for row in queue.json()["failed_jobs"]}
    assert failed["id"] in failed_ids
    pending_ids = {row["source_doc_id"] for row in queue.json()["proposals"]}
    assert failed["id"] not in pending_ids


def test_upload_case_d_cancel_and_treat_as_new(admin_client: TestClient) -> None:
    pdf = _pdf_bytes(
        "Inland Revenue (Amendment) Act, No. 02 of 2025\nRESCAN COPY different file body 99aa"
    )
    resp = _upload(admin_client, pdf, "rescanned-copy.pdf")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["case"] == "d"
    assert body["matched_source_doc_id"] == "ird-amend-2025-02"
    assert body["job"]["status"] == "paused_rescan"
    job_id = body["job_id"]

    treated = admin_client.post(
        f"/api/v1/catalog-admin/jobs/{job_id}/treat-as-new-source",
        headers=HEADERS_BOTH,
    )
    assert treated.status_code == 200, treated.text
    treated_body = treated.json()
    assert treated_body["case"] == "none"
    new_id = treated_body["suggested_source_doc_id"]
    assert new_id != "ird-amend-2025-02"
    assert treated_body["job"]["status"] == "uploaded"
    assert treated_body["job"]["source_doc_id"] == new_id
    blocked = admin_client.post(
        f"/api/v1/catalog-admin/jobs/{job_id}/source-doc-id",
        headers=HEADERS_BOTH,
        json={"source_doc_id": "ird-amend-2025-02"},
    )
    assert blocked.status_code == 400
    assert "replace" in blocked.json()["detail"].lower() or "existing" in blocked.json()["detail"].lower()

    pdf2 = _pdf_bytes(
        "Inland Revenue (Amendment) Act, No. 02 of 2025\nANOTHER RESCAN body 88bb"
    )
    paused = _upload(admin_client, pdf2, "rescanned-copy-2.pdf")
    assert paused.json()["case"] == "d"
    cancel_id = paused.json()["job_id"]
    discarded = admin_client.post(
        f"/api/v1/catalog-admin/jobs/{cancel_id}/discard",
        headers=HEADERS_BOTH,
    )
    assert discarded.status_code == 200
    assert discarded.json()["status"] == "discarded"
    again = _upload(admin_client, pdf2, "rescanned-copy-2.pdf")
    assert again.json()["case"] == "d"


def test_refresh_does_not_rewrite_manifest(admin_client: TestClient) -> None:
    before = MANIFEST.read_bytes()
    mtime = MANIFEST.stat().st_mtime
    resp = admin_client.post(
        "/api/v1/catalog-admin/corpus-hashes/refresh",
        headers=HEADERS_BOTH,
    )
    assert resp.status_code == 200, resp.text
    assert MANIFEST.read_bytes() == before
    assert MANIFEST.stat().st_mtime == mtime
    paths = catalog_admin_paths()
    assert paths.hash_index.is_file()
    assert paths.hash_index.resolve() != MANIFEST.resolve()
    index = json.loads(paths.hash_index.read_text(encoding="utf-8"))
    assert "Never rewrite corpus_manifest.json" in index["note"]


def test_upload_rejects_non_pdf(admin_client: TestClient) -> None:
    resp = _upload(admin_client, b"not-a-pdf", "note.txt")
    assert resp.status_code == 400
