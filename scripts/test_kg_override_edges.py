"""Tests for Phase 3 Step 9 Lex override path validation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("kg_override_edges_lib", _ROOT / "kg_override_edges_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _override_row() -> dict:
    return {
        "rel_type": "OVERRIDES",
        "from_label": "Section",
        "from_key": "section_uid",
        "from_id": "a::sec::s1",
        "to_label": "Section",
        "to_key": "section_uid",
        "to_id": "a::sec::s2",
        "review_status": "manual",
        "source_note": "curator confirmed",
    }


def test_non_override_row_skips_extra_checks() -> None:
    row = {
        "rel_type": "MENTIONS",
        "from_label": "TextChunk",
        "from_key": "chunk_id",
        "from_id": "c1",
        "to_label": "Concept",
        "to_key": "concept_id",
        "to_id": "x",
    }
    assert not _mod.validate_lex_override_row(row, strict=True, line_no=1)


def test_strict_requires_provenance() -> None:
    row = _override_row()
    assert not _mod.validate_lex_override_row(row, strict=True, line_no=1)

    row2 = dict(row)
    del row2["source_note"]
    errs = _mod.validate_lex_override_row(row2, strict=True, line_no=3)
    assert errs and any("source_note" in e for e in errs)

    row3 = dict(row)
    del row3["review_status"]
    errs3 = _mod.validate_lex_override_row(row3, strict=True, line_no=4)
    assert errs3 and any("review_status" in e for e in errs3)


def test_non_strict_allows_missing_provenance() -> None:
    row = {**_override_row(), "source_note": "", "review_status": ""}
    assert not _mod.validate_lex_override_row(row, strict=False, line_no=1)
