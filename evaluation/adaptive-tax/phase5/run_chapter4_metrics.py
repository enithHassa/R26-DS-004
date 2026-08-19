#!/usr/bin/env python3
"""Run all Adaptive Tax Chapter 4 / Phase 5.9 metrics and write a run JSON.

Offline-friendly. Does not require Neo4j or the HTTP API.

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  $env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
  $env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/phase5/run_chapter4_metrics.py
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/phase5/run_chapter4_metrics.py --write-metrics-md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_EVAL = _HERE.parent
_REPO = _HERE.parents[2]
_COMP = _REPO / "backend" / "comp-adaptive-tax"
_RUNS = _EVAL / "runs"


def _load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_pytest_examples() -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{_COMP}{os.pathsep}{_REPO}"
    env.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(_COMP / "tests" / "test_rule_engine_examples.py"),
            "-q",
            "--tb=line",
        ],
        cwd=str(_REPO),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    passed = proc.returncode == 0
    # Count named ex*.json files (variants expand inside tests).
    n_files = len(list((_REPO / "models" / "adaptive-tax" / "examples").glob("ex*.json")))
    return {
        "metric": "calculation_accuracy",
        "ok": passed,
        "pytest_returncode": proc.returncode,
        "n_example_files": n_files,
        "summary_line": out.strip().splitlines()[-1] if out.strip() else "",
        "target": "all covered-area goldens pass",
    }


def run_all() -> dict[str, Any]:
    os.environ.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    os.environ.setdefault("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")

    cov = _load(_EVAL / "coverage" / "score_coverage.py")
    prov = _load(_EVAL / "provenance" / "score_provenance.py")
    adapt = _load(_EVAL / "amendment_adaptivity" / "score_adaptivity.py")
    extract = _load(_EVAL / "extraction" / "score_extraction.py")
    harvest = _load(_EVAL / "extraction" / "score_harvest_sections.py")
    cite = _load(_EVAL / "citation_faithfulness" / "score_citations.py")
    ground = _load(_EVAL / "explanation_grounding" / "score_grounding.py")

    checklist = json.loads(
        (
            _REPO / "models" / "adaptive-tax" / "harvest" / "coverage_checklist_v1.json"
        ).read_text(encoding="utf-8")
    )
    coverage = cov.score_coverage(checklist)

    provenance = prov.score_examples()

    # Adaptivity: reuse offline entrypoint
    adaptivity = adapt._run_offline()  # noqa: SLF001

    gold = json.loads(
        (_EVAL / "extraction" / "labeled_sample_20fields.json").read_text(encoding="utf-8")
    )
    pred = json.loads(
        (
            _REPO / "models" / "adaptive-tax" / "fixtures" / "section52_extract_sample.json"
        ).read_text(encoding="utf-8")
    )
    extraction_labeled = extract.score(gold, pred.get("rules") or [])
    extraction_labeled["ok"] = (
        extraction_labeled["correct"] == extraction_labeled["total"]
        and extraction_labeled["total"] > 0
    )

    extraction_harvest = harvest.score_all()

    cite_cases = []
    for path in [
        _REPO / "models" / "adaptive-tax" / "fixtures" / "explain_ex04_sample.json",
    ]:
        for case_id, doc in cite._load_cases(path):  # noqa: SLF001
            cite_cases.append(cite.score_one(doc, case_id=case_id))
    citation = {
        "metric": "citation_faithfulness",
        "passed": sum(1 for c in cite_cases if c["ok"]),
        "total": len(cite_cases),
        "rate": round(
            sum(1 for c in cite_cases if c["ok"]) / len(cite_cases), 4
        )
        if cite_cases
        else 0.0,
        "ok": bool(cite_cases) and all(c["ok"] for c in cite_cases),
        "cases": cite_cases,
        "target": 1.0,
    }

    ground_cases = []
    for path in [
        _EVAL / "fixtures" / "explain_grounding_cases.jsonl",
        _REPO / "models" / "adaptive-tax" / "fixtures" / "explain_ex04_sample.json",
    ]:
        for case_id, doc in ground._load_cases(path):  # noqa: SLF001
            ground_cases.append(ground.score_one(doc, case_id=case_id))
    grounding = {
        "metric": "explanation_grounding",
        "passed": sum(1 for c in ground_cases if c["ok"]),
        "total": len(ground_cases),
        "rate": round(
            sum(1 for c in ground_cases if c["ok"]) / len(ground_cases), 4
        )
        if ground_cases
        else 0.0,
        "ok": bool(ground_cases) and all(c["ok"] for c in ground_cases),
        "cases": [
            {
                "case_id": c["case_id"],
                "ok": c["ok"],
                "grounded_sentences": c.get("grounded_sentences"),
                "total_sentences": c.get("total_sentences"),
            }
            for c in ground_cases
        ],
        "target": 1.0,
    }

    calculation = _run_pytest_examples()

    metrics = {
        "coverage": {
            "n_covered": coverage["n_covered"],
            "n_planned": coverage["n_planned"],
            "coverage_pct": coverage["coverage_pct"],
            "ok": coverage["n_covered"] == coverage["n_planned"],
            "covered_area_ids": coverage["covered_area_ids"],
            "pending_area_ids": coverage["pending_area_ids"],
            "target": "≥ 8/8 core areas",
        },
        "calculation_accuracy": calculation,
        "provenance_completeness": {
            "ok": provenance["ok"],
            "mode": provenance.get("mode"),
            "n_cases": len(provenance.get("cases") or []),
            "target": 1.0,
            "rate": 1.0 if provenance["ok"] else None,
        },
        "citation_faithfulness": citation,
        "explanation_grounding": grounding,
        "amendment_adaptivity": {
            "ok": adaptivity.get("ok"),
            "ex08_delta": (adaptivity.get("ex08_delta") or {}).get("actual_abs_delta"),
            "target": "T1 ≠ T2 with Sec 52 quotes",
        },
        "extraction_precision_labeled_sec52": extraction_labeled,
        "extraction_precision_harvest_sections": {
            "ok": extraction_harvest["ok"],
            "precision": extraction_harvest["precision"],
            "correct": extraction_harvest["correct"],
            "total": extraction_harvest["total"],
            "n_sections": extraction_harvest["n_sections"],
            "sections": [
                {
                    "section_key": s.get("section_key"),
                    "coverage_area": s.get("coverage_area"),
                    "precision": s.get("precision"),
                    "ok": s.get("ok"),
                }
                for s in extraction_harvest.get("sections") or []
            ],
            "target": 1.0,
        },
    }

    all_ok = all(
        bool(m.get("ok"))
        for m in metrics.values()
        if isinstance(m, dict) and "ok" in m
    )

    return {
        "run_id": f"phase5_9_{datetime.now(timezone.utc).strftime('%Y_%m_%d_%H%M%S')}",
        "component": "adaptive-tax",
        "phase": "5.9",
        "scored_at_utc": datetime.now(timezone.utc).isoformat(),
        "ok": all_ok,
        "metrics": metrics,
        "notes": (
            "Phase 5.9 Chapter 4 metrics — calculator track; "
            "graph size is not a success gate."
        ),
    }


def _metrics_md(report: dict[str, Any]) -> str:
    m = report["metrics"]
    cov = m["coverage"]
    calc = m["calculation_accuracy"]
    prov = m["provenance_completeness"]
    cite = m["citation_faithfulness"]
    ground = m["explanation_grounding"]
    adapt = m["amendment_adaptivity"]
    ext = m["extraction_precision_labeled_sec52"]
    harv = m["extraction_precision_harvest_sections"]

    lines = [
        "# Adaptive Tax evaluation metrics (dissertation Chapter 4)",
        "",
        f"Filled from Phase **5.9** offline scoring run `{report['run_id']}` "
        f"({report['scored_at_utc']}). "
        "OpenAI explain mode is validated by the same citation/grounding scripts "
        "when live responses are saved to JSON.",
        "",
        "| Metric | Method | Result | Notes |",
        "|--------|--------|--------|-------|",
        (
            f"| **Coverage** | `coverage/score_coverage.py` vs checklist | "
            f"**{cov['n_covered']}/{cov['n_planned']} = {cov['coverage_pct']}%** | "
            f"Core areas: {', '.join(cov['covered_area_ids'])} |"
        ),
        (
            f"| **Calculation accuracy** | Named goldens "
            f"`test_rule_engine_examples.py` | "
            f"**{'pass' if calc['ok'] else 'FAIL'}** "
            f"({calc.get('n_example_files')} example files; "
            f"{calc.get('summary_line', '')}) | "
            "ex01–ex08 + covered-area goldens (ex09–ex17) |"
        ),
        (
            f"| **Provenance completeness** | `provenance/score_provenance.py` "
            f"(strict) | **{prov.get('rate', '—')}** "
            f"({'ok' if prov['ok'] else 'FAIL'}; {prov.get('n_cases')} cases) | "
            "Every executable step → Act section + source_quote + source_doc_id |"
        ),
        (
            f"| **Citation faithfulness** | `sections_cited ⊆ retrieved`; "
            f"`citation_faithfulness/score_citations.py` | "
            f"**{cite['passed']}/{cite['total']} = {cite['rate']}** | "
            "`explain_ex04_sample.json` |"
        ),
        (
            f"| **Explanation grounding** | sentence → chunk / rule_source; "
            f"`explanation_grounding/score_grounding.py` | "
            f"**{ground['passed']}/{ground['total']} = {ground['rate']}** | "
            "Positive fixtures + production sample; negative control separate |"
        ),
        (
            f"| **Amendment adaptivity** | dual-YA Sec 52; "
            f"`amendment_adaptivity/score_adaptivity.py` | "
            f"**{'pass' if adapt['ok'] else 'FAIL'}** "
            f"(ex08 delta tax = {adapt.get('ex08_delta')}) | "
            "T1 ≠ T2 with distinct Sec 52 quotes |"
        ),
        (
            f"| Extraction precision (Sec 52 labeled) | "
            f"`extraction/score_extraction.py` | "
            f"**{ext['correct']}/{ext['total']} = {ext['precision']}** | "
            "Act 02/2025 20-field sample |"
        ),
        (
            f"| Extraction precision (harvested sections) | "
            f"`extraction/score_harvest_sections.py` | "
            f"**{harv['correct']}/{harv['total']} = {harv['precision']}** "
            f"({harv['n_sections']} sections) | "
            "Per `*_harvest_v1.json` Act-backed field checks |"
        ),
        "",
        "Reproduce: see [README.md](../README.md) and "
        "[phase5/README.md](README.md). "
        "Viva demo: `scripts/adaptive_tax_phase5_demo.py`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--write-run",
        action="store_true",
        default=True,
        help="Write JSON under evaluation/adaptive-tax/runs/ (default on)",
    )
    p.add_argument("--no-write-run", action="store_true")
    p.add_argument(
        "--write-metrics-md",
        action="store_true",
        help="Overwrite evaluation/adaptive-tax/metrics_table.md",
    )
    args = p.parse_args(argv)

    report = run_all()
    print(json.dumps(report, indent=2, default=str))
    print()
    print(f"Chapter 4 metrics ok={report['ok']}")

    if args.write_run and not args.no_write_run:
        _RUNS.mkdir(parents=True, exist_ok=True)
        out = _RUNS / f"{report['run_id']}.json"
        out.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        print(f"Wrote {out.relative_to(_REPO)}")

    if args.write_metrics_md:
        md_path = _EVAL / "metrics_table.md"
        md_path.write_text(_metrics_md(report), encoding="utf-8")
        print(f"Wrote {md_path.relative_to(_REPO)}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
