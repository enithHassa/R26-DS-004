"""Tests for Phase 3 Step 10 consolidated view anchors."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

_spec = importlib.util.spec_from_file_location("kg_consolidated_view_lib", _ROOT / "kg_consolidated_view_lib.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_make_anchor_id() -> None:
    aid = _mod.make_anchor_id(
        "ira_consolidated_202503",
        "2025-03-31",
        section_uid="ira2017::sec::section_45",
    )
    assert aid.startswith("ira_consolidated_202503::cv::")
    assert "section_45" in aid


def test_validate_anchor_row_good() -> None:
    row = {
        "anchor_id": "a::cv::2025_03_31::x",
        "source_doc_id": "a",
        "consolidated_as_of": "2025-03-31",
        "section_label_snapshot": "Section 1",
        "review_status": "manual",
    }
    assert not _mod.validate_anchor_row(row, line_no=1)


def test_validate_rejects_unknown_key() -> None:
    row = {
        "anchor_id": "a::cv::2025_03_31::x",
        "source_doc_id": "a",
        "consolidated_as_of": "2025-03-31",
        "extra": "nope",
    }
    errs = _mod.validate_anchor_row(row)
    assert errs and any("unknown" in e for e in errs)
