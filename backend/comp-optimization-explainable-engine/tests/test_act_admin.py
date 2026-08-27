"""Act-admin upload, review, impact preview, activation, and compiler semantics."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from db.year_views import OeEnginePromotedEntity, OeEnginePromotedRun, OeEngineYearRelief
from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.schemas.extract import ExtractRun
from oe_engine_app.services.act_admin_duplicate import (
    ActAdminUploadError,
    check_duplicate,
    ingest_upload,
    validate_pdf_bytes,
)
from oe_engine_app.services.act_admin_review import (
    ReviewValidationError,
    activate_draft,
    catalog_preview,
    impact_preview,
    patch_row,
    reset_activation,
    review_payload,
    review_ready,
)
from oe_engine_app.services.act_admin_extract import delete_job
from oe_engine_app.services.act_admin_store import (
    act_admin_paths,
    job_path,
    save_draft as _save_draft,
    save_job,
)
from oe_engine_app.services.compiler import (
    compile_maps,
    derive_assessment_years,
    recompile_year_views,
    validate_rate_band_set,
)
from oe_engine_app.services.fixtures import load_extract_fixture, seed_act_document
from oe_engine_app.services.terminus import PromoteForbidden, promote_act_run, unpromote_source_doc
from oe_engine_app.services.year_store import list_years


def _admin_headers(token: str = "test-token", reviewer: str = "Tester") -> dict[str, str]:
    return {
        "X-Oe-Act-Admin-Token": token,
        "X-Oe-Act-Admin-Reviewer": reviewer,
    }


@pytest.fixture()
def act_admin_work_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OE_ENGINE_ACT_ADMIN_WORK_DIR", str(tmp_path))
    monkeypatch.setenv("OE_ENGINE_ACT_ADMIN_TOKEN", "test-token")
    get_oe_engine_settings.cache_clear()
    yield tmp_path
    get_oe_engine_settings.cache_clear()


def test_act_admin_token_gate_503(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OE_ENGINE_ACT_ADMIN_TOKEN", "")
    get_oe_engine_settings.cache_clear()
    response = client.get("/act-admin/session", headers=_admin_headers())
    assert response.status_code == 503
    get_oe_engine_settings.cache_clear()


def test_act_admin_token_gate_ok(client, act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    response = client.get("/act-admin/session", headers=_admin_headers())
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_validate_pdf_rejects_empty() -> None:
    with pytest.raises(ActAdminUploadError):
        validate_pdf_bytes(b"")


def test_upload_rejects_non_pdf(db_session: Session, act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    with pytest.raises(ActAdminUploadError):
        ingest_upload(
            db_session,
            raw=b"not-a-pdf",
            filename="bad.txt",
            reviewer="Tester",
        )


def test_review_and_activate_fixture_draft(
    db_session: Session,
    act_admin_work_dir: Path,
) -> None:
    run = load_extract_fixture("act_extract_2025.json")
    seed_act_document(db_session, source_doc_id=run.source_doc_id)
    draft = run.model_dump(mode="json")
    draft["job_id"] = "job-fixture"
    for entity in draft["entities"]:
        if entity.get("entity_kind") in {"relief", "rate_band"} and entity.get("included"):
            entity["review_status"] = "accepted"
            entity["quote_ok_window"] = True
            entity["quote_ok_full_doc"] = True
    _save_draft(draft, act_admin_paths())
    payload = review_payload(run.source_doc_id)
    assert payload["activate_allowed"] is True
    preview = impact_preview(db_session, run.source_doc_id)
    assert preview["fingerprint"]
    result = activate_draft(
        db_session,
        run.source_doc_id,
        fingerprint=preview["fingerprint"],
        reviewer="Tester",
    )
    db_session.commit()
    assert result["entity_count"] >= 1
    rows = db_session.query(OeEngineYearRelief).filter(
        OeEngineYearRelief.source_doc_id == run.source_doc_id
    )
    assert rows.count() >= 1


def test_activate_rejects_stale_fingerprint(
    db_session: Session,
    act_admin_work_dir: Path,
) -> None:
    run = load_extract_fixture("act_extract_2025.json")
    seed_act_document(db_session, source_doc_id=run.source_doc_id)
    draft = run.model_dump(mode="json")
    for entity in draft["entities"]:
        if entity.get("entity_kind") in {"relief", "rate_band"} and entity.get("included"):
            entity["review_status"] = "accepted"
            entity["quote_ok_window"] = True
            entity["quote_ok_full_doc"] = True
    _save_draft(draft, act_admin_paths())
    preview = impact_preview(db_session, run.source_doc_id)
    first_id = str(draft["entities"][0]["entry_id"])
    patch_row(
        run.source_doc_id,
        first_id,
        reviewer="Tester",
        patch={"cap_amount": "9999999"},
    )
    with pytest.raises(ReviewValidationError, match="Stale impact preview"):
        activate_draft(
            db_session,
            run.source_doc_id,
            fingerprint=preview["fingerprint"],
            reviewer="Tester",
        )


def test_promote_requires_review_when_flagged(db_session: Session) -> None:
    run = load_extract_fixture("act_extract_2025.json")
    seed_act_document(db_session, source_doc_id=run.source_doc_id)
    with pytest.raises(PromoteForbidden, match="accepted"):
        promote_act_run(db_session, run, require_review_accepted=True)


def test_repeal_removes_relief_from_later_year(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    base = load_extract_fixture("act_extract_2025.json")
    relief = next(e for e in base.entities if e.get("entity_kind") == "relief")
    group = str(relief.get("compare_group_id"))
    rows = [
        OeEnginePromotedEntity(
            source_doc_id="oee-act-base",
            extraction_run_id="base",
            entity_kind="relief",
            compare_group_id=group,
            entry_id="base-relief",
            payload_json={
                **relief,
                "source_doc_id": "oee-act-base",
                "effective_from": "2018-04-01",
                "change_action": "add",
            },
            payload_hash="h1",
            promoted_at=now,
        ),
        OeEnginePromotedEntity(
            source_doc_id="oee-act-repeal",
            extraction_run_id="repeal",
            entity_kind="relief",
            compare_group_id=group,
            entry_id="repeal-relief",
            payload_json={
                **relief,
                "source_doc_id": "oee-act-repeal",
                "effective_from": "2024-04-01",
                "change_action": "repeal",
            },
            payload_hash="h2",
            promoted_at=now,
        ),
    ]
    reliefs, _rates = compile_maps(rows)
    assert group not in {r.get("compare_group_id") for r in reliefs.get("2024_25", [])}


def test_derive_assessment_years_does_not_add_2026_27(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    rows = [
        OeEnginePromotedEntity(
            source_doc_id="oee-act-11-2026",
            extraction_run_id="x",
            entity_kind="relief",
            compare_group_id="solar_panel_relief",
            entry_id="future",
            payload_json={
                "entity_kind": "relief",
                "compare_group_id": "solar_panel_relief",
                "effective_from": "2026-04-01",
                "engine_scope": "individual",
            },
            payload_hash="h",
            promoted_at=now,
        )
    ]
    years = derive_assessment_years(rows)
    assert "2026_27" not in years
    assert years[-1] == "2025_26"


def test_rate_band_validation_detects_gap() -> None:
    errors = validate_rate_band_set(
        [
            {
                "entity_kind": "rate_band",
                "band_index": 1,
                "lower": "0",
                "upper": "1000000",
                "rate_percent": "6",
                "applies_to": "individual",
            },
            {
                "entity_kind": "rate_band",
                "band_index": 2,
                "lower": "2000000",
                "upper": None,
                "rate_percent": "12",
                "applies_to": "individual",
            },
        ]
    )
    assert any("Gap or overlap" in err for err in errors)


def test_rate_band_validation_allows_inclusive_upper_to_next_lower() -> None:
    errors = validate_rate_band_set(
        [
            {
                "entity_kind": "rate_band",
                "band_index": 1,
                "lower": "0",
                "upper": "600000",
                "rate_percent": "4",
                "applies_to": "individual",
            },
            {
                "entity_kind": "rate_band",
                "band_index": 2,
                "lower": "600001",
                "upper": None,
                "rate_percent": "8",
                "applies_to": "individual",
            },
        ]
    )
    assert errors == []


def test_act_admin_extract_bypasses_phase6_guard(
    db_session: Session,
    act_admin_work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Act-admin live extract must not hit the CLI-only Phase 6 guard."""
    from oe_engine_app.services.act_admin_store import save_job
    from oe_engine_app.services.act_admin_extract import run_extract_job
    from oe_engine_app.services.fixtures import seed_act_document

    job_id = "job-phase6-guard"
    sid = "oee-act-guard-test"
    seed_act_document(db_session, source_doc_id=sid)
    db_session.commit()
    pdf_path = act_admin_work_dir / "uploads" / f"{job_id}__test.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4 minimal")
    save_job(
        {
            "id": job_id,
            "status": "uploaded",
            "source_doc_id": sid,
            "original_filename": "test.pdf",
            "storage_path": pdf_path.as_posix(),
            "pdf_sha256": "abc",
            "reviewer": "Tester",
            "uploaded_at": "2026-01-01T00:00:00+00:00",
        },
        act_admin_paths(),
    )
    seen: dict[str, bool] = {}

    def _fake_run_extract(*_args, **kwargs):
        seen["act_admin"] = kwargs.get("act_admin")
        raise RuntimeError("stop-after-guard")

    monkeypatch.setattr("oe_engine_app.services.act_admin_extract.run_extract", _fake_run_extract)
    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract.ingest_uploaded_pdf",
        lambda *_a, **_k: type("R", (), {"status": "ok", "chunk_count": 1, "embedding_usd": 0.0})(),
    )
    monkeypatch.setattr("oe_engine_app.services.act_admin_extract._build_embedder", lambda: object())
    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract._build_llm",
        lambda _ledger: object(),
    )
    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract.load_phase6_prior",
        lambda: 0.0,
    )

    job = run_extract_job(job_id, paths=act_admin_paths())
    assert seen.get("act_admin") is True
    assert job["status"] == "failed"
    assert job["error"] == "stop-after-guard"


