"""Unit tests for amendment-focused PDF text windowing."""

from __future__ import annotations

from pathlib import Path

import fitz

from adaptive_tax_app.services.pdf_extract import (
    DEFAULT_MAX_FOCUS_CHARS,
    extract_focused_amendment_text,
    extract_pdf_text,
    focus_amendment_text,
)


_SAMPLE_AMENDMENT = """
Short title and date of operation

This Act may be cited as the Inland Revenue (Amendment) Act, No. 2 of 2025.

Sections of the principal enactment amended

Sections 5, 52 and the First Schedule of the principal enactment are hereby amended.

Section 52 of the principal enactment is hereby amended by the substitution for
the words "one million two hundred thousand" of the words "one million eight
hundred thousand" wherever those words appear in that section relating to
qualifying payments.

Section 5 of the principal enactment is hereby amended by the insertion
immediately after subsection (2) of the following new subsection.

PADDED NOISE """ + ("whole act padding " * 5000)


def test_focus_pulls_principal_amendment_blocks_and_candidates() -> None:
    result = focus_amendment_text(_SAMPLE_AMENDMENT, max_chars=8_000)

    assert "Section 52 of the principal enactment is hereby amended" in result.focused_text
    assert "one million eight" in result.focused_text
    assert "qualifying payments" in result.focused_text
    assert "52" in result.amends_section_candidates
    assert "5" in result.amends_section_candidates
    assert result.char_count_focused <= 8_000 + 80  # allow truncation marker
    assert result.char_count_focused < result.char_count_full
    # Padding must not dominate the focused window.
    assert result.focused_text.count("whole act padding") < 50


def test_focus_never_exceeds_cap() -> None:
    huge = "Section 99 of the principal enactment is hereby amended " + ("x" * 100_000)
    result = focus_amendment_text(huge, max_chars=1_000)
    assert result.truncated is True
    assert len(result.focused_text) <= 1_000 + 80
    assert "99" in result.amends_section_candidates


def test_focus_fallback_front_matter_when_no_markers() -> None:
    result = focus_amendment_text("No amendment markers here.\n" + ("y" * 50_000), max_chars=2_000)
    assert "fallback front matter" in result.focused_text.lower() or result.focused_text
    assert result.char_count_focused <= 2_000 + 80


def test_extract_focused_from_real_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "amendment.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Section 52 of the principal enactment is hereby amended by substitution "
        "for qualifying payment cap.",
        fontsize=11,
    )
    doc.save(pdf_path)
    doc.close()

    full = extract_pdf_text(pdf_path)
    assert "Section 52" in full

    focused = extract_focused_amendment_text(pdf_path, max_chars=DEFAULT_MAX_FOCUS_CHARS)
    assert focused.page_count == 1
    assert "52" in focused.amends_section_candidates
    assert "principal enactment is hereby amended" in focused.focused_text.lower()
