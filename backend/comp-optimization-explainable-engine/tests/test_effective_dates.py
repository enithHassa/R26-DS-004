"""Deterministic effective_from/to lift from quote phrases (no GPT)."""

from __future__ import annotations

from oe_engine_app.services.effective_dates import (
    dates_still_missing,
    fill_effective_dates,
    lift_effective_dates,
)
from oe_engine_app.services.extract import extract_window
from oe_engine_app.services.extract_llm import (
    Pass1ActPayload,
    Pass1Eligibility,
    Pass1Relief,
)
from oe_engine_app.services.windows import DocText, FocusWindow
from tests.test_extract_dry import _FakeLLM


def test_prior_to_sets_effective_to_day_before() -> None:
    start, end = lift_effective_dates(
        "Rs. 500,000, for each year of assessment prior to January 1, 2020;",
    )
    assert start == ""
    assert end == "2019-12-31"


def test_commencing_on_or_after_sets_from() -> None:
    start, end = lift_effective_dates(
        "Rs. 3,000,000, for each year of assessment commencing on or after January 1, 2020,",
    )
    assert start == "2020-01-01"
    assert end == ""


def test_commencing_from_sets_from() -> None:
    start, _end = lift_effective_dates(
        "the taxable income of a resident or non-resident individual for a "
        "year of assessment commencing from April 1, 2025 shall be taxed",
    )
    assert start == "2025-04-01"


def test_commencing_on_without_or_after() -> None:
    start, _end = lift_effective_dates(
        "gains and profits from dividends for the second six months of the "
        "year of assessment commencing on April 1, 2022, such gains and profits "
        "shall be taxed at the rate of 15%",
    )
    assert start == "2022-04-01"


def test_commencing_on_or_prior_to_is_not_a_from_date() -> None:
    start, end = lift_effective_dates(
        "for a year of assessment commencing on or prior to April 1, 2022",
    )
    assert start == ""
    assert end == ""


def test_on_or_after_sets_from() -> None:
    start, _end = lift_effective_dates(
        "incurred for a year of assessment on or after January 1, 2020: - (i) health",
    )
    assert start == "2020-01-01"


def test_with_effect_from() -> None:
    start, _end = lift_effective_dates(
        "taxed at the rate of 24% with effect from January 1, 2020.",
    )
    assert start == "2020-01-01"


def test_does_not_overwrite_existing() -> None:
    start, end = lift_effective_dates(
        "prior to January 1, 2020 commencing on or after January 1, 2020",
        effective_from="2021-04-01",
        effective_to="2022-03-31",
    )
    assert start == "2021-04-01"
    assert end == "2022-03-31"


def test_act_year_is_not_a_qualifying_clause() -> None:
    start, end = lift_effective_dates(
        "President's Fund Act, No. 7 of 1978 or the National Defence Fund",
    )
    assert start == ""
    assert end == ""


def test_day_month_gazette_order() -> None:
    start, _end = lift_effective_dates("with effect from 1 April 2021")
    assert start == "2021-04-01"
    _start, end = lift_effective_dates("for each year of assessment prior to 1 January 2020")
    assert end == "2019-12-31"


def test_mixed_prior_and_from_only_lifts_from() -> None:
    start, end = lift_effective_dates(
        "taxed at the rate of 28% prior to January 1, 2020 and 24% with effect from January 1, 2020.",
    )
    assert start == "2020-01-01"
    assert end == ""


def test_w010_quotes() -> None:
    _, end = lift_effective_dates(
        "“(a) (i) Rs. 500,000, for each year of assessment prior to January 1, 2020;"
    )
    assert end == "2019-12-31"
    start, _ = lift_effective_dates(
        "(ii)Rs. 3,000,000, for each year of assessment commencing on or after January 1, 2020,"
    )
    assert start == "2020-01-01"
    start, _ = lift_effective_dates(
        "incurred for a year of assessment on or after January 1, 2020: - (i) health"
    )
    assert start == "2020-01-01"


def test_extract_fills_empty_dates_from_quote() -> None:
    quote = "Rs. 500,000, for each year of assessment prior to January 1, 2020;"
    stream = (
        "FIFTH SCHEDULE\n"
        "(2) The following reliefs shall be deducted:\n"
        f"(a) {quote}\n"
    )
    doc = DocText(
        source_doc_id="oee-act-fixture",
        title="Fixture Act",
        tier="act",
        stream=stream,
        tables_blob="",
        page_spans=[(1, 0, len(stream))],
        tables_by_page={},
    )
    window = FocusWindow(
        window_id="fifth_schedule",
        heading="Fifth Schedule",
        start=0,
        end=len(stream),
        stream_slice=stream,
        tables_slice="",
        page_start=1,
        page_end=1,
    )
    payload = Pass1ActPayload(
        reliefs=[
            Pass1Relief(
                compare_group_id="personal_relief",
                display_name="Personal relief",
                paragraph_ref="2(a)(i)",
                section_ref="Fifth Schedule",
                act_name="Fixture Act",
                cap_amount="500000",
                unit="lkr",
                quote=quote,
                eligibility=Pass1Eligibility(text="resident individual", quote=quote),
                required_evidence=[],
                filing_line="",
                stacking="",
                effective_from="",
                effective_to="",
            )
        ],
        rate_bands=[],
    )
    entities = extract_window(doc=doc, window=window, llm=_FakeLLM(payload), dry_run=False)
    assert entities[0]["effective_from"] == ""
    assert entities[0]["effective_to"] == "2019-12-31"


def test_foreign_currency_quote_lifts_effective_to() -> None:
    _, end = lift_effective_dates(
        "Rs. 15,000,000 for each year of assessment, up to the total of such income "
        "for the year up to December 31, 2019;",
    )
    assert end == "2019-12-31"


def test_scan_helper_after_fill() -> None:
    row = {
        "entity_kind": "relief",
        "quote": "Rs. 3,000,000 commencing on or after January 1, 2020",
        "effective_from": "",
        "effective_to": "",
    }
    assert dates_still_missing(row) is True
    fill_effective_dates(row)
    assert row["effective_from"] == "2020-01-01"
    assert dates_still_missing(row) is False
