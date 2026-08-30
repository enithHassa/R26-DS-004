"""Re-gate recovers gate rejections only; review decisions survive."""

from __future__ import annotations

from oe_engine_app.services.regate import regate_entities
from oe_engine_app.services.windows import DocText, FocusWindow

WRAPPED = (
    "in the upgrading of a cinema at a cost of not exceeding ten million rupees: "
    "provided that the deduction under this subparagraph shall be restricted to "
    "one third of the taxable income."
)
ACT_SPELLING = "in the construction and equipping of a new cinema at a cost of not exceeding twenty-five million rupees;"
STREAM = (
    "expenditure incurred on or after April 1, 2021, by any person- "
    "in the construction and equipping of a new cinema at a cost of not "
    "exceeding twenty- five million rupees; " + WRAPPED
)


def _doc() -> DocText:
    return DocText(
        source_doc_id="oee-act-test",
        title="test",
        tier="act",
        stream=STREAM,
        tables_blob="",
    )


def _window() -> FocusWindow:
    return FocusWindow(
        window_id="w009",
        heading="Fifth Schedule",
        start=0,
        end=len(STREAM),
        stream_slice=STREAM,
        tables_slice="",
        page_start=1,
        page_end=1,
    )


def test_wrapped_hyphen_rejection_is_recovered() -> None:
    entity = {
        "entry_id": "oee-act-test:w009:relief:2",
        "compare_group_id": "film_production_construction",
        "quote": ACT_SPELLING,
        "quote_ok_window": False,
        "quote_ok_full_doc": False,
        "quote_source": "none",
        "included": False,
    }
    out, changes = regate_entities([entity], _doc(), [_window()])
    assert len(changes) == 1
    assert out[0]["included"] is True
    assert out[0]["quote_ok_full_doc"] is True
    assert out[0]["quote_source"] == "text_stream"


def test_reviewer_exclusion_of_a_passing_quote_is_left_alone() -> None:
    entity = {
        "entry_id": "oee-act-test:w009:relief:3",
        "compare_group_id": "capital_allowances",
        "quote": WRAPPED,
        "quote_ok_window": True,
        "quote_ok_full_doc": True,
        "quote_source": "text_stream",
        "included": False,
    }
    out, changes = regate_entities([entity], _doc(), [_window()])
    assert changes == []
    assert out[0]["included"] is False


def test_regate_never_revokes_an_included_row() -> None:
    entity = {
        "entry_id": "oee-act-test:w404:relief:0",
        "compare_group_id": "personal_relief",
        "quote": "a quote that is nowhere in this document at all",
        "quote_ok_window": False,
        "quote_ok_full_doc": False,
        "quote_source": "none",
        "included": True,
    }
    out, _changes = regate_entities([entity], _doc(), [_window()])
    assert out[0]["included"] is True
