"""Step 7: regression smoke uses committed fixtures."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent


def test_phase2_regression_smoke_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, str(_ROOT / "phase2_regression_smoke.py")],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_phase2_smoke_fixtures_exist() -> None:
    corp = _REPO / "evaluation" / "fixtures" / "phase2_smoke" / "corpus_v1.jsonl"
    bench = _REPO / "evaluation" / "fixtures" / "phase2_smoke" / "benchmark.jsonl"
    assert corp.is_file() and bench.is_file()
