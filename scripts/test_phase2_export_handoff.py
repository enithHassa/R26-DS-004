"""Step 8: handoff report generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent

_spec = importlib.util.spec_from_file_location("phase2_export_handoff", _ROOT / "phase2_export_handoff.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_handoff_report_contains_baseline_and_tasks(tmp_path: Path) -> None:
    text = _mod.build_report(runs_path=tmp_path / "missing.jsonl")
    assert "M5_phase2" in text or "M5 frozen baseline" in text
    assert "retrieval_law_grounding" in text
    assert "phase2_export_handoff" in text


def test_handoff_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "R.md"
    text = _mod.build_report(runs_path=_REPO / "evaluation" / "phase2_runs.jsonl")
    out.write_text(text, encoding="utf-8")
    assert out.is_file()
    assert len(out.read_text(encoding="utf-8")) > 500
