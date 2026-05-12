"""Tests for phase2_merge_benchmark_splits.py (Step 13)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent


def test_merge_two_files_order_preserved(tmp_path: Path) -> None:
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(
        json.dumps({"example_id": "1", "utterance": "x"}) + "\n", encoding="utf-8"
    )
    b.write_text(
        json.dumps({"example_id": "2", "utterance": "y"}) + "\n", encoding="utf-8"
    )
    out = tmp_path / "merged.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "phase2_merge_benchmark_splits.py"),
            "--inputs",
            str(a),
            str(b),
            "-o",
            str(out),
        ],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0])["example_id"] == "1"
    assert json.loads(lines[1])["example_id"] == "2"


def test_merge_dedupe_keeps_first(tmp_path: Path) -> None:
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text(
        json.dumps({"example_id": "1", "utterance": "first"}) + "\n", encoding="utf-8"
    )
    b.write_text(
        json.dumps({"example_id": "1", "utterance": "second"}) + "\n", encoding="utf-8"
    )
    out = tmp_path / "merged.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "phase2_merge_benchmark_splits.py"),
            "--inputs",
            str(a),
            str(b),
            "-o",
            str(out),
            "--dedupe-example-id",
        ],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["utterance"] == "first"
