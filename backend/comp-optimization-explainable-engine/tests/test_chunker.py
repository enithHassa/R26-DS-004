"""Chunker maps text vs table channels."""

from __future__ import annotations

from oe_engine_app.services.chunker import build_chunks


def test_section_aware_text_and_table_channels() -> None:
    page = (
        "5. Employment income.\n"
        "(1) Employment income means the gains.\n"
        "Expenditure on solar panels may be deducted.\n"
    )
    chunks = build_chunks(
        pages=[(1, page)],
        source_doc_id="oee-test",
        title="Test",
        tier="act",
        tables_by_page={1: ["Rate\tPercent\nFirst\t6%"]},
        table_method="pdfplumber",
        max_chars=400,
        overlap=40,
    )
    channels = {c["channel"] for c in chunks}
    assert "text_stream" in channels
    assert "table_render" in channels
    joined = " ".join(c["text"] for c in chunks)
    assert "solar panels" in joined.lower()
