#!/usr/bin/env python3
"""Phase 2 Step 5: run TF-IDF eval suite and append one experiment record (JSONL).

Orchestrates retrieval, intent, and joint scripts; merges metrics into a record aligned with
evaluation/experiment_run_template.json (superset fields + nested eval_outputs).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
_LM_INIT = _REPO_ROOT / "backend" / "comp-language-model" / "app" / "__init__.py"


def _read_component_version() -> str:
    if not _LM_INIT.is_file():
        return "0.0.0"
    text = _LM_INIT.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else "0.0.0"


def _benchmark_line_count(path: Path) -> int:
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def _run_eval_script(script: str, args: list[str]) -> tuple[int, str, str]:
    cmd = [sys.executable, str(_SCRIPTS / script), *args]
    proc = subprocess.run(cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def _parse_json_stdout(stdout: str) -> dict[str, object] | None:
    stdout = stdout.strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus-jsonl", type=Path, required=True)
    p.add_argument(
        "--benchmark",
        type=Path,
        required=True,
        help="Eval benchmark JSONL (retrieval + intent + joint scored here).",
    )
    p.add_argument(
        "--train-benchmark",
        type=Path,
        default=None,
        help="Optional train split: intent centroid fit only (Step 10). --benchmark is eval only.",
    )
    p.add_argument("--k", type=int, default=8)
    p.add_argument(
        "--retrieval-backend",
        choices=("tfidf", "dense"),
        default="tfidf",
        help="Retrieval baseline for bundle retrieval eval + joint (Step 11: dense = embeddings).",
    )
    p.add_argument(
        "--dense-model",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-Transformers model when --retrieval-backend dense",
    )
    p.add_argument(
        "--task-registry",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "phase2_task_registry.json",
    )
    p.add_argument("--model-version", type=str, default="tfidf_baseline", help="Logical model / candidate id")
    p.add_argument("--intent-mode", choices=("loocv", "holdout"), default="loocv")
    p.add_argument("--intent-test-fraction", type=float, default=0.25)
    p.add_argument("--intent-seed", type=int, default=42)
    p.add_argument("--joint-mode", choices=("loocv", "holdout"), default="loocv")
    p.add_argument("--joint-test-fraction", type=float, default=0.25)
    p.add_argument("--joint-seed", type=int, default=42)
    p.add_argument(
        "--append",
        type=Path,
        default=_REPO_ROOT / "evaluation" / "phase2_runs.jsonl",
        help="Append one JSON object per run (JSONL)",
    )
    p.add_argument("--notes", type=str, default="", help="Free-text note stored on the record")
    p.add_argument("--dry-run", action="store_true", help="Print record to stdout only; do not append")
    p.add_argument("--skip-retrieval", action="store_true")
    p.add_argument("--skip-intent", action="store_true")
    p.add_argument("--skip-joint", action="store_true")
    args = p.parse_args()

    if not args.corpus_jsonl.is_file():
        print(f"corpus not found: {args.corpus_jsonl}", file=sys.stderr)
        return 2
    if not args.benchmark.is_file():
        print(f"benchmark not found: {args.benchmark}", file=sys.stderr)
        return 2
    if args.train_benchmark is not None and not args.train_benchmark.is_file():
        print(f"train-benchmark not found: {args.train_benchmark}", file=sys.stderr)
        return 2

    started = datetime.now(UTC)
    stamp = started.strftime("%Y%m%d_%H%M%S")
    run_id = f"run_{stamp}_{uuid.uuid4().hex[:8]}"

    eval_outputs: dict[str, object] = {}
    errors: dict[str, str] = {}

    if not args.skip_retrieval:
        if args.retrieval_backend == "tfidf":
            retr_script = "phase2_eval_retrieval_tfidf.py"
            retr_args: list[str] = [
                "--corpus-jsonl",
                str(args.corpus_jsonl),
                "--benchmark",
                str(args.benchmark),
                "--k",
                str(args.k),
                "--task-registry",
                str(args.task_registry),
            ]
        else:
            retr_script = "phase2_eval_retrieval_dense.py"
            retr_args = [
                "--corpus-jsonl",
                str(args.corpus_jsonl),
                "--benchmark",
                str(args.benchmark),
                "--k",
                str(args.k),
                "--model-name",
                args.dense_model,
                "--task-registry",
                str(args.task_registry),
            ]
        code, out, err = _run_eval_script(retr_script, retr_args)
        parsed = _parse_json_stdout(out)
        if code == 0 and parsed is not None:
            eval_outputs["retrieval"] = parsed
        else:
            errors["retrieval"] = err.strip() or out.strip() or f"exit {code}"

    if not args.skip_intent:
        intent_args = [
            "--benchmark",
            str(args.benchmark),
            "--task-registry",
            str(args.task_registry),
            "--mode",
            args.intent_mode,
        ]
        if args.train_benchmark is not None:
            intent_args += ["--train-benchmark", str(args.train_benchmark)]
        if args.train_benchmark is None and args.intent_mode == "holdout":
            intent_args += [
                "--test-fraction",
                str(args.intent_test_fraction),
                "--seed",
                str(args.intent_seed),
            ]
        code, out, err = _run_eval_script("phase2_eval_intent_tfidf.py", intent_args)
        parsed = _parse_json_stdout(out)
        if code == 0 and parsed is not None:
            eval_outputs["intent"] = parsed
        else:
            errors["intent"] = err.strip() or out.strip() or f"exit {code}"

    if not args.skip_joint:
        joint_args = [
            "--corpus-jsonl",
            str(args.corpus_jsonl),
            "--benchmark",
            str(args.benchmark),
            "--k",
            str(args.k),
            "--task-registry",
            str(args.task_registry),
            "--mode",
            args.joint_mode,
        ]
        if args.train_benchmark is not None:
            joint_args += ["--intent-train-benchmark", str(args.train_benchmark)]
        if args.train_benchmark is None and args.joint_mode == "holdout":
            joint_args += [
                "--test-fraction",
                str(args.joint_test_fraction),
                "--seed",
                str(args.joint_seed),
            ]
        joint_args += ["--retrieval-backend", args.retrieval_backend]
        if args.retrieval_backend == "dense":
            joint_args += ["--dense-model", args.dense_model]
        code, out, err = _run_eval_script("phase2_eval_joint_tfidf.py", joint_args)
        parsed = _parse_json_stdout(out)
        if code == 0 and parsed is not None:
            eval_outputs["joint"] = parsed
        else:
            errors["joint"] = err.strip() or out.strip() or f"exit {code}"

    finished = datetime.now(UTC)
    duration = (finished - started).total_seconds()

    retr = eval_outputs.get("retrieval") if isinstance(eval_outputs.get("retrieval"), dict) else {}
    intent = eval_outputs.get("intent") if isinstance(eval_outputs.get("intent"), dict) else {}
    joint = eval_outputs.get("joint") if isinstance(eval_outputs.get("joint"), dict) else {}

    metrics: dict[str, object] = {
        "intent_f1": intent.get("macro_f1"),
        "entity_f1": None,
        "grounding_adherence": retr.get("value"),
        "latency_p95_ms": None,
        "phase2_retrieval_recall_at_k_any_gold": retr.get("value"),
        "phase2_retrieval_mrr_at_k": retr.get("mrr"),
        "phase2_retrieval_n_evaluated": retr.get("n_evaluated"),
        "phase2_intent_accuracy": intent.get("value"),
        "phase2_intent_macro_f1": intent.get("macro_f1"),
        "phase2_joint_success_rate": joint.get("joint_success_rate"),
        "phase2_joint_n": joint.get("n_joint"),
    }

    record: dict[str, object] = {
        "run_id": run_id,
        "component": "language-model",
        "component_version": _read_component_version(),
        "model_version": args.model_version,
        "corpus_version": "corpus_v1",
        "rule_engine_version": "n/a",
        "dataset": {
            "name": args.benchmark.stem,
            "benchmark_path": str(args.benchmark.as_posix()),
            "train_benchmark_path": str(args.train_benchmark.as_posix()) if args.train_benchmark else None,
            "corpus_path": str(args.corpus_jsonl.as_posix()),
            "split": "held_out_train_eval" if args.train_benchmark else "phase2_bundle",
            "sample_count": _benchmark_line_count(args.benchmark),
            "train_sample_count": _benchmark_line_count(args.train_benchmark) if args.train_benchmark else 0,
            "retrieval_top_k": args.k,
            "retrieval_backend": args.retrieval_backend,
            "dense_model": args.dense_model if args.retrieval_backend == "dense" else None,
        },
        "metrics": metrics,
        "runtime": {
            "started_at_utc": started.isoformat().replace("+00:00", "Z"),
            "finished_at_utc": finished.isoformat().replace("+00:00", "Z"),
            "duration_seconds": round(duration, 3),
        },
        "cost": {"currency": "USD", "estimated_total": 0.0},
        "notes": args.notes or "Phase 2 Step 5 bundle (TF-IDF baselines).",
        "phase2_eval_outputs": eval_outputs,
    }
    if errors:
        record["phase2_errors"] = errors

    line = json.dumps(record, ensure_ascii=False) + "\n"
    if args.dry_run:
        sys.stdout.write(line)
        return 0

    args.append.parent.mkdir(parents=True, exist_ok=True)
    with args.append.open("a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
