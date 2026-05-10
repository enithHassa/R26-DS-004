#!/usr/bin/env python3
"""Phase 2 Step 8: export a single Markdown handoff report (baseline, tasks, leaderboard, commands)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_SCRIPTS = _REPO / "scripts"
_DEFAULT_OUT = _REPO / "evaluation" / "phase2_handoff" / "REPORT.md"
_BASELINE = _REPO / "evaluation" / "frozen" / "phase2_M5_baseline.json"
_REGISTRY = _REPO / "evaluation" / "phase2_task_registry.json"
_DEFAULT_RUNS = _REPO / "evaluation" / "phase2_runs.jsonl"


def _leaderboard_markdown(runs_path: Path) -> str:
    if not runs_path.is_file():
        return "_No experiment log at this path yet. Append runs with `scripts/phase2_experiment_run.py` (Step 5)._\n\n"
    proc = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS / "phase2_leaderboard.py"),
            "--input",
            str(runs_path),
            "--format",
            "markdown",
            "--sort",
            "joint",
        ],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return f"```\n{proc.stderr}\n```\n\n"
    return proc.stdout + "\n\n"


def build_report(*, runs_path: Path) -> str:
    parts: list[str] = []
    parts.append("# Phase 2 handoff report\n\n")
    parts.append("Single-file summary for supervisors, examiners, or repo handoff. Regenerate after new runs or gate changes.\n\n")
    parts.append(f"**Generated (UTC):** {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}\n\n")

    parts.append("## M5 frozen baseline\n\n")
    if _BASELINE.is_file():
        baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
        parts.append("```json\n")
        parts.append(json.dumps(baseline, indent=2))
        parts.append("\n```\n\n")
    else:
        parts.append("_Missing `evaluation/frozen/phase2_M5_baseline.json`._\n\n")

    parts.append("## Task registry\n\n")
    if _REGISTRY.is_file():
        reg = json.loads(_REGISTRY.read_text(encoding="utf-8"))
        ver = reg.get("registry_version", "?")
        tasks = reg.get("tasks") or []
        parts.append(f"- **registry_version:** {ver}\n")
        parts.append(f"- **task count:** {len(tasks)}\n")
        parts.append("- **path:** `evaluation/phase2_task_registry.json`\n\n")
        parts.append("| task_id | name |\n|---|---|\n")
        for t in tasks:
            tid = t.get("task_id", "")
            name = t.get("name", "")
            parts.append(f"| {tid} | {name} |\n")
        parts.append("\n")
    else:
        parts.append("_Registry not found._\n\n")

    parts.append("## Leaderboard (`phase2_runs.jsonl`)\n\n")
    parts.append(_leaderboard_markdown(runs_path))

    parts.append("## Frozen NLU schemas\n\n")
    parts.append("- `evaluation/frozen/nlu_parse_request.schema.json`\n")
    parts.append("- `evaluation/frozen/nlu_parse_response.schema.json`\n\n")

    parts.append("## Copy-paste commands\n\n")
    parts.append("```text\n")
    parts.append("# Regression smoke (Step 7)\n")
    parts.append("python scripts/phase2_regression_smoke.py\n\n")
    parts.append("# Experiment bundle dry-run (replace paths)\n")
    parts.append("python scripts/phase2_experiment_run.py --corpus-jsonl data/processed/ird/corpus_v1.jsonl ")
    parts.append("--benchmark evaluation/benchmark_seed_template.jsonl --dry-run\n\n")
    parts.append("# Leaderboard\n")
    parts.append("python scripts/phase2_leaderboard.py --input evaluation/phase2_runs.jsonl\n")
    parts.append("```\n\n")

    parts.append("---\n\n*Produced by `scripts/phase2_export_handoff.py` (Phase 2 Step 8).*\n")
    return "".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help="Output Markdown path (default: evaluation/phase2_handoff/REPORT.md)",
    )
    p.add_argument(
        "--runs",
        type=Path,
        default=_DEFAULT_RUNS,
        help="phase2_runs.jsonl for leaderboard section",
    )
    p.add_argument(
        "--stdout",
        action="store_true",
        help="Print report to stdout only (do not write file)",
    )
    args = p.parse_args()

    text = build_report(runs_path=args.runs)
    if args.stdout:
        sys.stdout.write(text)
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
