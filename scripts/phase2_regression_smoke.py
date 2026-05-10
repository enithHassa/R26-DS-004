#!/usr/bin/env python3
"""Phase 2 Step 7: regression smoke — run experiment bundle on committed fixtures (CI / pre-push).

Exits 0 only if phase2_experiment_run --dry-run succeeds with no phase2_errors and required keys present.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_CORPUS = _REPO / "evaluation" / "fixtures" / "phase2_smoke" / "corpus_v1.jsonl"
_BENCH = _REPO / "evaluation" / "fixtures" / "phase2_smoke" / "benchmark.jsonl"
_BUNDLE = _REPO / "scripts" / "phase2_experiment_run.py"


def main() -> int:
    if not _CORPUS.is_file() or not _BENCH.is_file():
        print(f"Missing fixtures: {_CORPUS} or {_BENCH}", file=sys.stderr)
        return 2

    val = subprocess.run(
        [
            sys.executable,
            str(_REPO / "scripts" / "validate_benchmark_corpus.py"),
            "--benchmark",
            str(_BENCH),
            "--corpus-jsonl",
            str(_CORPUS),
        ],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
    )
    if val.returncode != 0:
        print(val.stdout, file=sys.stderr)
        print(val.stderr, file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(_BUNDLE),
        "--corpus-jsonl",
        str(_CORPUS),
        "--benchmark",
        str(_BENCH),
        "--k",
        "4",
        "--model-version",
        "regression_smoke_fixture",
        "--dry-run",
        "--notes",
        "phase2_regression_smoke",
    ]
    proc = subprocess.run(cmd, cwd=str(_REPO), capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout, file=sys.stderr)
        print(proc.stderr, file=sys.stderr)
        return 1

    raw = proc.stdout.strip()
    if not raw:
        print("empty stdout from phase2_experiment_run", file=sys.stderr)
        return 1

    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON: {exc}\n{raw[:500]}", file=sys.stderr)
        return 1

    if record.get("phase2_errors"):
        print(f"phase2_errors: {record['phase2_errors']}", file=sys.stderr)
        return 1

    outs = record.get("phase2_eval_outputs")
    if not isinstance(outs, dict):
        print("missing phase2_eval_outputs", file=sys.stderr)
        return 1
    for key in ("retrieval", "intent", "joint"):
        if key not in outs:
            print(f"missing phase2_eval_outputs.{key}", file=sys.stderr)
            return 1

    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        print("missing metrics", file=sys.stderr)
        return 1
    for mk in (
        "phase2_retrieval_recall_at_k_any_gold",
        "phase2_retrieval_mrr_at_k",
        "phase2_intent_accuracy",
        "phase2_joint_success_rate",
    ):
        if mk not in metrics:
            print(f"missing metrics.{mk}", file=sys.stderr)
            return 1

    print("phase2_regression_smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