def test_run_extract_job_reuses_canonical_doc_when_sha_skipped(
    act_admin_work_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ingest skips duplicate sha256, extract must use the existing corpus doc id."""
    from oe_engine_app.services.act_admin_extract import run_extract_job
    from oe_engine_app.services.act_admin_store import load_draft, save_job
    from oe_engine_app.services.ingest import IngestResult

    job_id = "job-sha-skip"
    sid = "oee-act-4-2023"
    canonical = "oee-act-existing"
    pdf_path = act_admin_work_dir / "uploads" / f"{job_id}__test.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF-1.4 minimal")
    save_job(
        {
            "id": job_id,
            "status": "uploaded",
            "source_doc_id": sid,
            "original_filename": "IR_Act_No_04_2023_E.pdf",
            "storage_path": pdf_path.as_posix(),
            "pdf_sha256": "abc",
            "reviewer": "Tester",
            "uploaded_at": "2026-01-01T00:00:00+00:00",
        },
        act_admin_paths(),
    )
    seen: dict[str, str] = {}

    def _fake_ingest(*_a, **_k):
        return IngestResult(
            source_doc_id=canonical,
            status="skipped_sha256",
            sha256="abc",
            chunk_count=10,
        )

    def _fake_run_extract(*_a, **kwargs):
        seen["extract_sid"] = kwargs["source_doc_id"]
        return ExtractRun(
            extraction_run_id="run-sha-skip",
            source_doc_id=canonical,
            tier="act",
            terminus="review_then_promote",
            model="test",
            entities=[{"source_doc_id": canonical, "entity_kind": "relief", "included": True}],
        )

    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract.ingest_uploaded_pdf",
        _fake_ingest,
    )
    monkeypatch.setattr("oe_engine_app.services.act_admin_extract.run_extract", _fake_run_extract)
    monkeypatch.setattr("oe_engine_app.services.act_admin_extract._build_embedder", lambda: object())
    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract._build_llm",
        lambda _ledger: object(),
    )
    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract.load_phase6_prior",
        lambda: 0.0,
    )
    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract.write_extract_run",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "oe_engine_app.services.act_admin_extract.SpendLedger.dump",
        lambda self: None,
    )

    job = run_extract_job(job_id, paths=act_admin_paths())
    assert seen["extract_sid"] == canonical
    assert job["ingest_reused_from"] == canonical
    assert job["status"] == "extracted"
    draft = load_draft(sid, act_admin_paths())
    assert draft is not None
    assert draft["source_doc_id"] == sid
    assert draft["entities"][0]["source_doc_id"] == sid


def test_review_ready_ignores_out_of_scope_pending(act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    draft = {
        "source_doc_id": "oee-fixture-scope",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "ind-1",
                "compare_group_id": "personal_relief",
                "included": True,
                "review_status": "accepted",
                "engine_scope": "individual",
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "cap_amount": "500000",
                "effective_from": "2017-04-01",
            },
            {
                "entity_kind": "relief",
                "entry_id": "ent-1",
                "compare_group_id": "donation_to_charitable_institution",
                "included": True,
                "review_status": "pending",
                "engine_scope": "other",
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "eligibility": {"text": "entities making donations"},
                "cap_amount": "500000",
                "effective_from": "2017-04-01",
            },
        ],
    }
    ready = review_ready(draft)
    assert ready["out_of_scope_count"] == 1
    assert ready["pending_count"] == 0
    assert ready["activate_allowed"] is True


def test_patch_row_http(client, act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    draft = {
        "source_doc_id": "oee-fixture-act-2025",
        "extraction_run_id": "fixture",
        "tier": "act",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "r1",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar",
                "quote": "solar panels relief capped",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
            }
        ],
    }
    _save_draft(draft, act_admin_paths())
    response = client.patch(
        "/act-admin/review/oee-fixture-act-2025/rows/r1",
        json={"review_status": "accepted"},
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1


def test_reject_then_reapprove_updates_counts(act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    draft = {
        "source_doc_id": "oee-fixture-act-2025",
        "extraction_run_id": "fixture",
        "tier": "act",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "r1",
                "compare_group_id": "foreign_currency_income_relief",
                "display_name": "Foreign currency income relief",
                "quote": "foreign currency income relief capped",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
                "cap_amount": "15000000",
                "effective_from": "2017-04-01",
            }
        ],
    }
    _save_draft(draft, act_admin_paths())
    rejected = patch_row(
        "oee-fixture-act-2025",
        "r1",
        reviewer="tester",
        patch={"review_status": "rejected"},
    )
    assert rejected["rejected_count"] == 1
    assert rejected["accepted_count"] == 0
    assert rejected["activate_allowed"] is False

    approved = patch_row(
        "oee-fixture-act-2025",
        "r1",
        reviewer="tester",
        patch={"review_status": "accepted", "included": True},
    )
    assert approved["rejected_count"] == 0
    assert approved["accepted_count"] == 1
    assert approved["activate_allowed"] is True


def test_review_payload_includes_interview_preview(act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    draft = {
        "source_doc_id": "oee-fixture-act-2025",
        "extraction_run_id": "fixture",
        "tier": "act",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "r1",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar panel relief",
                "quote": "solar panels relief capped",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
                "question_prompt": "Did you install solar panels this year?",
                "help": "Keep the supplier invoice.",
                "input_kind": "yes_no_amount",
            }
        ],
    }
    _save_draft(draft, act_admin_paths())
    payload = review_payload("oee-fixture-act-2025")
    relief = payload["reliefs"][0]
    preview = relief["interview_preview"]
    assert preview["question_prompt"] == "Did you install solar panels this year?"
    assert preview["help"] == "Keep the supplier invoice."
    assert relief["has_prior_catalog"] is False


def test_review_payload_merges_prior_interview(
    db_session: Session,
    act_admin_work_dir: Path,
) -> None:
    del act_admin_work_dir
    db_session.add(
        OeEngineYearRelief(
            assessment_year="2025_26",
            compare_group_id="solar_panel_relief",
            entry_id="live-solar",
            source_doc_id="oee-act-prior",
            cap_amount="600000",
            display_name="Solar panel relief",
            unit="lkr",
            input_kind="yes_no_amount",
            payload_json={
                "question_prompt": "Did you install solar panels this year?",
                "help": "Use the invoice total.",
                "input_kind": "yes_no_amount",
                "display_name": "Solar panel relief",
                "compare_group_id": "solar_panel_relief",
            },
            effective_from="2021-04-01",
            extraction_run_id="live",
        )
    )
    db_session.commit()
    draft = {
        "source_doc_id": "oee-act-new",
        "extraction_run_id": "new",
        "tier": "act",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "r-new",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar panel relief",
                "quote": "solar panels relief capped",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
                "question_prompt": "",
                "help": "",
                "input_kind": "notice",
            }
        ],
    }
    _save_draft(draft, act_admin_paths())
    payload = review_payload("oee-act-new", session=db_session)
    relief = payload["reliefs"][0]
    assert relief["has_prior_catalog"] is True
    assert relief["question_prompt"] == "Did you install solar panels this year?"
    assert relief["prior_question_prompt"] == "Did you install solar panels this year?"
    assert relief["interview_preview"]["question_prompt"] == "Did you install solar panels this year?"
    assert relief["help"] == "Use the invoice total."
    assert relief["input_kind"] == "yes_no_amount"


def test_patch_question_fields_http(client, act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    draft = {
        "source_doc_id": "oee-fixture-act-2025",
        "extraction_run_id": "fixture",
        "tier": "act",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "r1",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar",
                "quote": "solar panels relief capped",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
            }
        ],
    }
    _save_draft(draft, act_admin_paths())
    response = client.patch(
        "/act-admin/review/oee-fixture-act-2025/rows/r1",
        json={
            "question_prompt": "Did you buy solar panels this year?",
            "help": "Enter the invoice amount.",
            "input_kind": "yes_no_amount",
        },
        headers=_admin_headers(),
    )
    assert response.status_code == 200
    relief = next(row for row in response.json()["reliefs"] if row["entry_id"] == "r1")
    assert relief["question_prompt"] == "Did you buy solar panels this year?"
    assert relief["help"] == "Enter the invoice amount."
    assert relief["input_kind"] == "yes_no_amount"
    assert relief["interview_preview"]["question_prompt"] == "Did you buy solar panels this year?"


def test_catalog_preview_uses_present_relief(
    db_session: Session,
    act_admin_work_dir: Path,
) -> None:
    del act_admin_work_dir
    draft = {
        "source_doc_id": "oee-preview-act",
        "extraction_run_id": "preview",
        "tier": "act",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "r1",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar panel relief",
                "quote": "solar panels relief capped",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "accepted",
                "engine_scope": "individual",
                "cap_amount": "600000",
                "effective_from": "2021-04-01",
                "question_prompt": "Did you install solar panels this year?",
                "help": "Keep the invoice.",
                "input_kind": "yes_no_amount",
            }
        ],
    }
    _save_draft(draft, act_admin_paths())
    preview = catalog_preview(db_session, "oee-preview-act", assessment_year="2025_26")
    rows = preview["preview_reliefs"]
    assert rows
    solar = next(row for row in rows if row.get("compare_group_id") == "solar_panel_relief")
    assert solar["question_prompt"] == "Did you install solar panels this year?"
    assert solar["help"] == "Keep the invoice."


def test_list_years_excludes_compiled_2026(
    db_session: Session,
) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(
        OeEnginePromotedEntity(
            source_doc_id="oee-act-11-2026",
            extraction_run_id="x",
            entity_kind="relief",
            compare_group_id="solar_panel_relief",
            entry_id="future",
            payload_json={
                "entity_kind": "relief",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar panel relief",
                "effective_from": "2026-04-01",
                "engine_scope": "individual",
                "question_prompt": "Did you install solar panels this year?",
            },
            payload_hash="h",
            promoted_at=now,
        )
    )
    db_session.commit()
    recompile_year_views(db_session)
    db_session.commit()
    years = {row["assessment_year"] for row in list_years(db_session)}
    assert "2026_27" not in years


def test_list_years_hides_leftover_2026_rows(db_session: Session) -> None:
    db_session.add(
        OeEngineYearRelief(
            assessment_year="2026_27",
            compare_group_id="personal_relief",
            entry_id="stale-2026",
            source_doc_id="oee-stale",
            cap_amount="1800000",
            display_name="Personal relief",
            unit="lkr",
            input_kind="notice",
            payload_json={"compare_group_id": "personal_relief"},
            effective_from="2026-04-01",
            extraction_run_id="stale",
        )
    )
    db_session.add(
        OeEngineYearRelief(
            assessment_year="2025_26",
            compare_group_id="personal_relief",
            entry_id="live-2025",
            source_doc_id="oee-live",
            cap_amount="1800000",
            display_name="Personal relief",
            unit="lkr",
            input_kind="notice",
            payload_json={"compare_group_id": "personal_relief"},
            effective_from="2025-04-01",
            extraction_run_id="live",
        )
    )
    db_session.commit()
    years = {row["assessment_year"] for row in list_years(db_session)}
    assert "2026_27" not in years
    assert "2025_26" in years


def test_delete_stuck_ingesting_job(act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    save_job(
        {
            "id": "stuck-job",
            "status": "ingesting",
            "source_doc_id": "oee-act-99-2026",
            "original_filename": "demo.pdf",
        }
    )
    result = delete_job("stuck-job", reviewer="Tester")
    assert result["status"] == "deleted"
    assert job_path("stuck-job").is_file() is False


def test_review_payload_collapses_reprint_reliefs(act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    draft = {
        "source_doc_id": "oee-act-99-2026",
        "extraction_run_id": "fixture",
        "tier": "act",
        "entities": [
            {
                "entity_kind": "relief",
                "entry_id": "oee-act-99-2026:fifth_schedule:relief:0",
                "compare_group_id": "personal_relief",
                "display_name": "Personal Relief",
                "quote": "Rs. 2,000,000, for the year of assessment commencing on April 1, 2026.",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
                "cap_amount": "2000000",
                "effective_from": "2026-04-01",
                "question_prompt": (
                    "What is your personal relief amount for the year of assessment "
                    "commencing on April 1, 2026?"
                ),
                "help": "Enter the personal relief amount for the specified year.",
                "input_kind": "amount",
            },
            {
                "entity_kind": "relief",
                "entry_id": "oee-act-99-2026:w006:relief:0",
                "compare_group_id": "personal_relief",
                "display_name": "Personal Relief",
                "quote": "The synthetic amendment changes the personal relief to Rs. 2,000,000.",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
                "cap_amount": "2000000",
            "effective_from": "2026-04-01",
            "question_prompt": "What is your personal relief for the assessment year 2026/27?",
            "help": "Enter the amount of personal relief applicable for the year 2026/27.",
            "input_kind": "amount",
        },
        {
            "entity_kind": "relief",
            "entry_id": "oee-act-99-2026:w006:relief:0b",
            "compare_group_id": "personal_relief",
            "display_name": "Personal Relief",
            "quote": "Personal relief restated without a date.",
            "included": True,
            "quote_ok_window": True,
            "quote_ok_full_doc": True,
            "review_status": "pending",
            "engine_scope": "individual",
            "cap_amount": "2000000",
            "effective_from": "",
            "question_prompt": "What is your personal relief?",
            "help": "",
            "input_kind": "amount",
        },
            {
                "entity_kind": "relief",
                "entry_id": "oee-act-99-2026:w009:relief:0",
                "compare_group_id": "qualifying_computer_equipment",
                "display_name": "Qualifying Computer Equipment",
                "quote": "A computer or laptop purchased and used primarily by an individual.",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
            },
            {
                "entity_kind": "relief",
                "entry_id": "oee-act-99-2026:fifth_schedule:relief:1",
                "compare_group_id": "digital_productivity_equipment_relief",
                "display_name": "Digital Productivity Equipment Relief",
                "quote": "subject to a maximum of Rs. 300,000",
                "included": True,
                "quote_ok_window": True,
                "quote_ok_full_doc": True,
                "review_status": "pending",
                "engine_scope": "individual",
                "cap_amount": "300000",
                "effective_from": "2026-04-01",
                "question_prompt": (
                    "Did you incur qualifying expenditure for digital productivity equipment "
                    "used primarily in the production of income?"
                ),
                "help": "This relief is for digital productivity equipment used primarily for income production.",
                "input_kind": "yes_no_amount",
            },
        ],
    }
    _save_draft(draft, act_admin_paths())
    payload = review_payload("oee-act-99-2026")
    reliefs = payload["reliefs"]
    groups = [str(row["compare_group_id"]) for row in reliefs]
    assert groups.count("personal_relief") == 1
    assert groups.count("digital_productivity_equipment_relief") == 1
    assert "qualifying_computer_equipment" not in groups
    personal = next(row for row in reliefs if row["compare_group_id"] == "personal_relief")
    assert personal["question_prompt"] == "What is your personal relief amount?"
    assert payload["pending_count"] == 2
    assert payload["year_context"]["year_kind_suggested"] == "NEW_YEAR"
    assert personal["year_kind_suggested"] == "NEW_YEAR"
    assert personal["year_kind"] is None


def _future_draft(**overrides: object) -> dict:
    entity = {
        "entity_kind": "relief",
        "entry_id": "r-2026",
        "compare_group_id": "digital_productivity_equipment_relief",
        "display_name": "Digital Productivity Equipment Relief",
        "quote": "subject to a maximum of Rs. 300,000",
        "included": True,
        "quote_ok_window": True,
        "quote_ok_full_doc": True,
        "review_status": "accepted",
        "engine_scope": "individual",
        "cap_amount": "300000",
        "effective_from": "2026-04-01",
        "question_prompt": (
            "Did you incur qualifying expenditure for digital productivity equipment?"
        ),
        "input_kind": "yes_no_amount",
    }
    entity.update(overrides)
    return {
        "source_doc_id": "oee-act-99-2026",
        "extraction_run_id": "preview",
        "tier": "act",
        "entities": [entity],
    }


def test_review_ready_requires_year_kind_for_new_ya(act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    ready = review_ready(_future_draft())
    assert ready["activate_allowed"] is False
    assert any(issue["code"] == "missing_year_kind" for issue in ready["blocking_issues"])
    ready_new = review_ready(_future_draft(year_kind="NEW_YEAR"))
    assert ready_new["activate_allowed"] is True


def test_patch_and_bulk_year_kind(act_admin_work_dir: Path, client) -> None:
    del act_admin_work_dir
    _save_draft(_future_draft(review_status="pending"), act_admin_paths())
    patched = client.patch(
        "/act-admin/review/oee-act-99-2026/rows/r-2026",
        json={"year_kind": "NEW_YEAR"},
        headers=_admin_headers(),
    )
    assert patched.status_code == 200
    row = patched.json()["reliefs"][0]
    assert row["year_kind"] == "NEW_YEAR"
    bulk = client.post(
        "/act-admin/review/oee-act-99-2026/year-kind",
        json={"year_kind": "UPDATE"},
        headers=_admin_headers(),
    )
    assert bulk.status_code == 200
    assert bulk.json()["reliefs"][0]["year_kind"] == "UPDATE"


def test_catalog_preview_includes_2026_after_new_year(
    db_session: Session,
    act_admin_work_dir: Path,
) -> None:
    del act_admin_work_dir
    _save_draft(_future_draft(), act_admin_paths())
    without_kind = catalog_preview(db_session, "oee-act-99-2026")
    assert "2026_27" not in without_kind["preview_years"]
    patch_row(
        "oee-act-99-2026",
        "r-2026",
        reviewer="Tester",
        patch={"year_kind": "NEW_YEAR"},
        session=db_session,
    )
    with_kind = catalog_preview(db_session, "oee-act-99-2026")
    assert "2026_27" in with_kind["preview_years"]
    year_view = catalog_preview(
        db_session, "oee-act-99-2026", assessment_year="2026_27"
    )
    groups = {row.get("compare_group_id") for row in year_view["preview_reliefs"]}
    assert "digital_productivity_equipment_relief" in groups


def test_list_years_includes_new_year_2026(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(
        OeEnginePromotedEntity(
            source_doc_id="oee-act-99-2026",
            extraction_run_id="x",
            entity_kind="relief",
            compare_group_id="solar_panel_relief",
            entry_id="future",
            payload_json={
                "entity_kind": "relief",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar panel relief",
                "effective_from": "2026-04-01",
                "engine_scope": "individual",
                "year_kind": "NEW_YEAR",
                "question_prompt": "Did you install solar panels this year?",
            },
            payload_hash="h",
            promoted_at=now,
        )
    )
    db_session.commit()
    recompile_year_views(db_session)
    db_session.commit()
    years = {row["assessment_year"] for row in list_years(db_session)}
    assert "2026_27" in years


def test_unpromote_drops_new_year_2026(db_session: Session) -> None:
    now = datetime.now(timezone.utc)
    db_session.add(
        OeEnginePromotedEntity(
            source_doc_id="oee-act-14-2023",
            extraction_run_id="older",
            entity_kind="relief",
            compare_group_id="personal_relief",
            entry_id="live-2025",
            payload_json={
                "entity_kind": "relief",
                "compare_group_id": "personal_relief",
                "display_name": "Personal relief",
                "effective_from": "2023-04-01",
                "engine_scope": "individual",
                "cap_amount": "1200000",
                "question_prompt": "What is your personal relief amount?",
            },
            payload_hash="older",
            promoted_at=now,
        )
    )
    db_session.add(
        OeEnginePromotedEntity(
            source_doc_id="oee-act-99-2026",
            extraction_run_id="x",
            entity_kind="relief",
            compare_group_id="solar_panel_relief",
            entry_id="future",
            payload_json={
                "entity_kind": "relief",
                "compare_group_id": "solar_panel_relief",
                "display_name": "Solar panel relief",
                "effective_from": "2026-04-01",
                "engine_scope": "individual",
                "year_kind": "NEW_YEAR",
                "question_prompt": "Did you install solar panels this year?",
            },
            payload_hash="h",
            promoted_at=now,
        )
    )
    db_session.add(
        OeEnginePromotedRun(
            source_doc_id="oee-act-99-2026",
            extraction_run_id="x",
            payload_hash="h",
            branch="insert",
            promoted_at=now,
        )
    )
    db_session.commit()
    recompile_year_views(db_session)
    db_session.commit()
    assert "2026_27" in {row["assessment_year"] for row in list_years(db_session)}
    result = unpromote_source_doc(db_session, "oee-act-99-2026")
    db_session.commit()
    years = {row["assessment_year"] for row in list_years(db_session)}
    assert result["removed_entities"] == 1
    assert result["removed_run"] is True
    assert "2026_27" not in years
    assert "2025_26" in years
    leftover = db_session.query(OeEngineYearRelief).filter_by(source_doc_id="oee-act-99-2026")
    assert leftover.count() == 0
    kept = db_session.query(OeEngineYearRelief).filter_by(source_doc_id="oee-act-14-2023")
    assert kept.count() >= 1


def test_reset_activation_returns_draft_to_queue(act_admin_work_dir: Path) -> None:
    del act_admin_work_dir
    draft = _future_draft(year_kind="NEW_YEAR")
    draft["job_id"] = "job-99"
    draft["review_status"] = "activated"
    draft["activated_by"] = "Tester"
    _save_draft(draft, act_admin_paths())
    save_job(
        {
            "id": "job-99",
            "status": "activated",
            "source_doc_id": "oee-act-99-2026",
            "activated_by": "Tester",
        }
    )
    result = reset_activation("oee-act-99-2026", reviewer="Tester")
    assert result["draft_reset"] is True
    assert result["job_reset"] is True
    reloaded = json.loads((act_admin_paths().drafts_dir / "oee-act-99-2026.json").read_text(encoding="utf-8"))
    assert "activated_at" not in reloaded
    assert reloaded["entities"][0]["year_kind"] == "NEW_YEAR"
    assert reloaded["entities"][0]["review_status"] == "accepted"
    job = json.loads(job_path("job-99").read_text(encoding="utf-8"))
    assert job["status"] == "extracted"
