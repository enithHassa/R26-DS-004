"""Deterministic quote substring gate: verbatim in, reassembled out."""

from __future__ import annotations

from oe_engine_app.services.quote_gate import quote_gate, quote_in_text, reassembled_out

WINDOW = (
    "Qualifying payment to an approved charity. "
    "Personal relief of rupees one million two hundred thousand. "
    "Expenditure on solar panels may be deducted."
)


def test_verbatim_quote_is_in() -> None:
    quote = "Personal relief of rupees one million two hundred thousand."
    gated = quote_gate(quote, WINDOW, WINDOW, "")
    assert gated["quote_ok_window"] is True
    assert gated["quote_ok_full_doc"] is True
    assert gated["quote_source"] == "text_stream"
    assert gated["reassembled_out"] is False
    assert quote_in_text(quote, WINDOW) is True


def test_whitespace_and_dash_fold_still_in() -> None:
    quote = "Personal  relief of rupees one million\ntwo hundred thousand"
    gated = quote_gate(quote, WINDOW, WINDOW, "")
    assert gated["quote_ok_window"] is True


def test_paraphrase_is_out() -> None:
    quote = "Individuals receive a personal allowance of 1.2 million rupees."
    gated = quote_gate(quote, WINDOW, WINDOW, "")
    assert gated["quote_ok_window"] is False
    assert gated["quote_ok_full_doc"] is False
    assert gated["quote_source"] == "none"


def test_reassembled_noncontiguous_is_out() -> None:
    quote = "Qualifying payment on solar panels may be deducted"
    gated = quote_gate(quote, WINDOW, WINDOW, "")
    assert gated["quote_ok_window"] is False
    assert gated["reassembled_out"] is True
    assert reassembled_out(quote, WINDOW) is True


def test_wrapped_hyphen_in_pdf_still_matches_act_spelling() -> None:
    """pypdf reads "twenty- five" where the Act prints "twenty-five"."""
    stream = (
        "in the construction and equipping of a new cinema at a cost of not "
        "exceeding twenty- five million rupees;"
    )
    quote = (
        "in the construction and equipping of a new cinema at a cost of not "
        "exceeding twenty-five million rupees;"
    )
    gated = quote_gate(quote, stream, stream, "")
    assert gated["quote_ok_window"] is True
    assert gated["quote_ok_full_doc"] is True
    assert gated["quote_source"] == "text_stream"
    assert gated["reassembled_out"] is False


def test_trim_quote_drops_stitched_fifth_schedule_list() -> None:
    from oe_engine_app.services.quote_gate import trim_quote_to_verbatim

    window = (
        "(f) in the case of a resident individual, following expenditure up to "
        "a total sum of Rs. 1,200,000, incurred for a year of assessment on or "
        "after January 1, 2020: -\n(i) health expenditure including contributions "
        "to medical insurance;"
    )
    stitched = (
        "(f) in the case of a resident individual, following expenditure up to "
        "a total sum of Rs. 1,200,000, incurred for a year of assessment on or "
        "after January 1, 2020: - (i) health expenditure including contributions "
        "to medical insurance; (ii) vocational education or other educational "
        "expenditure incurred locally"
    )
    trimmed = trim_quote_to_verbatim(stitched, window, window, "")
    assert trimmed.startswith("(f) in the case of a resident individual")
    assert "(ii)" not in trimmed
    assert quote_gate(trimmed, window, window, "")["quote_ok_window"] is True


def test_hyphen_fold_does_not_admit_a_paraphrase() -> None:
    stream = "a cost of not exceeding twenty- five million rupees"
    gated = quote_gate("a cost of about twenty-five million rupees", stream, stream, "")
    assert gated["quote_ok_full_doc"] is False


def test_table_render_source() -> None:
    tables = "Taxable Income | Tax Payable\nNot Exceeding Rs. 600,000 | 4%"
    quote = "Not Exceeding Rs. 600,000 | 4%"
    gated = quote_gate(quote, "unrelated prose", "unrelated prose", tables)
    assert gated["quote_ok_window"] is False
    assert gated["quote_ok_full_doc"] is True
    assert gated["quote_source"] == "table_render"


def test_tab_separated_table_matches_pipe_quote() -> None:
    tables = (
        "Taxable income\tTax Payable\n"
        "Not exceeding Rs. 1,000,000\t6% of the amount in excess of Rs.0"
    )
    quote = "Not exceeding Rs. 1,000,000 | 6% of the amount in excess of Rs.0"
    window = (
        "### Tables on these pages, reconstructed from the same PDF\n"
        "Each line is one table row; cells are separated by ' | '.\n\n"
        "Not exceeding Rs. 1,000,000 | 6% of the amount in excess of Rs.0"
    )
    gated = quote_gate(quote, window, "wrapped Not exceeding 6% of the", tables)
    assert gated["quote_ok_window"] is True
    assert gated["quote_ok_full_doc"] is True
    assert gated["quote_source"] == "table_render"
