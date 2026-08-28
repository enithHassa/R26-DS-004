"""Dry extract with a mocked window (no live API key)."""

from __future__ import annotations

from oe_engine_app.schemas.extract import ReliefEntity, terminus_for_tier
from oe_engine_app.services.extract import _normalize_unit, extract_window
from oe_engine_app.services.extract_llm import (
    Pass1ActPayload,
    Pass1Eligibility,
    Pass1RateBand,
    Pass1Relief,
    QuoteCheck,
)
from oe_engine_app.services.windows import DocText, FocusWindow, list_windows


class _FakeLLM:
    def __init__(self, payload: Pass1ActPayload) -> None:
        self.payload = payload

    def pass1_act(self, **_kwargs: object) -> Pass1ActPayload:
        return self.payload

    def pass1_guide(self, **_kwargs: object) -> object:
        raise AssertionError("guide pass not used")

    def pass1_consolidated(self, **_kwargs: object) -> object:
        raise AssertionError("consolidated pass not used")

    def pass2(self, **_kwargs: object) -> QuoteCheck:
        return QuoteCheck(verbatim=True, closest_quote="", note="mock")


QUOTE = "Personal relief of rupees one million two hundred thousand"


def _tiny_doc() -> tuple[DocText, FocusWindow]:
    stream = (
        "FIFTH SCHEDULE\n"
        "(2) The following reliefs shall be deducted:\n"
        f"(a) {QUOTE} for each year of assessment.\n"
        "Evidence: a salary sheet is not required by this window.\n"
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
    return doc, window


def test_mocked_window_extract_matches_relief_schema() -> None:
    doc, window = _tiny_doc()
    payload = Pass1ActPayload(
        reliefs=[
            Pass1Relief(
                compare_group_id="personal_relief",
                display_name="Personal relief",
                paragraph_ref="2(a)",
                section_ref="Fifth Schedule",
                act_name="Fixture Act",
                cap_amount="1200000",
                unit="lkr",
                quote=QUOTE,
                eligibility=Pass1Eligibility(
                    text="Available to a resident individual",
                    quote=QUOTE,
                ),
                required_evidence=[],
                filing_line="",
                stacking="",
                effective_from="",
                effective_to="",
                question_prompt="Did personal relief apply to you this year?",
                help="This relief is applied automatically.",
                input_kind="notice",
            )
        ],
        rate_bands=[],
    )
    entities = extract_window(doc=doc, window=window, llm=_FakeLLM(payload), dry_run=False)
    assert len(entities) == 1
    parsed = ReliefEntity.model_validate(entities[0])
    assert parsed.entity_kind == "relief"
    assert parsed.eligibility.review_status == "pending"
    assert parsed.quote_ok_window is True
    assert parsed.quote_ok_full_doc is True
    assert parsed.included is True
    assert parsed.engine_scope == "individual"
    assert parsed.cap_amount == "1200000"
    assert parsed.unit == "lkr"
    assert parsed.required_evidence == []
    assert parsed.filing_line == ""
    assert parsed.stacking == ""
    assert parsed.question_prompt == "Did personal relief apply to you this year?"
    assert parsed.help == "This relief is applied automatically."
    assert parsed.input_kind == "notice"


def test_mocked_rate_band_shape() -> None:
    tables = "Taxable Income | Tax Payable\nNot Exceeding Rs. 600,000 | 4%"
    stream = "FIRST SCHEDULE\nTax rates for a resident individual.\n"
    doc = DocText(
        source_doc_id="oee-act-fixture",
        title="Fixture Act",
        tier="act",
        stream=stream,
        tables_blob=tables,
        page_spans=[(1, 0, len(stream))],
        tables_by_page={1: tables},
    )
    window = FocusWindow(
        window_id="first_schedule",
        heading="First Schedule",
        start=0,
        end=len(stream),
        stream_slice=stream,
        tables_slice=tables,
        page_start=1,
        page_end=1,
    )
    payload = Pass1ActPayload(
        reliefs=[],
        rate_bands=[
            Pass1RateBand(
                band_index=1,
                band_label="Taxable Income",
                lower="0",
                upper="600000",
                rate_percent="4",
                applies_to="resident individual",
                section_ref="First Schedule",
                act_name="Fixture Act",
                effective_from="2017-04-01",
                quote="Not Exceeding Rs. 600,000 | 4%",
                compare_group_id="first_schedule_rates",
            )
        ],
    )
    entities = extract_window(doc=doc, window=window, llm=_FakeLLM(payload), dry_run=False)
    assert entities[0]["entity_kind"] == "rate_band"
    assert entities[0]["quote_source"] == "table_render"
    assert entities[0]["lower"] == "0"
    assert entities[0]["rate_percent"] == "4"


def test_dry_run_extract_window_is_empty() -> None:
    doc, window = _tiny_doc()
    assert extract_window(doc=doc, window=window, llm=_FakeLLM(Pass1ActPayload(reliefs=[], rate_bands=[])), dry_run=True) == []


def test_list_windows_single_short_doc() -> None:
    stream = "x" * 4000
    doc = DocText(
        source_doc_id="oee-act-14-2023",
        title="Small Act",
        tier="act",
        stream=stream,
        tables_blob="",
        page_spans=[(1, 0, len(stream))],
    )
    windows = list_windows(doc)
    assert len(windows) == 1
    assert windows[0].char_count == 4000


def test_extract_focus_windows_long_act_keeps_named_schedules() -> None:
    from oe_engine_app.services.windows import extract_focus_windows

    body = "x" * 25_000
    stream = (
        body
        + "\nFIRST SCHEDULE (Section 2)\n TAX RATES\n"
        + "Taxable income of a resident individual.\n"
        + "y" * 8_000
        + "\nFIFTH SCHEDULE\nQUALIFYING PAYMENTS AND RELIEFS\n"
        + "Personal relief of rupees five hundred thousand.\n"
        + "z" * 8_000
    )
    doc = DocText(
        source_doc_id="oee-act-24-2017",
        title="Base Act",
        tier="act",
        stream=stream,
        tables_blob="",
        page_spans=[(1, 0, len(stream))],
    )
    windows = extract_focus_windows(doc)
    ids = [w.window_id for w in windows]
    assert "first_schedule" in ids
    assert "fifth_schedule" in ids
    first = next(w for w in windows if w.window_id == "first_schedule")
    fifth = next(w for w in windows if w.window_id == "fifth_schedule")
    assert "TAX RATES" in first.text
    assert "QUALIFYING PAYMENTS" in fifth.text
    assert "QUALIFYING PAYMENTS" not in first.text


def test_named_fifth_includes_dated_personal_relief_and_clips_sixth() -> None:
    from oe_engine_app.services.windows import extract_focus_windows

    stream = (
        "x" * 25_000
        + "\nFIFTH SCHEDULE (Section 52)\nQUALIFYING PAYMENTS AND RELIEFS\n"
        + "(a) (i) Rs. 500,000, for each year of assessment prior to January 1, 2020;\n"
        + "(v) Rs. 1,800,000, for each year of assessment commencing on or after April 1, 2025,\n"
        + "y" * 2_000
        + "\nSIXTH SCHEDULE (Section 104)\nTEMPORARY CONCESSIONS Enhanced Capital Allowances\n"
        + "z" * 8_000
    )
    doc = DocText(
        source_doc_id="oee-consolidated-2025",
        title="Consolidated",
        tier="consolidated",
        stream=stream,
        tables_blob="",
        page_spans=[(1, 0, len(stream))],
    )
    windows = extract_focus_windows(doc)
    fifth = next(w for w in windows if w.window_id == "fifth_schedule")
    assert "1,800,000" in fifth.text
    assert "TEMPORARY CONCESSIONS" not in fifth.text


def test_consolidated_focus_skips_admin_sliding_windows() -> None:
    from oe_engine_app.services.windows import extract_focus_windows

    stream = (
        "CHAPTER XII ASSESSMENTS search and seizure with warrant. " * 400
        + "\nFIRST SCHEDULE (Section 2)\n TAX RATES\n"
        + "Taxable income of a resident individual.\n"
        + "Not Exceeding Rs. 600,000 4% of the amount in excess of Rs. 0\n"
        + "y" * 1_000
        + "\nFIFTH SCHEDULE\nQUALIFYING PAYMENTS AND RELIEFS\n"
        + "Personal relief of rupees five hundred thousand.\n"
        + "z" * 1_000
    )
    doc = DocText(
        source_doc_id="oee-consolidated-2025",
        title="Consolidated",
        tier="consolidated",
        stream=stream,
        tables_blob="",
        page_spans=[(1, 0, len(stream))],
    )
    windows = extract_focus_windows(doc)
    ids = [w.window_id for w in windows]
    assert ids[0] == "fifth_schedule" or "fifth_schedule" in ids
    assert "first_schedule" in ids
    assert "fifth_schedule" in ids
    assert all(not wid.startswith("w") for wid in ids)


def test_guide_focus_keeps_relief_chapters_not_admin() -> None:
    from oe_engine_app.services.windows import extract_focus_windows

    stream = (
        "CHAPTER XII ASSESSMENTS search and seizure with warrant. " * 400
        + "\n3.4.2 Aggregate reliefs referred to in section 52\n"
        + "(a) Personal relief of Rs. 500,000 for each year of assessment. "
        + "This relief is available for resident individuals.\n"
        + "y" * 2_000
    )
    doc = DocText(
        source_doc_id="oee-guide-ira",
        title="Guide",
        tier="guide",
        stream=stream,
        tables_blob="",
        page_spans=[(1, 0, len(stream))],
    )
    windows = extract_focus_windows(doc)
    blob = "\n".join(w.stream_slice for w in windows)
    assert "Personal relief" in blob
    assert all("Personal relief" in w.stream_slice or "Aggregate reliefs" in w.stream_slice for w in windows)


def test_canonical_guide_compare_group_aliases() -> None:
    from oe_engine_app.services.extract import canonical_guide_compare_group

    assert canonical_guide_compare_group("personal") == "personal_relief"
    assert canonical_guide_compare_group("senior_citizen_interest_relief") == (
        "senior_citizen_interest_income_relief"
    )
    assert canonical_guide_compare_group("personal_relief") == "personal_relief"


def test_terminus_by_tier() -> None:
    assert terminus_for_tier("act") == "review_then_promote"
    assert terminus_for_tier("guide") == "display_no_promote"
    assert terminus_for_tier("consolidated") == "facts_and_mismatch_no_promote"


def test_tab_rate_table_pipe_quote_is_included() -> None:
    tables = (
        "Taxable income\tTax Payable\n"
        "Not exceeding Rs. 1,000,000\t6% of the amount in excess of Rs.0\n"
        "Exceeding Rs. 2,500,000\tRs. 420,000 plus 36% of the amount in excess of Rs. 2,500,000"
    )
    stream = "FIRST SCHEDULE\nsubparagraph (1D) taxable income of a resident individual.\n"
    doc = DocText(
        source_doc_id="oee-act-02-2025",
        title="Act 02 of 2025",
        tier="act",
        stream=stream,
        tables_blob=tables,
        page_spans=[(1, 0, len(stream))],
        tables_by_page={1: tables},
    )
    window = FocusWindow(
        window_id="w000",
        heading="PARLIAMENT OF THE DEMOCRATIC SOCIALIST REPUBLIC",
        start=0,
        end=len(stream),
        stream_slice=stream,
        tables_slice=tables,
        page_start=1,
        page_end=1,
    )
    assert window.text.startswith("### Tables on these pages")
    assert "Not exceeding Rs. 1,000,000 | 6%" in window.text
    payload = Pass1ActPayload(
        reliefs=[],
        rate_bands=[
            Pass1RateBand(
                band_index=1,
                band_label="Not exceeding Rs. 1,000,000",
                lower="0",
                upper="1000000",
                rate_percent="6",
                applies_to="resident or non-resident individual",
                section_ref="First Schedule",
                act_name="Act 02 of 2025",
                effective_from="2025-04-01",
                quote="Not exceeding Rs. 1,000,000 | 6% of the amount in excess of Rs.0",
                compare_group_id="individual_income_tax_slab",
            )
        ],
    )
    entities = extract_window(doc=doc, window=window, llm=_FakeLLM(payload), dry_run=False)
    assert entities[0]["included"] is True
    assert entities[0]["quote_ok_window"] is True
    assert entities[0]["quote_ok_full_doc"] is True
    assert entities[0]["quote_source"] == "table_render"


def test_normalize_unit_maps_currency_to_lkr() -> None:
    assert _normalize_unit("currency") == "lkr"
    assert _normalize_unit("%") == "percent"
    assert _normalize_unit("text") == "text"


def test_act_admin_focus_stops_at_named_schedules() -> None:
    from oe_engine_app.services.windows import extract_focus_windows

    stream = (
        "x" * 25_000
        + "\nFIRST SCHEDULE (Section 2)\n TAX RATES\n"
        + "Taxable income of a resident individual.\n"
        + "y" * 8_000
        + "\nFIFTH SCHEDULE\nQUALIFYING PAYMENTS AND RELIEFS\n"
        + "Personal relief of rupees five hundred thousand.\n"
        + "z" * 8_000
        + "\nLater reprint of personal relief Rs. 2,000,000.\n"
        + "n" * 40_000
    )
    doc = DocText(
        source_doc_id="oee-act-99-2026",
        title="Amendment",
        tier="act",
        stream=stream,
        tables_blob="",
        page_spans=[(1, 0, len(stream))],
    )
    full = extract_focus_windows(doc)
    admin = extract_focus_windows(doc, act_admin=True)
    assert "first_schedule" in {w.window_id for w in admin}
    assert "fifth_schedule" in {w.window_id for w in admin}
    assert all(not w.window_id.startswith("w") for w in admin)
    assert any(w.window_id.startswith("w") for w in full)


def test_collapse_reprint_reliefs_keeps_dated_variants() -> None:
    from oe_engine_app.services.extract_dedupe import (
        collapse_duplicate_extract_entities,
        scrub_interview_fields,
    )

    rows = [
        {
            "entity_kind": "relief",
            "entry_id": "doc:fifth_schedule:relief:0",
            "compare_group_id": "personal_relief",
            "cap_amount": "2000000",
            "effective_from": "2026-04-01",
            "quote": "Rs. 2,000,000, for the year of assessment commencing on April 1, 2026.",
            "included": True,
            "review_status": "pending",
            "question_prompt": (
                "What is your personal relief amount for the year of assessment "
                "commencing on April 1, 2026?"
            ),
            "help": "Enter the personal relief amount for the specified year.",
        },
        {
            "entity_kind": "relief",
            "entry_id": "doc:w006:relief:0",
            "compare_group_id": "personal_relief",
            "cap_amount": "2000000",
            "effective_from": "",
            "quote": "The synthetic amendment changes the personal relief to Rs. 2,000,000.",
            "included": True,
            "review_status": "pending",
            "question_prompt": "What is your personal relief for the assessment year 2026/27?",
            "help": "Enter the amount of personal relief applicable for the year 2026/27.",
        },
        {
            "entity_kind": "relief",
            "entry_id": "doc:fifth_schedule:relief:1",
            "compare_group_id": "personal_relief",
            "cap_amount": "1800000",
            "effective_from": "2025-04-01",
            "quote": "Rs. 1,800,000, for each year of assessment commencing on or after April 1, 2025.",
            "included": True,
            "review_status": "pending",
        },
        {
            "entity_kind": "relief",
            "entry_id": "doc:w009:relief:0",
            "compare_group_id": "qualifying_computer_equipment",
            "cap_amount": "",
            "effective_from": "",
            "quote": "A computer or laptop purchased and used primarily by an individual.",
            "included": True,
            "review_status": "pending",
        },
        {
            "entity_kind": "relief",
            "entry_id": "doc:fifth_schedule:relief:2",
            "compare_group_id": "digital_productivity_equipment_relief",
            "cap_amount": "300000",
            "effective_from": "2026-04-01",
            "quote": "Digital Productivity Equipment Relief shall not exceed Rs. 300,000.",
            "included": True,
            "review_status": "pending",
        },
        {
            "entity_kind": "rate_band",
            "entry_id": "doc:first_schedule:band:0",
            "compare_group_id": "individual_tax_rates",
            "lower": "0",
            "upper": "1200000",
            "rate_percent": "5",
            "applies_to": "resident or non-resident individual",
            "effective_from": "2026-04-01",
            "quote": "Not exceeding Rs. 1,200,000 | 5%",
            "included": True,
            "review_status": "pending",
        },
        {
            "entity_kind": "rate_band",
            "entry_id": "doc:w006:band:0",
            "compare_group_id": "individual_rate_bands",
            "lower": "",
            "upper": "1200000",
            "rate_percent": "5",
            "applies_to": "individual",
            "effective_from": "2026-04-01",
            "quote": "5%",
            "included": True,
            "review_status": "pending",
        },
    ]
    collapsed = collapse_duplicate_extract_entities(rows)
    groups = [str(r.get("compare_group_id")) for r in collapsed]
    assert groups.count("personal_relief") == 2
    assert "qualifying_computer_equipment" not in groups
    assert "digital_productivity_equipment_relief" in groups
    assert groups.count("first_schedule_rates") == 1
    survivor = next(
        row
        for row in collapsed
        if row["compare_group_id"] == "personal_relief" and row["cap_amount"] == "2000000"
    )
    assert "fifth_schedule" in survivor["entry_id"]
    scrub_interview_fields(survivor)
    assert survivor["question_prompt"] == "What is your personal relief amount?"
    assert "April" not in survivor["question_prompt"]


def test_collapse_foreign_currency_alias_groups() -> None:
    from oe_engine_app.services.extract_dedupe import (
        canonical_compare_group_id,
        collapse_duplicate_extract_entities,
        collapse_year_relief_aliases,
    )

    assert (
        canonical_compare_group_id("foreign_currency_income")
        == "foreign_currency_income_relief"
    )
    rows = [
        {
            "entity_kind": "relief",
            "entry_id": "oee-act-24-2017:w042:relief:0",
            "compare_group_id": "foreign_currency_income",
            "cap_amount": "15000000",
            "quote": "short foreign currency reprint",
            "included": True,
            "review_status": "pending",
        },
        {
            "entity_kind": "relief",
            "entry_id": "oee-act-24-2017:fifth_schedule:relief:8",
            "compare_group_id": "foreign_currency_income_relief",
            "cap_amount": "15000000",
            "quote": "Fifth Schedule foreign currency income relief at Rs. 15,000,000.",
            "included": True,
            "review_status": "pending",
        },
    ]
    collapsed = collapse_duplicate_extract_entities(rows)
    groups = [str(r.get("compare_group_id")) for r in collapsed]
    assert groups == ["foreign_currency_income_relief"]
    assert "fifth_schedule" in collapsed[0]["entry_id"]

    listed = collapse_year_relief_aliases(
        [
            {
                "compare_group_id": "foreign_currency_income",
                "entry_id": "oee-act-24-2017:w042:relief:0",
                "quote": "short",
                "display_name": "Foreign currency income relief",
            },
            {
                "compare_group_id": "foreign_currency_income_relief",
                "entry_id": "oee-act-24-2017:fifth_schedule:relief:8",
                "quote": "longer Fifth Schedule quote",
                "display_name": "Foreign Currency Income Relief",
            },
        ]
    )
    assert len(listed) == 1
    assert listed[0]["compare_group_id"] == "foreign_currency_income_relief"
    assert "fifth_schedule" in listed[0]["entry_id"]


def test_collapse_maps_resident_expenditure_alias() -> None:
    from oe_engine_app.services.extract_dedupe import canonical_compare_group_id

    assert (
        canonical_compare_group_id("resident_individual_expenditure")
        == "expenditure_relief"
    )
    assert canonical_compare_group_id("fifth_schedule_2_f") == "expenditure_relief"

