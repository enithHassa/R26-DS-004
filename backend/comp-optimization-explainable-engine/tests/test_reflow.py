"""Narrow-column PDF prose is reflowed before the extract model sees it."""

from __future__ import annotations

from oe_engine_app.services.quote_gate import quote_in_text
from oe_engine_app.services.windows import FocusWindow, reflow_column_text

COLUMN = (
    "(f) expenditure incurred on or after April\n"
    "1, 2021, by any person-\n"
    "(i) in the production of a film at a\n"
    "cost of (including promotional\n"
    "expenditure of such film) not\n"
    "less than five million rupees;\n"
    "(ii) in the construction and\n"
    "equipping of a new cinema at a\n"
    "cost of not exceeding twenty-\n"
    "five million rupees;\n"
)


def test_wrapped_words_are_rejoined_with_a_space() -> None:
    out = reflow_column_text(COLUMN)
    assert "including promotional expenditure of such film" in out
    assert "rupees; (ii)" not in out


def test_wrapped_hyphen_is_closed_up() -> None:
    assert "twenty-five million rupees" in reflow_column_text(COLUMN)


def test_list_markers_keep_their_own_line() -> None:
    lines = reflow_column_text(COLUMN).splitlines()
    assert any(line.startswith("(i) in the production") for line in lines)
    assert any(line.startswith("(ii) in the construction") for line in lines)


def test_paragraph_breaks_survive() -> None:
    out = reflow_column_text("first para line one\nline two\n\nsecond para here")
    assert out == "first para line one line two\n\nsecond para here"


def test_a_quote_of_reflowed_text_still_gates_against_the_raw_stream() -> None:
    """The model quotes the reflowed window; the gate scores it on raw pypdf output."""
    window = FocusWindow(
        window_id="w009",
        heading="Fifth Schedule",
        start=0,
        end=len(COLUMN),
        stream_slice=COLUMN,
        tables_slice="",
        page_start=1,
        page_end=1,
    )
    quoted = (
        "in the construction and equipping of a new cinema at a cost of not "
        "exceeding twenty-five million rupees;"
    )
    assert quoted in window.text
    assert quote_in_text(quoted, COLUMN) is True
