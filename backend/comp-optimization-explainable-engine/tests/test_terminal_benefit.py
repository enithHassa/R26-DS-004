"""Terminal-benefit rate family: compile, dedupe, calculate, engine_scope."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from db.year_views import OeEnginePromotedEntity
from oe_engine_app.services.calculate import calculate, tax_from_slabs
from oe_engine_app.services.compiler import (
    compile_maps,
    persist_year_views,
    recompile_year_views,
    validate_rate_band_set,
)
from oe_engine_app.services.engine_scope import infer_engine_scope
from oe_engine_app.services.extract_dedupe import (
    canonical_compare_group_id,
    collapse_duplicate_extract_entities,
)
from oe_engine_app.services.fixtures import load_extract_fixture, seed_act_document
from oe_engine_app.services import year_store
from oe_engine_app.services.terminal_benefit import (
    PERIOD_NA,
    PERIOD_OVER_20,
    PERIOD_UPTO_20,
    TERMINAL_BENEFIT_GROUP,
    select_terminal_bands,
)
from oe_engine_app.services.terminus import promote_act_run
from tests.test_calculate import TYPICAL_INCOME

_PROMOTED_AT = datetime(2026, 8, 26)


def _aggregate_terminal_tax(
    db_session: Session,
    assessment_year: str,
    amount: int,
    *,
    over_20_years: bool | None = None,
    period: str | None = None,
) -> int:
    rates = year_store.rates_for_year(db_session, assessment_year)
    assert rates is not None
    _, terminal = year_store.split_year_rates(rates)
    bands = select_terminal_bands(
        terminal,
        assessment_year=assessment_year,
        over_20_years=over_20_years,
        period=period,
    )
    tax, _ = tax_from_slabs(amount, bands)
    return tax


def _promoted(
    *,
    source_doc_id: str,
    entry_id: str,
    payload: dict,
    row_id: int,
    entity_kind: str = "rate_band",
) -> OeEnginePromotedEntity:
    body = dict(payload)
    body.setdefault("entity_kind", entity_kind)
    body.setdefault("entry_id", entry_id)
    body.setdefault("source_doc_id", source_doc_id)
    body.setdefault("engine_scope", "individual")
    body.setdefault("included", True)
    return OeEnginePromotedEntity(
        id=row_id,
        source_doc_id=source_doc_id,
        extraction_run_id="test",
        entity_kind=entity_kind,
        compare_group_id=str(body.get("compare_group_id") or ""),
        entry_id=entry_id,
        payload_json=body,
        payload_hash="t" * 64,
        promoted_at=_PROMOTED_AT,
    )


def _ordinary(*, source: str, rate: str, lower: str, upper: str | None, ef: str, row_id: int, entry: str) -> OeEnginePromotedEntity:
    return _promoted(
        source_doc_id=source,
        entry_id=entry,
        row_id=row_id,
        payload={
            "compare_group_id": "first_schedule_rates",
            "band_index": 1,
            "lower": lower,
            "upper": upper,
            "rate_percent": rate,
            "applies_to": "resident or non-resident individual",
            "effective_from": ef,
            "effective_to": "",
        },
    )


def _terminal(
    *,
    source: str,
    entry: str,
    index: int,
    lower: str,
    upper: str | None,
    rate: str,
    ef: str,
    et: str,
    group: str,
    row_id: int,
    applies: str = "resident or non-resident individual",
) -> OeEnginePromotedEntity:
    return _promoted(
        source_doc_id=source,
        entry_id=entry,
        row_id=row_id,
        payload={
            "compare_group_id": group,
            "band_index": index,
            "lower": lower,
            "upper": upper,
            "rate_percent": rate,
            "applies_to": applies,
            "effective_from": ef,
            "effective_to": et,
        },
    )


def _personal(*, source: str = "oee-act-24-2017", cap: str = "500000", ef: str = "2018-04-01", row_id: int = 90) -> OeEnginePromotedEntity:
    return _promoted(
        source_doc_id=source,
        entry_id=f"{source}:personal",
        row_id=row_id,
        entity_kind="relief",
        payload={
            "compare_group_id": "personal_relief",
            "display_name": "Personal relief",
            "cap_amount": cap,
            "effective_from": ef,
            "input_kind": "notice",
            "engine_binding": {"kind": "none"},
            "unit": "lkr",
        },
    )


def _family_rows() -> list[OeEnginePromotedEntity]:
    ordinary_2017 = _ordinary(
        source="oee-act-24-2017",
        rate="4",
        lower="0",
        upper="600000",
        ef="2018-04-01",
        row_id=1,
        entry="ord-2017",
    )
    ordinary_later = _ordinary(
        source="oee-act-45-2022",
        rate="6",
        lower="0",
        upper="500000",
        ef="2023-04-01",
        row_id=2,
        entry="ord-2022",
    )
    t2017 = []
    for i, (lower, upper, rate) in enumerate(
        [("0", "2000000", "0"), ("2000001", "3000000", "5"), ("3000001", None, "10")],
        start=1,
    ):
        t2017.append(
            _terminal(
                source="oee-act-24-2017",
                entry=f"t2017-upto-{i}",
                index=i,
                lower=lower,
                upper=upper,
                rate=rate,
                ef="2018-04-01",
                et="2019-12-31",
                group="employment_income_tax",
                row_id=10 + i,
            )
        )
    for i, (lower, upper, rate) in enumerate(
        [("0", "5000000", "0"), ("5000001", "6000000", "5"), ("6000001", None, "10")],
        start=1,
    ):
        t2017.append(
            _terminal(
                source="oee-act-24-2017",
                entry=f"t2017-over-{i}",
                index=i,
                lower=lower,
                upper=upper,
                rate=rate,
                ef="2018-04-01",
                et="2019-12-31",
                group="employment_income_tax_20_years",
                row_id=20 + i,
            )
        )
    t2021 = []
    for i, (lower, upper, rate) in enumerate(
        [("0", "10000000", "0"), ("10000000", "20000000", "6"), ("20000000", None, "12")],
        start=1,
    ):
        t2021.append(
            _terminal(
                source="oee-act-10-2021",
                entry=f"t2021-{i}",
                index=i,
                lower=lower,
                upper=upper,
                rate=rate,
                ef="2020-01-01",
                et="",
                group="employment_income",
                row_id=30 + i,
                applies="a person",
            )
        )
    return [ordinary_2017, ordinary_later, _personal(), *t2017, *t2021]


def _terminal_in(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row.get("compare_group_id") == TERMINAL_BENEFIT_GROUP]


def test_canonical_aliases_do_not_merge_into_first_schedule() -> None:
    assert canonical_compare_group_id("employment_income_tax", entity_kind="rate_band") == TERMINAL_BENEFIT_GROUP
    assert canonical_compare_group_id("employment_income", entity_kind="rate_band") == TERMINAL_BENEFIT_GROUP
    assert (
        canonical_compare_group_id("employment_income_tax_20_years", entity_kind="rate_band")
        == TERMINAL_BENEFIT_GROUP
    )
    assert canonical_compare_group_id("first_schedule_rates", entity_kind="rate_band") == "first_schedule_rates"


def test_dedupe_keeps_2m_and_5m_zero_bands() -> None:
    rows = [
        {
            "entity_kind": "rate_band",
            "entry_id": "a:band:6",
            "compare_group_id": "employment_income_tax",
            "rate_percent": "0",
            "effective_from": "2018-04-01",
            "applies_to": "resident or non-resident individual",
            "upper": "2000000",
            "band_index": 1,
            "included": True,
            "quote": "Not exceeding Rs. 2,000,000 | 0%",
        },
        {
            "entity_kind": "rate_band",
            "entry_id": "a:band:9",
            "compare_group_id": "employment_income_tax_20_years",
            "rate_percent": "0",
            "effective_from": "2018-04-01",
            "applies_to": "resident or non-resident individual",
            "upper": "5000000",
            "band_index": 1,
            "included": True,
            "quote": "Not exceeding Rs. 5,000,000 | 0%",
        },
    ]
    collapsed = collapse_duplicate_extract_entities(rows)
    assert len(collapsed) == 2
    conditions = {row.get("employment_period_condition") for row in collapsed}
    # canonical group is stamped on collapse; period is in the key even if not stored
    assert {row["entry_id"] for row in collapsed} == {"a:band:6", "a:band:9"}
    assert conditions <= {PERIOD_UPTO_20, PERIOD_OVER_20, None, ""}


def test_validate_allows_two_individual_ladders() -> None:
    ordinary = [
        {
            "entity_kind": "rate_band",
            "band_index": 1,
            "lower": "0",
            "upper": "1000000",
            "rate_percent": "6",
            "applies_to": "resident or non-resident individual",
            "compare_group_id": "first_schedule_rates",
        },
        {
            "entity_kind": "rate_band",
            "band_index": 2,
            "lower": "1000001",
            "upper": None,
            "rate_percent": "12",
            "applies_to": "resident or non-resident individual",
            "compare_group_id": "first_schedule_rates",
        },
    ]
    terminal = [
        {
            "entity_kind": "rate_band",
            "band_index": 1,
            "lower": "0",
            "upper": "10000000",
            "rate_percent": "0",
            "applies_to": "resident or non-resident individual",
            "compare_group_id": TERMINAL_BENEFIT_GROUP,
            "employment_period_condition": PERIOD_NA,
        },
        {
            "entity_kind": "rate_band",
            "band_index": 2,
            "lower": "10000000",
            "upper": "20000000",
            "rate_percent": "6",
            "applies_to": "resident or non-resident individual",
            "compare_group_id": TERMINAL_BENEFIT_GROUP,
            "employment_period_condition": PERIOD_NA,
        },
        {
            "entity_kind": "rate_band",
            "band_index": 3,
            "lower": "20000000",
            "upper": None,
            "rate_percent": "12",
            "applies_to": "resident or non-resident individual",
            "compare_group_id": TERMINAL_BENEFIT_GROUP,
            "employment_period_condition": PERIOD_NA,
        },
    ]
    assert validate_rate_band_set(ordinary + terminal) == []


def test_gratuity_eligibility_stays_individual_for_terminal_group() -> None:
    assert (
        infer_engine_scope(
            compare_group_id=TERMINAL_BENEFIT_GROUP,
            eligibility_text="retiring gratuity, commuted pension or compensation for loss of office",
        )
        == "individual"
    )
    assert (
        infer_engine_scope(
            compare_group_id="employment_income_tax",
            eligibility_text="a retiring gratuity paid to an employee",
        )
        == "individual"
    )


def test_compile_both_families_2018_19() -> None:
    _reliefs, rates = compile_maps(_family_rows())
    rows = rates["2018_19"]
    ordinary = [row for row in rows if row.get("compare_group_id") != TERMINAL_BENEFIT_GROUP]
    terminal = _terminal_in(rows)
    assert [row["rate_percent"] for row in ordinary] == ["4"]
    conditions = {row["employment_period_condition"] for row in terminal}
    assert PERIOD_UPTO_20 in conditions
    assert PERIOD_OVER_20 in conditions
    assert PERIOD_NA not in conditions
    assert all(row["source_doc_id"] == "oee-act-24-2017" for row in terminal)


def test_compile_2017_terminal_absent_from_2020_onward() -> None:
    _reliefs, rates = compile_maps(_family_rows())
    for ya in ("2020_21", "2021_22", "2025_26"):
        terminal = _terminal_in(rates[ya])
        assert terminal
        assert all(row["source_doc_id"] == "oee-act-10-2021" for row in terminal)
        assert {row["employment_period_condition"] for row in terminal} == {PERIOD_NA}
        assert "0" in {row["rate_percent"] for row in terminal}
        assert "6" in {row["rate_percent"] for row in terminal}
        assert "12" in {row["rate_percent"] for row in terminal}


def test_compile_2019_20_has_two_period_slices() -> None:
    _reliefs, rates = compile_maps(_family_rows())
    terminal = _terminal_in(rates["2019_20"])
    periods = {(row.get("period_from"), row.get("period_to")) for row in terminal}
    assert ("2019-04-01", "2019-12-31") in periods
    assert ("2020-01-01", "2020-03-31") in periods
    pre = [row for row in terminal if row.get("period_to") == "2019-12-31"]
    post = [row for row in terminal if row.get("period_from") == "2020-01-01"]
    assert {row["employment_period_condition"] for row in pre} == {PERIOD_UPTO_20, PERIOD_OVER_20}
    assert {row["employment_period_condition"] for row in post} == {PERIOD_NA}
    assert all(row["source_doc_id"] == "oee-act-24-2017" for row in pre)
    assert all(row["source_doc_id"] == "oee-act-10-2021" for row in post)


def test_later_ordinary_ladder_still_replaces_base() -> None:
    _reliefs, rates = compile_maps(_family_rows())
    ordinary_2018 = [
        row for row in rates["2018_19"] if row.get("compare_group_id") != TERMINAL_BENEFIT_GROUP
    ]
    ordinary_2025 = [
        row for row in rates["2025_26"] if row.get("compare_group_id") != TERMINAL_BENEFIT_GROUP
    ]
    assert ordinary_2018[0]["rate_percent"] == "4"
    assert ordinary_2025[0]["rate_percent"] == "6"


def _promote_2025_with_terminal(db_session: Session) -> None:
    seed_act_document(db_session, source_doc_id="oee-fixture-act-2025", title="Fixture 2025")
    promote_act_run(db_session, load_extract_fixture("act_extract_2025.json"))
    for i, (lower, upper, rate) in enumerate(
        [("0", "10000000", "0"), ("10000000", "20000000", "6"), ("20000000", None, "12")],
        start=1,
    ):
        db_session.add(
            _terminal(
                source="oee-act-10-2021",
                entry=f"live-t-{i}",
                index=i,
                lower=lower,
                upper=upper,
                rate=rate,
                ef="2020-01-01",
                et="",
                group=TERMINAL_BENEFIT_GROUP,
                row_id=400 + i,
                applies="a person",
            )
        )
    db_session.flush()
    recompile_year_views(db_session, persist=True)
    db_session.commit()


def test_calculate_2025_salary_only_has_empty_terminal_slabs(db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    result = calculate(db_session, "2025_26", TYPICAL_INCOME, claims=[])
    assert result["tax_payable"] == 270_000
    assert result["slab_lines"][0]["rate_percent"] == 6.0
    assert result["terminal_benefit_slab_lines"] == []
    assert result["terminal_benefit_tax"] == 0


def test_calculate_gratuity_only_uses_10m_ladder(db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    result = calculate(
        db_session,
        "2025_26",
        {
            "employment": 0,
            "business": 0,
            "investment": 0,
            "other": 0,
            "terminal_benefit_amount": 12_000_000,
            "terminal_benefit_type": "retiring_gratuity",
        },
        claims=[],
    )
    assert result["terminal_benefit_tax"] == 120_000
    assert result["tax_payable"] == 120_000
    rates = [line["rate_percent"] for line in result["terminal_benefit_slab_lines"]]
    assert 0.0 in rates
    assert 6.0 in rates
    assert 12.0 in rates
    assert all(line["rate_percent"] != 6.0 or line.get("slice", 0) >= 0 for line in result["slab_lines"])


def test_mixed_salary_gratuity_does_not_apply_terminal_to_salary(db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    result = calculate(
        db_session,
        "2025_26",
        {
            **TYPICAL_INCOME,
            "terminal_benefit_amount": 12_000_000,
            "terminal_benefit_type": "retiring_gratuity",
        },
        claims=[],
    )
    assert result["slab_lines"][0]["rate_percent"] == 6.0
    assert result["taxable_income"] == 2_000_000
    assert result["terminal_benefit_tax"] == 120_000
    assert result["tax_payable"] == 390_000
    ordinary_slices_at_zero = [
        line for line in result["slab_lines"] if line["rate_percent"] == 0.0 and line["slice"] > 0
    ]
    assert ordinary_slices_at_zero == []


def test_2018_19_upto_and_over_20_ladders(db_session: Session) -> None:
    rows = _family_rows()
    reliefs, rates = compile_maps(rows)
    persist_year_views(db_session, reliefs, rates)
    db_session.commit()
    upto = calculate(
        db_session,
        "2018_19",
        {
            "employment": 0,
            "terminal_benefit_amount": 2_500_000,
            "terminal_benefit_type": "commuted_pension",
            "employment_period_over_20_years": False,
        },
        claims=[],
    )
    over = calculate(
        db_session,
        "2018_19",
        {
            "employment": 0,
            "terminal_benefit_amount": 2_500_000,
            "terminal_benefit_type": "commuted_pension",
            "employment_period_over_20_years": True,
        },
        claims=[],
    )
    assert upto["terminal_benefit_tax"] == 25_000
    assert over["terminal_benefit_tax"] == 0


def test_2019_20_period_switch(db_session: Session) -> None:
    reliefs, rates = compile_maps(_family_rows())
    persist_year_views(db_session, reliefs, rates)
    db_session.commit()
    pre = calculate(
        db_session,
        "2019_20",
        {
            "employment": 0,
            "terminal_benefit_amount": 2_500_000,
            "terminal_benefit_type": "retiring_gratuity",
            "employment_period_over_20_years": False,
            "terminal_benefit_period": "pre_2020",
        },
        claims=[],
    )
    post = calculate(
        db_session,
        "2019_20",
        {
            "employment": 0,
            "terminal_benefit_amount": 12_000_000,
            "terminal_benefit_type": "retiring_gratuity",
            "terminal_benefit_period": "from_2020_01_01",
        },
        claims=[],
    )
    missing = calculate(
        db_session,
        "2019_20",
        {
            "employment": 0,
            "terminal_benefit_amount": 12_000_000,
            "terminal_benefit_type": "retiring_gratuity",
        },
        claims=[],
    )
    assert pre["terminal_benefit_tax"] == 25_000
    assert post["terminal_benefit_tax"] == 120_000
    assert missing["terminal_benefit_tax"] == 0
    assert missing["terminal_benefit_slab_lines"] == []


def test_calculate_two_terminal_benefits_aggregated_once(db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    result = calculate(
        db_session,
        "2025_26",
        {
            **TYPICAL_INCOME,
            "terminal_benefits": [
                {"type": "retiring_gratuity", "amount": 12_000_000},
                {"type": "commuted_pension", "amount": 1_000_000},
            ],
        },
        claims=[],
    )
    assert result["slab_lines"][0]["rate_percent"] == 6.0
    ordinary_zero = [
        line for line in result["slab_lines"] if line["rate_percent"] == 0.0 and line["slice"] > 0
    ]
    assert ordinary_zero == []
    types = [line["type"] for line in result["terminal_benefit_lines"]]
    assert types == ["retiring_gratuity", "commuted_pension"]
    assert [line["amount"] for line in result["terminal_benefit_lines"]] == [12_000_000, 1_000_000]
    assert all(line["tax"] is None for line in result["terminal_benefit_lines"])
    expected = _aggregate_terminal_tax(db_session, "2025_26", 13_000_000)
    assert expected == 180_000
    assert result["terminal_benefit_tax"] == expected
    assert result["tax_payable"] == 270_000 + expected
    assert result["employment_income"] == TYPICAL_INCOME["employment"]
    assert result["terminal_benefit_amount"] == 13_000_000


def test_11m_plus_71m_aggregates_to_82m_before_tax(db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    result = calculate(
        db_session,
        "2025_26",
        {
            "employment": 0,
            "business": 0,
            "investment": 0,
            "other": 0,
            "terminal_benefits": [
                {"type": "commuted_pension", "amount": 11_000_000},
                {"type": "retiring_gratuity", "amount": 71_000_000},
            ],
        },
        claims=[],
    )
    expected = _aggregate_terminal_tax(db_session, "2025_26", 82_000_000)
    assert expected == 8_040_000
    assert result["terminal_benefit_amount"] == 82_000_000
    assert result["terminal_benefit_tax"] == expected
    assert result["tax_payable"] == expected
    assert result["terminal_benefit_tax"] != 6_780_000
    independent = _aggregate_terminal_tax(db_session, "2025_26", 11_000_000) + _aggregate_terminal_tax(
        db_session, "2025_26", 71_000_000
    )
    assert independent == 6_780_000
    assert result["terminal_benefit_tax"] != independent


def test_salary_plus_multiple_terminal_keeps_ordinary_slabs(db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    result = calculate(
        db_session,
        "2025_26",
        {
            "employment": 2_000_000,
            "business": 0,
            "investment": 0,
            "other": 0,
            "interest": 0,
            "rents": 0,
            "terminal_benefits": [
                {"type": "retiring_gratuity", "amount": 12_000_000},
                {"type": "commuted_pension", "amount": 1_000_000},
            ],
        },
        claims=[],
    )
    assert result["employment_income"] == 2_000_000
    assert result["slab_lines"][0]["rate_percent"] == 6.0
    ordinary_zero = [
        line for line in result["slab_lines"] if line["rate_percent"] == 0.0 and line["slice"] > 0
    ]
    assert ordinary_zero == []
    expected = _aggregate_terminal_tax(db_session, "2025_26", 13_000_000)
    assert result["terminal_benefit_tax"] == expected


def test_list_path_does_not_subtract_terminal_from_employment(db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    result = calculate(
        db_session,
        "2025_26",
        {
            "employment": 2_000_000,
            "business": 0,
            "investment": 0,
            "other": 0,
            "interest": 0,
            "rents": 0,
            "terminal_benefits": [{"type": "retiring_gratuity", "amount": 2_000_000}],
        },
        claims=[],
    )
    assert result["employment_income"] == 2_000_000
    assert result["terminal_benefit_lines"][0]["amount"] == 2_000_000
    assert result["terminal_benefit_tax"] == 0


def test_2018_19_period_applied_per_item(db_session: Session) -> None:
    reliefs, rates = compile_maps(_family_rows())
    persist_year_views(db_session, reliefs, rates)
    db_session.commit()
    result = calculate(
        db_session,
        "2018_19",
        {
            "employment": 0,
            "terminal_benefits": [
                {
                    "type": "commuted_pension",
                    "amount": 2_500_000,
                    "employment_period_over_20_years": False,
                },
                {
                    "type": "retiring_gratuity",
                    "amount": 2_500_000,
                    "employment_period_over_20_years": True,
                },
            ],
        },
        claims=[],
    )
    by_type = {line["type"]: line for line in result["terminal_benefit_lines"]}
    assert by_type["commuted_pension"]["amount"] == 2_500_000
    assert by_type["retiring_gratuity"]["amount"] == 2_500_000
    assert all(line["tax"] is None for line in result["terminal_benefit_lines"])
    assert result["terminal_benefit_tax"] == 25_000


def test_2019_20_period_applied_per_item(db_session: Session) -> None:
    reliefs, rates = compile_maps(_family_rows())
    persist_year_views(db_session, reliefs, rates)
    db_session.commit()
    result = calculate(
        db_session,
        "2019_20",
        {
            "employment": 0,
            "terminal_benefits": [
                {
                    "type": "retiring_gratuity",
                    "amount": 2_500_000,
                    "employment_period_over_20_years": False,
                    "terminal_benefit_period": "pre_2020",
                },
                {
                    "type": "commuted_pension",
                    "amount": 12_000_000,
                    "terminal_benefit_period": "from_2020_01_01",
                },
            ],
        },
        claims=[],
    )
    by_type = {line["type"]: line for line in result["terminal_benefit_lines"]}
    assert by_type["retiring_gratuity"]["amount"] == 2_500_000
    assert by_type["commuted_pension"]["amount"] == 12_000_000
    assert all(line["tax"] is None for line in result["terminal_benefit_lines"])
    assert result["terminal_benefit_tax"] == 145_000


def test_2018_19_same_ladder_benefits_aggregated(db_session: Session) -> None:
    reliefs, rates = compile_maps(_family_rows())
    persist_year_views(db_session, reliefs, rates)
    db_session.commit()
    result = calculate(
        db_session,
        "2018_19",
        {
            "employment": 0,
            "terminal_benefits": [
                {
                    "type": "retiring_gratuity",
                    "amount": 4_000_000,
                    "employment_period_over_20_years": False,
                },
                {
                    "type": "commuted_pension",
                    "amount": 3_000_000,
                    "employment_period_over_20_years": False,
                },
            ],
        },
        claims=[],
    )
    expected = _aggregate_terminal_tax(
        db_session, "2018_19", 7_000_000, over_20_years=False
    )
    independent = _aggregate_terminal_tax(
        db_session, "2018_19", 4_000_000, over_20_years=False
    ) + _aggregate_terminal_tax(db_session, "2018_19", 3_000_000, over_20_years=False)
    assert result["terminal_benefit_amount"] == 7_000_000
    assert result["terminal_benefit_tax"] == expected
    assert result["terminal_benefit_tax"] != independent
    assert [line["type"] for line in result["terminal_benefit_lines"]] == [
        "retiring_gratuity",
        "commuted_pension",
    ]


def test_2019_20_aggregates_within_period_not_across(db_session: Session) -> None:
    reliefs, rates = compile_maps(_family_rows())
    persist_year_views(db_session, reliefs, rates)
    db_session.commit()
    result = calculate(
        db_session,
        "2019_20",
        {
            "employment": 0,
            "terminal_benefits": [
                {
                    "type": "retiring_gratuity",
                    "amount": 2_500_000,
                    "employment_period_over_20_years": False,
                    "terminal_benefit_period": "pre_2020",
                },
                {
                    "type": "etf_retirement_payment",
                    "amount": 2_500_000,
                    "employment_period_over_20_years": False,
                    "terminal_benefit_period": "pre_2020",
                },
                {
                    "type": "commuted_pension",
                    "amount": 12_000_000,
                    "terminal_benefit_period": "from_2020_01_01",
                },
            ],
        },
        claims=[],
    )
    pre = _aggregate_terminal_tax(
        db_session,
        "2019_20",
        5_000_000,
        over_20_years=False,
        period="pre_2020",
    )
    post = _aggregate_terminal_tax(
        db_session,
        "2019_20",
        12_000_000,
        period="from_2020_01_01",
    )
    per_row_pre = _aggregate_terminal_tax(
        db_session, "2019_20", 2_500_000, over_20_years=False, period="pre_2020"
    ) * 2
    assert result["terminal_benefit_tax"] == pre + post
    assert result["terminal_benefit_tax"] != per_row_pre + post
    types = [line["type"] for line in result["terminal_benefit_lines"]]
    assert types == ["retiring_gratuity", "etf_retirement_payment", "commuted_pension"]


def test_rates_endpoint_keeps_ordinary_separate(client, db_session: Session) -> None:
    _promote_2025_with_terminal(db_session)
    response = client.get("/rates/2025_26")
    assert response.status_code == 200
    body = response.json()
    assert body["band_count"] == len(body["bands"])
    assert all(row.get("compare_group_id") != TERMINAL_BENEFIT_GROUP for row in body["bands"])
    assert body["terminal_benefit_ladders"]
    ladder = body["terminal_benefit_ladders"][0]
    assert ladder["compare_group_id"] == TERMINAL_BENEFIT_GROUP
    audit = client.get("/rates/2025_26/audit", params={"family": TERMINAL_BENEFIT_GROUP})
    assert audit.status_code == 200
    assert audit.json()["band_count"] >= 3
