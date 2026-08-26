"""Phase 5 load-act APIs: fixtures, Guide, mismatches; no live extract."""

from __future__ import annotations

from sqlalchemy.orm import Session

from oe_engine_app.services.fixtures import load_extract_fixture, seed_act_document
from oe_engine_app.services.terminus import promote_act_run


def test_extract_live_rejected(client) -> None:
    response = client.post("/extract", json={"source_doc_id": "oee-act-14-2023", "dry_run": False})
    assert response.status_code == 400
    assert "Phase 6" in response.json()["detail"]


def test_extract_dry_run_ok(client) -> None:
    response = client.post("/extract", json={"source_doc_id": "oee-act-14-2023", "dry_run": True})
    assert response.status_code == 200
    assert response.json()["usd_this_run"] == 0.0


def test_review_fixture_act(client) -> None:
    response = client.get("/review/oee-fixture-act-2025")
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "act"
    assert body["promote_allowed"] is True
    assert body["entity_count"] >= 1


def test_review_fixture_guide_no_promote(client) -> None:
    response = client.get("/review/oee-fixture-guide")
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "guide"
    assert body["promote_allowed"] is False


def test_review_fixture_consolidated_no_promote(client) -> None:
    response = client.get("/review/oee-fixture-consolidated")
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "consolidated"
    assert body["promote_allowed"] is False


def test_apply_guide_fixture_then_update_display(client) -> None:
    applied = client.post("/fixtures/apply", json={"file_name": "guide_extract.json"})
    assert applied.status_code == 200
    assert applied.json()["promote_allowed"] is False
    notes = client.get("/guide-notes", params={"compare_group_id": "solar_panel_relief"})
    assert notes.status_code == 200
    assert notes.json()["note_count"] >= 1
    assert notes.json()["source_label"] == "Guide"
    updated = client.post(
        "/guide-display/update", json={"source_doc_id": "oee-fixture-guide"}
    )
    assert updated.status_code == 200
    assert updated.json()["review_status"] == "accepted"


def test_apply_consolidated_fixture_writes_mismatches(client, db_session: Session) -> None:
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2022")
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2022.json"))
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    db_session.commit()
    applied = client.post("/fixtures/apply", json={"file_name": "consolidated_facts.json"})
    assert applied.status_code == 200
    flags = client.get("/mismatches")
    assert flags.status_code == 200
    body = flags.json()
    assert body["flag_count"] >= 2
    years = {row["year"] for row in body["flags"] if row["compare_group_id"] == "personal_relief"}
    assert years == {"2024_25", "2025_26"}


def test_reliefs_include_prompt_and_evidence(client, db_session: Session) -> None:
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    db_session.commit()
    response = client.get("/reliefs/2025_26")
    assert response.status_code == 200
    solar = next(
        e
        for e in response.json()["entries"]
        if e["compare_group_id"] == "solar_panel_relief"
    )
    assert solar["question_prompt"]
    assert solar["required_evidence"]
    assert solar["eligibility_text"]
