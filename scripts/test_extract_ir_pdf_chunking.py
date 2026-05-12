"""Unit tests for IR corpus chunking helpers (no PDF I/O)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ird_corpus_lib", _ROOT / "ird_corpus_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_make_chunk_id_format() -> None:
    assert _mod.make_chunk_id_text("ird-ira-2017-base", 12, 3) == "ird-ira-2017-base::p0012::c0003"
    assert _mod.make_chunk_id_table("ird-x", 2, 1) == "ird-x::p0002::t0001"


def test_chunk_page_text_splits_and_overlaps() -> None:
    text = ("word " * 200).strip()
    chunks = _mod.chunk_page_text(text, max_chars=200, overlap=40)
    assert len(chunks) >= 2
    for start, end, piece in chunks:
        assert piece == text[start:end].strip()
        assert len(piece) <= 200


def test_chunk_page_text_empty() -> None:
    assert _mod.chunk_page_text("   \n\t  ", max_chars=200, overlap=40) == []


def test_extract_section_refs() -> None:
    refs = _mod.extract_section_refs("Under Section 45 and Part IV of the Act.")
    assert refs is not None
    assert "Section 45" in refs
    assert "Part IV" in refs
