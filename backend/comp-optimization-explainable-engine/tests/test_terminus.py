"""Guide/Consolidated never promote; Consolidated writes facts + flags."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.shared.config.database import Base
from db.mismatch import OeEngineMismatchFlag
from db.models import OeEngineConsolidatedFact
from oe_engine_app.schemas.extract import ExtractRun
from oe_engine_app.services.terminus import (
    ChunkCoverageError,
    PromoteForbidden,
    accept_guide_display,
    apply_extract_terminus,
    guide_notes_for,
    promote_act_run,
    update_guide_display,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_promote_guide_forbidden(db_session: Session) -> None:
    run = ExtractRun(
        extraction_run_id="t1",
        source_doc_id="oee-guide-ira",
        tier="guide",
        terminus="display_no_promote",
        model="gpt-4o",
        entities=[],
    )
    with pytest.raises(PromoteForbidden):
        promote_act_run(db_session, run)


def test_promote_consolidated_forbidden(db_session: Session) -> None:
    run = ExtractRun(
        extraction_run_id="t1",
        source_doc_id="oee-consolidated-2025",
        tier="consolidated",
        terminus="facts_and_mismatch_no_promote",
        model="gpt-4o",
        entities=[],
    )
    with pytest.raises(PromoteForbidden):
        promote_act_run(db_session, run)


def test_promote_act_requires_chunks(db_session: Session) -> None:
    run = ExtractRun(
        extraction_run_id="t1",
        source_doc_id="oee-act-14-2023",
        tier="act",
        terminus="review_then_promote",
        model="gpt-4o",
        entities=[],
    )
    with pytest.raises(ChunkCoverageError):
        promote_act_run(db_session, run)


def test_consolidated_writes_facts_and_open_flags(db_session: Session) -> None:
    run = ExtractRun(
        extraction_run_id="t1",
        source_doc_id="oee-consolidated-2025",
        tier="consolidated",
        terminus="facts_and_mismatch_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "consolidated_fact",
                "entry_id": "f1",
                "compare_group_id": "personal_relief",
                "year": "2025_26",
                "value": "1800000",
                "quote": "Rs. 1,800,000",
            }
        ],
    )
    result = apply_extract_terminus(db_session, run)
    db_session.commit()
    assert result["consolidated"]["facts_upserted"] == 1
    fact = db_session.query(OeEngineConsolidatedFact).one()
    assert fact.value == "1800000"
    flag = db_session.query(OeEngineMismatchFlag).one()
    assert flag.status == "open"
    assert flag.value_act is None
    assert flag.value_consolidated == "1800000"


def test_guide_update_display_sets_needs_update(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "oe_engine_app.services.terminus.GUIDE_DISPLAY_DIR",
        tmp_path,
    )
    first = ExtractRun(
        extraction_run_id="r1",
        source_doc_id="oee-guide-ira",
        tier="guide",
        terminus="display_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "guide_help",
                "entry_id": "g1",
                "display_name": "Solar",
                "help": "old",
            }
        ],
    )
    update_guide_display(first)
    second = ExtractRun(
        extraction_run_id="r2",
        source_doc_id="oee-guide-ira",
        tier="guide",
        terminus="display_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "guide_help",
                "entry_id": "g1",
                "display_name": "Solar",
                "help": "new wording",
            }
        ],
    )
    result = update_guide_display(second)
    assert result["review_status"] == "needs_update"
    frozen = json.loads((tmp_path / "oee-guide-ira.json").read_text(encoding="utf-8"))
    assert frozen["entities"][0]["help"] == "old"
    assert frozen["pending_entities"][0]["help"] == "new wording"


def test_guide_display_skips_quote_gated_out(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "oe_engine_app.services.terminus.GUIDE_DISPLAY_DIR",
        tmp_path,
    )
    run = ExtractRun(
        extraction_run_id="r1",
        source_doc_id="oee-guide-ira",
        tier="guide",
        terminus="display_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "guide_help",
                "entry_id": "keep",
                "compare_group_id": "personal_relief",
                "display_name": "Personal",
                "help": "Resident individuals may claim personal relief.",
                "included": True,
            },
            {
                "entity_kind": "guide_help",
                "entry_id": "drop",
                "compare_group_id": "personal_relief",
                "display_name": "Dropped",
                "help": "not in the window",
                "included": False,
            },
        ],
    )
    update_guide_display(run)
    payload = json.loads((tmp_path / "oee-guide-ira.json").read_text(encoding="utf-8"))
    assert [e["entry_id"] for e in payload["entities"]] == ["keep"]


def test_guide_reextract_does_not_swap_notes_until_accept(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "oe_engine_app.services.terminus.GUIDE_DISPLAY_DIR",
        tmp_path,
    )
    first = ExtractRun(
        extraction_run_id="r1",
        source_doc_id="oee-guide-ira",
        tier="guide",
        terminus="display_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "guide_help",
                "entry_id": "g1",
                "compare_group_id": "personal_relief",
                "display_name": "Personal",
                "help": "live help from first extract",
                "included": True,
            }
        ],
    )
    update_guide_display(first)
    second = ExtractRun(
        extraction_run_id="r2",
        source_doc_id="oee-guide-ira",
        tier="guide",
        terminus="display_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "guide_help",
                "entry_id": "g1",
                "compare_group_id": "personal_relief",
                "display_name": "Personal",
                "help": "pending help from re-extract",
                "included": True,
            }
        ],
    )
    update_guide_display(second)
    notes = guide_notes_for("personal_relief")
    assert notes[0]["help"] == "live help from first extract"
    accepted = accept_guide_display("oee-guide-ira")
    assert accepted["review_status"] == "accepted"
    notes_after = guide_notes_for("personal_relief")
    assert notes_after[0]["help"] == "pending help from re-extract"
