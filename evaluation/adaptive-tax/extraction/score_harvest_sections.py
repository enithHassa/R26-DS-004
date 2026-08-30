#!/usr/bin/env python3
"""Extraction precision per harvested Phase 5 section.

Scores each ``models/adaptive-tax/fixtures/*_harvest_v1.json`` for required
Act-backed fields on every rule row:

  section, concept_id, source_quote (≥ min length), engine_handler (if executable),
  assessment_years (non-empty).

Precision = correct_fields / total_required_fields (aggregated and per section).

Example::

  .\\.venv-backend\\Scripts\\python.exe \\
    evaluation/adaptive-tax/extraction/score_harvest_sections.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_DEFAULT_FIXTURES = _REPO / "models" / "adaptive-tax" / "fixtures"
_MIN_QUOTE = 40


def _score_rule(rule: dict[str, Any], *, min_quote: int) -> tuple[int, int, list[str]]:
    checks: list[tuple[str, bool]] = [
        ("section", bool(str(rule.get("section") or "").strip())),
        ("concept_id", bool(str(rule.get("concept_id") or "").strip())),
        (
            "source_quote",
            len(str(rule.get("source_quote") or "").strip()) >= min_quote,
        ),
        (
            "assessment_years",
            isinstance(rule.get("assessment_years"), list)
            and len(rule.get("assessment_years") or []) > 0,
        ),
    ]
    if rule.get("executable") is True:
        checks.append(
            ("engine_handler", bool(str(rule.get("engine_handler") or "").strip()))
        )

    correct = 0
    mismatches: list[str] = []
    for name, ok in checks:
        if ok:
            correct += 1
        else:
            mismatches.append(name)
    return correct, len(checks), mismatches


def score_harvest_file(
    path: Path, *, min_quote: int = _MIN_QUOTE
) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rules = list(doc.get("rules") or [])
    correct = 0
    total = 0
    rule_details: list[dict[str, Any]] = []
    for i, rule in enumerate(rules):
        c, t, bad = _score_rule(rule, min_quote=min_quote)
        correct += c
        total += t
        rule_details.append(
            {
                "rule_index": i,
                "concept_id": rule.get("concept_id"),
                "correct": c,
                "total": t,
                "mismatches": bad,
                "ok": not bad,
            }
        )
    precision = (correct / total) if total else 0.0
    return {
        "file": path.name,
        "section_key": doc.get("section_key"),
        "coverage_area": doc.get("coverage_area"),
        "phase": doc.get("phase"),
        "n_rules": len(rules),
        "correct": correct,
        "total": total,
        "precision": round(precision, 4),
        "ok": correct == total and total > 0,
        "rules": rule_details,
    }


def score_all(
    fixtures_dir: Path | None = None, *, min_quote: int = _MIN_QUOTE
) -> dict[str, Any]:
    root = fixtures_dir or _DEFAULT_FIXTURES
    paths = sorted(root.glob("*_harvest_v1.json"))
    sections = [score_harvest_file(p, min_quote=min_quote) for p in paths]
    correct = sum(s["correct"] for s in sections)
    total = sum(s["total"] for s in sections)
    precision = (correct / total) if total else 0.0
    return {
        "metric": "extraction_precision_per_harvested_section",
        "n_sections": len(sections),
        "correct": correct,
        "total": total,
        "precision": round(precision, 4),
        "ok": all(s["ok"] for s in sections) and bool(sections),
        "sections": sections,
        "target": 1.0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--min-quote", type=int, default=_MIN_QUOTE)
    p.add_argument("--fixtures-dir", type=Path, default=_DEFAULT_FIXTURES)
    args = p.parse_args(argv)

    result = score_all(args.fixtures_dir, min_quote=args.min_quote)
    # Compact sections for stdout
    printable = {
        **result,
        "sections": [
            {
                "section_key": s["section_key"],
                "coverage_area": s["coverage_area"],
                "file": s["file"],
                "precision": s["precision"],
                "correct": s["correct"],
                "total": s["total"],
                "ok": s["ok"],
            }
            for s in result["sections"]
        ],
    }
    print(json.dumps(printable, indent=2))
    print(
        f"harvest_section_precision = {result['correct']}/{result['total']} "
        f"= {result['precision']}  ({result['n_sections']} sections)"
    )
    for s in printable["sections"]:
        status = "OK" if s["ok"] else "FAIL"
        print(
            f"  [{status}] sec {s['section_key']} ({s['coverage_area']}): "
            f"{s['correct']}/{s['total']} = {s['precision']}"
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
