"""Later amendment wins; chunk-coverage; hash-match three-way."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from db.year_views import OeEnginePromotedEntity, OeEngineYearRelief
from oe_engine_app.services.compiler import (
    ASSESSMENT_YEARS,
    act_implicit_from,
    compile_maps,
    default_question_prompt,
    derive_assessment_years,
    entity_applies,
    payload_for_apply,
)
from oe_engine_app.services.fixtures import load_extract_fixture, seed_act_document
from oe_engine_app.services.hash_match import classify_act_hash
from oe_engine_app.services.terminus import ChunkCoverageError, promote_act_run
from oe_engine_app.services.year_store import reliefs_for_year


def test_hash_match_three_way() -> None:
    assert classify_act_hash(existing_hash=None, new_hash="abc") == "insert"
    assert classify_act_hash(existing_hash="abc", new_hash="abc") == "identical"
    assert classify_act_hash(existing_hash="abc", new_hash="def") == "updated"


def test_assessment_years_stop_at_2025_26() -> None:
    assert "2026_27" not in ASSESSMENT_YEARS
    assert ASSESSMENT_YEARS[-1] == "2025_26"


def test_later_amendment_wins_personal_relief(db_session: Session) -> None:
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2022")
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2022.json"))
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    db_session.commit()
    y2024 = reliefs_for_year(db_session, "2024_25") or []
    y2025 = reliefs_for_year(db_session, "2025_26") or []
    assert db_session.query(OeEngineYearRelief).count() >= 1
    personal_2024 = next(e for e in y2024 if e["compare_group_id"] == "personal_relief")
    personal_2025 = next(e for e in y2025 if e["compare_group_id"] == "personal_relief")
    assert personal_2024["cap_amount"] == "1200000"
    assert personal_2024["source_doc_id"] == "oee-fixture-act-2022"
    assert personal_2025["cap_amount"] == "1800000"
    assert personal_2025["source_doc_id"] == "oee-fixture-act-2025"


def test_promote_without_chunks_rejected(db_session: Session) -> None:
    seed_act_document(
        db_session, source_doc_id="oee-fixture-act-2025", with_chunk=False
    )
    with pytest.raises(ChunkCoverageError):
        promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    assert db_session.query(OeEngineYearRelief).count() == 0


def test_identical_hash_skips_rewrite(db_session: Session) -> None:
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025")
    run = load_extract_fixture("act_extract_2025.json")
    first = promote_act_run(db_session, run)
    second = promote_act_run(db_session, run)
    assert first["branch"] == "insert"
    assert second["branch"] == "identical"
    assert second["skipped"] is True


def _solar_blank_payload() -> dict:
    return {
        "entity_kind": "relief",
        "entry_id": "oee-act-10-2021:w010:relief:3",
        "source_doc_id": "oee-act-10-2021",
        "compare_group_id": "solar_panel_expenditure",
        "display_name": "Solar Panel Expenditure",
        "cap_amount": "600000",
        "quote": (
            "in the case of a resident individual who has acquired solar panels "
            "to fix on his premises, Rs. 600,000 for each year of assessment"
        ),
        "effective_from": "",
        "effective_to": "",
        "engine_scope": "individual",
        "included": True,
    }


def test_blank_dates_floor_to_act_year_not_epoch() -> None:
    payload = _solar_blank_payload()
    assert act_implicit_from(payload).isoformat() == "2021-04-01"
    before_act = [ya for ya in ASSESSMENT_YEARS if ya < "2021_22"]
    assert before_act
    assert all(entity_applies(payload, ya) is False for ya in before_act)
    assert entity_applies(payload, "2021_22") is True


def test_act_24_2017_implicit_from_is_catalog_epoch() -> None:
    """Certification Oct 2017 must not map Target YA to 2017/18 — catalog starts 2018/19."""
    payload = {"source_doc_id": "oee-act-24-2017", "effective_from": ""}
    assert act_implicit_from(payload).isoformat() == "2018-04-01"
    from oe_engine_app.services.compiler import assessment_year_label, _ya_start_containing

    assert assessment_year_label(_ya_start_containing(act_implicit_from(payload))) == "2018_19"


def test_solar_relief_not_in_years_before_act_10_2021() -> None:
    payload = _solar_blank_payload()
    row = OeEnginePromotedEntity(
        id=1,
        source_doc_id="oee-act-10-2021",
        extraction_run_id="test",
        entity_kind="relief",
        compare_group_id="solar_panel_expenditure",
        entry_id=payload["entry_id"],
        payload_json=payload,
        payload_hash="0" * 64,
        promoted_at=datetime(2026, 8, 26),
    )
    reliefs, _rates = compile_maps([row])
    years_with_solar = [
        ya
        for ya, rows in reliefs.items()
        if any(item.get("compare_group_id") == "solar_panel_expenditure" for item in rows)
    ]
    assert "2020_21" not in years_with_solar
    assert "2019_20" not in years_with_solar
    assert "2018_19" not in years_with_solar
    assert "2021_22" in years_with_solar
    for ya in years_with_solar:
        assert ya >= "2021_22"


def _employment_24_2017_payload() -> dict:
    return {
        "entity_kind": "relief",
        "entry_id": "oee-act-24-2017:fifth_schedule:relief:5",
        "source_doc_id": "oee-act-24-2017",
        "compare_group_id": "employment_income_relief",
        "display_name": "Employment income relief",
        "cap_amount": "700000",
        "quote": (
            "in the case of an individual with income from employment, "
            "Rs. 700,000 for each year of assessment"
        ),
        "effective_from": "",
        "effective_to": "",
        "engine_scope": "individual",
        "included": True,
    }


def test_employment_relief_stops_after_2019_20() -> None:
    payload = _employment_24_2017_payload()
    assert entity_applies(payload, "2018_19") is True
    assert entity_applies(payload, "2019_20") is True
    assert entity_applies(payload, "2020_21") is False
    assert entity_applies(payload, "2025_26") is False
    row = OeEnginePromotedEntity(
        id=2,
        source_doc_id="oee-act-24-2017",
        extraction_run_id="test",
        entity_kind="relief",
        compare_group_id="employment_income_relief",
        entry_id=payload["entry_id"],
        payload_json=payload,
        payload_hash="1" * 64,
        promoted_at=datetime(2026, 8, 26),
    )
    reliefs, _rates = compile_maps([row])
    years_with_emp = [
        ya
        for ya, rows in reliefs.items()
        if any(item.get("compare_group_id") == "employment_income_relief" for item in rows)
    ]
    assert years_with_emp == ["2018_19", "2019_20"]


def test_employment_relief_sunset_when_payload_omits_group_id() -> None:
    payload = _employment_24_2017_payload()
    payload.pop("compare_group_id")
    row = OeEnginePromotedEntity(
        id=3,
        source_doc_id="oee-act-24-2017",
        extraction_run_id="test",
        entity_kind="relief",
        compare_group_id="employment_income_relief",
        entry_id=payload["entry_id"],
        payload_json=payload,
        payload_hash="2" * 64,
        promoted_at=datetime(2026, 8, 26),
    )
    reliefs, _rates = compile_maps([row])
    years_with_emp = [
        ya
        for ya, rows in reliefs.items()
        if any(item.get("compare_group_id") == "employment_income_relief" for item in rows)
    ]
    assert years_with_emp == ["2018_19", "2019_20"]


def _band(
    *,
    source_doc_id: str,
    entry_id: str,
    applies_to: str,
    rate: str,
    lower: str,
    upper: str | None,
    effective_from: str,
    row_id: int,
) -> OeEnginePromotedEntity:
    payload = {
        "entity_kind": "rate_band",
        "entry_id": entry_id,
        "source_doc_id": source_doc_id,
        "compare_group_id": "individual_income_tax_slab",
        "band_index": int(rate),
        "lower": lower,
        "upper": upper,
        "rate_percent": rate,
        "applies_to": applies_to,
        "effective_from": effective_from,
        "effective_to": "",
        "engine_scope": "individual",
        "included": True,
    }
    return OeEnginePromotedEntity(
        id=row_id,
        source_doc_id=source_doc_id,
        extraction_run_id="test",
        entity_kind="rate_band",
        compare_group_id="individual_income_tax_slab",
        entry_id=entry_id,
        payload_json=payload,
        payload_hash="0" * 64,
        promoted_at=datetime(2026, 8, 26),
    )


def test_later_individual_ladder_replaces_base_act_and_or_wording() -> None:
    older = _band(
        source_doc_id="oee-act-24-2017",
        entry_id="old-4",
        applies_to="resident and non-resident individuals",
        rate="4",
        lower="0",
        upper="600000",
        effective_from="2018-04-01",
        row_id=1,
    )
    newer = _band(
        source_doc_id="oee-act-45-2022",
        entry_id="new-6",
        applies_to="resident or non-resident individual",
        rate="6",
        lower="0",
        upper="500000",
        effective_from="2023-04-01",
        row_id=2,
    )
    _reliefs, rates = compile_maps([older, newer])
    assert [b["rate_percent"] for b in rates["2018_19"]] == ["4"]
    assert rates["2018_19"][0]["source_doc_id"] == "oee-act-24-2017"
    assert [b["rate_percent"] for b in rates["2023_24"]] == ["6"]
    assert rates["2023_24"][0]["source_doc_id"] == "oee-act-45-2022"
    assert [b["rate_percent"] for b in rates["2025_26"]] == ["6"]


def test_compile_maps_preserves_stored_question_prompt() -> None:
    payload = _solar_blank_payload()
    payload["question_prompt"] = "Did you install solar panels this year?"
    payload["help"] = "Keep the supplier invoice."
    payload["input_kind"] = "yes_no_amount"
    fallback = default_question_prompt({**payload, "question_prompt": ""})
    assert fallback != payload["question_prompt"]
    row = OeEnginePromotedEntity(
        id=11,
        source_doc_id="oee-act-10-2021",
        extraction_run_id="test",
        entity_kind="relief",
        compare_group_id="solar_panel_expenditure",
        entry_id=payload["entry_id"],
        payload_json=payload,
        payload_hash="q" * 64,
        promoted_at=datetime(2026, 8, 26),
    )
    reliefs, _rates = compile_maps([row])
    compiled = next(
        item
        for item in reliefs["2021_22"]
        if item.get("compare_group_id") == "solar_panel_expenditure"
    )
    assert compiled["question_prompt"] == "Did you install solar panels this year?"
    assert compiled["help"] == "Keep the supplier invoice."
    assert compiled["input_kind"] == "yes_no_amount"


def _future_promoted(*, year_kind: str = "") -> OeEnginePromotedEntity:
    payload = {
        "entity_kind": "relief",
        "compare_group_id": "solar_panel_relief",
        "display_name": "Solar panel relief",
        "effective_from": "2026-04-01",
        "engine_scope": "individual",
        "cap_amount": "600000",
        "question_prompt": "Did you install solar panels this year?",
    }
    if year_kind:
        payload["year_kind"] = year_kind
    return OeEnginePromotedEntity(
        source_doc_id="oee-act-99-2026",
        extraction_run_id="x",
        entity_kind="relief",
        compare_group_id="solar_panel_relief",
        entry_id="future",
        payload_json=payload,
        payload_hash="h",
        promoted_at=datetime(2026, 8, 26),
    )


def test_new_year_kind_adds_2026_27_to_compiled_catalog() -> None:
    row = _future_promoted(year_kind="NEW_YEAR")
    years = derive_assessment_years([row])
    assert "2026_27" in years
    reliefs, _rates = compile_maps([row])
    assert "2026_27" in reliefs
    groups = {item.get("compare_group_id") for item in reliefs["2026_27"]}
    assert "solar_panel_relief" in groups


def test_update_kind_clips_2026_into_2025_26() -> None:
    row = _future_promoted(year_kind="UPDATE")
    clipped = payload_for_apply(row)
    assert clipped["effective_from"] == "2025-04-01"
    years = derive_assessment_years([row])
    assert "2026_27" not in years
    reliefs, _rates = compile_maps([row])
    assert "2026_27" not in reliefs
    groups = {item.get("compare_group_id") for item in reliefs["2025_26"]}
    assert "solar_panel_relief" in groups
    groups_2024 = {item.get("compare_group_id") for item in reliefs["2024_25"]}
    assert "solar_panel_relief" not in groups_2024


def _foreign_currency_promoted(
    *,
    row_id: int,
    compare_group_id: str,
    entry_id: str,
    display_name: str,
    promoted_at: datetime,
) -> OeEnginePromotedEntity:
    payload = {
        "entity_kind": "relief",
        "entry_id": entry_id,
        "source_doc_id": "oee-act-24-2017",
        "compare_group_id": compare_group_id,
        "display_name": display_name,
        "cap_amount": "15000000",
        "quote": "income earned in foreign currency in Sri Lanka",
        "effective_from": "2018-04-01",
        "engine_scope": "individual",
        "included": True,
    }
    return OeEnginePromotedEntity(
        id=row_id,
        source_doc_id="oee-act-24-2017",
        extraction_run_id="test",
        entity_kind="relief",
        compare_group_id=compare_group_id,
        entry_id=entry_id,
        payload_json=payload,
        payload_hash=f"{row_id:064d}",
        promoted_at=promoted_at,
    )


def test_compile_maps_collapses_foreign_currency_alias_groups() -> None:
    numbered = _foreign_currency_promoted(
        row_id=41,
        compare_group_id="foreign_currency_income",
        entry_id="oee-act-24-2017:w042:relief:0",
        display_name="Foreign currency income relief",
        promoted_at=datetime(2026, 8, 27, 12, 0, 0),
    )
    schedule = _foreign_currency_promoted(
        row_id=42,
        compare_group_id="foreign_currency_income_relief",
        entry_id="oee-act-24-2017:fifth_schedule:relief:8",
        display_name="Foreign Currency Income Relief",
        promoted_at=datetime(2026, 8, 26, 12, 0, 0),
    )
    reliefs, _rates = compile_maps([numbered, schedule])
    groups_2018 = [
        row["compare_group_id"] for row in reliefs["2018_19"]
    ]
    assert groups_2018.count("foreign_currency_income_relief") == 1
    assert "foreign_currency_income" not in groups_2018
    winner = next(
        row
        for row in reliefs["2018_19"]
        if row["compare_group_id"] == "foreign_currency_income_relief"
    )
    assert "fifth_schedule" in winner["entry_id"]
    assert winner["display_name"] == "Foreign currency service income relief"
    assert winner["effective_to"] == "2019-12-31"
    assert not any(
        row.get("compare_group_id") == "foreign_currency_income_relief"
        for row in reliefs["2025_26"]
    )


def test_foreign_currency_income_relief_stops_after_2019_20() -> None:
    row = _foreign_currency_promoted(
        row_id=43,
        compare_group_id="foreign_currency_income_relief",
        entry_id="oee-act-24-2017:fifth_schedule:relief:8",
        display_name="Foreign Currency Income Relief",
        promoted_at=datetime(2026, 8, 26, 12, 0, 0),
    )
    payload = payload_for_apply(row)
    assert entity_applies(payload, "2018_19") is True
    assert entity_applies(payload, "2019_20") is True
    assert entity_applies(payload, "2020_21") is False
    assert entity_applies(payload, "2025_26") is False
    reliefs, _rates = compile_maps([row])
    years_with = [
        ya
        for ya, rows in reliefs.items()
        if any(
            item.get("compare_group_id") == "foreign_currency_income_relief"
            for item in rows
        )
    ]
    assert years_with == ["2018_19", "2019_20"]
    winner_2019 = next(
        item
        for item in reliefs["2019_20"]
        if item["compare_group_id"] == "foreign_currency_income_relief"
    )
    assert "31 December 2019" in winner_2019["help"]


def test_reliefs_for_year_hides_stale_foreign_currency(db_session: Session) -> None:
    """Stale compiled rows (pre-hard-close) must not reach the interview."""
    payload = {
        "compare_group_id": "foreign_currency_income_relief",
        "display_name": "Foreign currency income relief",
        "cap_amount": "15000000",
        "unit": "lkr",
        "input_kind": "amount",
        "effective_from": "2018-04-01",
        "quote": "foreign currency service income",
    }
    for ya in ("2019_20", "2025_26"):
        db_session.add(
            OeEngineYearRelief(
                assessment_year=ya,
                compare_group_id="foreign_currency_income_relief",
                entry_id=f"stale:foreign_currency:{ya}",
                source_doc_id="oee-act-24-2017",
                cap_amount="15000000",
                display_name="Foreign currency income relief",
                unit="lkr",
                input_kind="amount",
                payload_json=payload,
                effective_from="2018-04-01",
                extraction_run_id="test",
            )
        )
    db_session.commit()
    listed = reliefs_for_year(db_session, "2025_26") or []
    assert not any(
        row.get("compare_group_id") == "foreign_currency_income_relief" for row in listed
    )
    listed_2019 = reliefs_for_year(db_session, "2019_20") or []
    assert any(
        row.get("compare_group_id") == "foreign_currency_income_relief" for row in listed_2019
    )


def _expenditure_promoted(
    *,
    row_id: int,
    compare_group_id: str,
    entry_id: str,
    cap_amount: str,
    effective_from: str,
    source_doc_id: str,
) -> OeEnginePromotedEntity:
    payload = {
        "entity_kind": "relief",
        "entry_id": entry_id,
        "source_doc_id": source_doc_id,
        "compare_group_id": compare_group_id,
        "display_name": "Expenditure relief",
        "cap_amount": cap_amount,
        "quote": "following expenditure up to a total sum of Rs. 1,200,000",
        "effective_from": effective_from,
        "engine_scope": "individual",
        "included": True,
        "input_kind": "amount",
    }
    return OeEnginePromotedEntity(
        id=row_id,
        source_doc_id=source_doc_id,
        extraction_run_id="test",
        entity_kind="relief",
        compare_group_id=compare_group_id,
        entry_id=entry_id,
        payload_json=payload,
        payload_hash=f"{row_id:064d}",
        promoted_at=datetime(2026, 8, 21, 12, 0, 0),
    )


def test_expenditure_relief_listed_through_2022_23_then_sunset() -> None:
    row = _expenditure_promoted(
        row_id=51,
        compare_group_id="resident_individual_expenditure",
        entry_id="oee-act-10-2021:fifth_schedule:relief:2",
        cap_amount="1200000",
        effective_from="2020-01-01",
        source_doc_id="oee-act-10-2021",
    )
    payload = payload_for_apply(row)
    payload["compare_group_id"] = "resident_individual_expenditure"
    assert entity_applies(payload, "2019_20") is False
    assert entity_applies(payload, "2020_21") is True
    assert entity_applies(payload, "2022_23") is True
    assert entity_applies(payload, "2023_24") is False
    assert entity_applies(payload, "2025_26") is False
    reliefs, _rates = compile_maps([row])
    years_with = [
        ya
        for ya, rows in reliefs.items()
        if any(item.get("compare_group_id") == "expenditure_relief" for item in rows)
    ]
    assert years_with == ["2020_21", "2021_22", "2022_23"]
    for ya in years_with:
        winner = next(
            item for item in reliefs[ya] if item["compare_group_id"] == "expenditure_relief"
        )
        assert winner["cap_amount"] == "1200000"
        assert winner["input_kind"] == "amount"


def test_act_45_expenditure_cap_wins_2022_23_then_sunset() -> None:
    older = _expenditure_promoted(
        row_id=52,
        compare_group_id="expenditure_relief",
        entry_id="oee-act-10-2021:fifth_schedule:relief:2",
        cap_amount="1200000",
        effective_from="2020-01-01",
        source_doc_id="oee-act-10-2021",
    )
    newer = _expenditure_promoted(
        row_id=53,
        compare_group_id="expenditure_relief",
        entry_id="oee-act-45-2022:fifth_schedule:relief:6",
        cap_amount="900000",
        effective_from="2022-04-01",
        source_doc_id="oee-act-45-2022",
    )
    newer.payload_json["quote"] = (
        "sum of Rs. 900,000, incurred for the first nine months of the "
        "year of assessment commencing on April 1, 2022"
    )
    newer.payload_json["display_name"] = "Expenditure relief (Act 45 bound)"
    reliefs, _rates = compile_maps([older, newer])
    assert next(
        item["cap_amount"]
        for item in reliefs["2021_22"]
        if item["compare_group_id"] == "expenditure_relief"
    ) == "1200000"
    winner_2022 = next(
        item
        for item in reliefs["2022_23"]
        if item["compare_group_id"] == "expenditure_relief"
    )
    assert winner_2022["cap_amount"] == "900000"
    assert winner_2022["display_name"] == "Expenditure relief (Act 45 bound)"
    assert not any(
        item.get("compare_group_id") == "expenditure_relief" for item in reliefs["2025_26"]
    )


def test_samurdhi_shop_listed_from_2021_22() -> None:
    payload = {
        "entity_kind": "relief",
        "entry_id": "oee-act-10-2021:w009:relief:6",
        "source_doc_id": "oee-act-10-2021",
        "compare_group_id": "contribution_to_samurdhi_shop",
        "display_name": "Samurdhi shop contribution",
        "cap_amount": None,
        "unit": "text",
        "quote": (
            "(d) with effect from April 1, 2021, contribution made by a resident "
            "individual in money or otherwise to establish a shop for a female "
            "individual who is from a Samurdhi beneficiary family"
        ),
        "effective_from": "2021-04-01",
        "engine_scope": "individual",
        "included": True,
        "input_kind": "notice",
        "section_ref": "Fifth Schedule",
    }
    row = OeEnginePromotedEntity(
        id=61,
        source_doc_id="oee-act-10-2021",
        extraction_run_id="test",
        entity_kind="relief",
        compare_group_id="contribution_to_samurdhi_shop",
        entry_id=payload["entry_id"],
        payload_json=payload,
        payload_hash="s" * 64,
        promoted_at=datetime(2026, 8, 27),
    )
    assert entity_applies(payload, "2020_21") is False
    assert entity_applies(payload, "2021_22") is True
    reliefs, _rates = compile_maps([row])
    years_with = [
        ya
        for ya, rows in reliefs.items()
        if any(item.get("compare_group_id") == "qp_samurdhi_shop" for item in rows)
    ]
    assert "2020_21" not in years_with
    assert years_with[0] == "2021_22"
    assert "2025_26" in years_with
    winner = next(
        item for item in reliefs["2025_26"] if item["compare_group_id"] == "qp_samurdhi_shop"
    )
    assert winner["display_name"] == "Samurdhi shop contribution"
    assert winner["input_kind"] == "amount"
    assert winner["cap_amount"] in (None, "")


