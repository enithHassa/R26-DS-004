"""Unit tests for PDF outline breadcrumb helpers (no PDF file)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ird_pdf_outline", _ROOT / "ird_pdf_outline.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_outline_breadcrumb_trail() -> None:
    flat = [(1, "Part I"), (5, "Chapter 2"), (10, "Section block")]
    assert _mod.outline_breadcrumb_for_page(flat, 1) == ["Part I"]
    assert _mod.outline_breadcrumb_for_page(flat, 7) == ["Part I", "Chapter 2"]
    assert _mod.outline_breadcrumb_for_page(flat, 99) == ["Part I", "Chapter 2", "Section block"]


def test_outline_breadcrumb_map() -> None:
    flat = [(1, "A"), (2, "B")]
    m = _mod.outline_breadcrumb_map(flat, [1, 2])
    assert m[1] == ["A"]
    assert m[2] == ["A", "B"]
