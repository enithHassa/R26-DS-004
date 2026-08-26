"""Consolidated facts vs year views: two years, independent flags."""

from __future__ import annotations

from sqlalchemy.orm import Session

from db.mismatch import OeEngineMismatchFlag
from oe_engine_app.schemas.extract import ExtractRun
from oe_engine_app.services.fixtures import load_extract_fixture, seed_act_document
from oe_engine_app.services.mismatch_queue import next_status, write_consolidated_facts
from oe_engine_app.services.terminus import apply_extract_terminus, promote_act_run


def test_two_years_independent_mismatch_rows(db_session: Session) -> None:
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2022")
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2022.json"))
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    cons = load_extract_fixture("consolidated_facts.json")
    apply_extract_terminus(db_session, cons)
    db_session.commit()
    flags = (
        db_session.query(OeEngineMismatchFlag)
        .filter(OeEngineMismatchFlag.compare_group_id == "personal_relief")
        .order_by(OeEngineMismatchFlag.year)
        .all()
    )
    assert len(flags) == 2
    by_year = {f.year: f for f in flags}
    assert by_year["2024_25"].value_consolidated == "1200000"
    assert by_year["2024_25"].value_act == "1200000"
    assert by_year["2024_25"].status == "resolved"
    assert by_year["2025_26"].value_consolidated == "1800000"
    assert by_year["2025_26"].value_act == "1800000"
    assert by_year["2025_26"].status == "resolved"
    assert by_year["2024_25"].value_act != by_year["2025_26"].value_act


def test_promote_recompare_resolves_open_flag(db_session: Session) -> None:
    cons = load_extract_fixture("consolidated_facts.json")
    apply_extract_terminus(db_session, cons)
    db_session.commit()
    open_flags = db_session.query(OeEngineMismatchFlag).all()
    assert all(f.status == "open" for f in open_flags)
    assert all(f.value_act is None for f in open_flags)
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2022")
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2022.json"))
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    db_session.commit()
    flags = {f.year: f for f in db_session.query(OeEngineMismatchFlag).all()}
    assert flags["2025_26"].status == "resolved"
    assert flags["2024_25"].status == "resolved"


def test_dismissed_reopens_only_when_pair_changes() -> None:
    assert (
        next_status(
            old_status="dismissed",
            old_consolidated="1800000",
            old_act="1200000",
            new_consolidated="1800000",
            new_act="1200000",
        )
        == "dismissed"
    )
    assert (
        next_status(
            old_status="dismissed",
            old_consolidated="1800000",
            old_act="1200000",
            new_consolidated="1800000",
            new_act="1800000",
        )
        == "resolved"
    )
    assert (
        next_status(
            old_status="dismissed",
            old_consolidated="1800000",
            old_act="1200000",
            new_consolidated="1500000",
            new_act="1200000",
        )
        == "open"
    )


def test_consolidated_extract_never_writes_year_tables(db_session: Session) -> None:
    from db.year_views import OeEngineYearRelief

    cons = ExtractRun.model_validate(load_extract_fixture("consolidated_facts.json").model_dump())
    write_consolidated_facts(db_session, cons)
    db_session.commit()
    assert db_session.query(OeEngineYearRelief).count() == 0


def test_write_consolidated_facts_skips_quote_gated_out(db_session: Session) -> None:
    from db.models import OeEngineConsolidatedFact

    run = ExtractRun(
        extraction_run_id="gated",
        source_doc_id="oee-consolidated-2025",
        tier="consolidated",
        terminus="facts_and_mismatch_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "consolidated_fact",
                "entry_id": "keep",
                "compare_group_id": "personal_relief",
                "year": "2025_26",
                "value": "1,800,000",
                "quote": "Rs. 1,800,000",
                "included": True,
            },
            {
                "entity_kind": "consolidated_fact",
                "entry_id": "drop",
                "compare_group_id": "personal_relief",
                "year": "2024_25",
                "value": "999",
                "quote": "not in the window",
                "included": False,
            },
        ],
    )
    result = write_consolidated_facts(db_session, run)
    db_session.commit()
    assert result["facts_upserted"] == 1
    fact = db_session.query(OeEngineConsolidatedFact).one()
    assert fact.year == "2025_26"
    assert fact.value == "1800000"


def test_lookup_act_value_joins_progressive_ladder_aliases(db_session: Session) -> None:
    from oe_engine_app.services.year_store import lookup_act_value

    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    db_session.commit()
    joined = lookup_act_value(db_session, "individual_progressive_rates", "2025_26")
    assert joined == lookup_act_value(db_session, "first_schedule_rates", "2025_26")
    assert joined


def test_rate_ladder_alias_group_compares_as_first_schedule(db_session: Session) -> None:
    from db.mismatch import OeEngineMismatchFlag
    from oe_engine_app.services.year_store import lookup_act_value

    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    db_session.commit()
    act_ladder = lookup_act_value(db_session, "first_schedule_rates", "2025_26")
    assert act_ladder
    run = ExtractRun(
        extraction_run_id="alias",
        source_doc_id="oee-consolidated-2025",
        tier="consolidated",
        terminus="facts_and_mismatch_no_promote",
        model="gpt-4o",
        entities=[
            {
                "entity_kind": "consolidated_fact",
                "entry_id": "rates",
                "compare_group_id": "oee-consolidated-2025--First-Schedule",
                "year": "2025_26",
                "value": act_ladder,
                "quote": "Not exceeding Rs. 1,000,000 | 6 %",
                "included": True,
            }
        ],
    )
    write_consolidated_facts(db_session, run)
    db_session.commit()
    flag = db_session.query(OeEngineMismatchFlag).one()
    assert flag.compare_group_id == "first_schedule_rates"
    assert flag.status == "resolved"
