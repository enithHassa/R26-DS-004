#!/usr/bin/env python3
"""Extraction precision: correct fields / total fields on the 20-field labeled sample.

Compares a predicted ExtractedRulesPayload (fixture or live extract JSON) against
``labeled_sample_20fields.json``.

Example::

  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/extraction/score_extraction.py
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/extraction/score_extraction.py \\
    --predicted models/adaptive-tax/fixtures/section52_extract_sample.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_DEFAULT_GOLD = _HERE / "labeled_sample_20fields.json"
_DEFAULT_PRED = (
    _REPO / "models" / "adaptive-tax" / "fixtures" / "section52_extract_sample.json"
)


def _norm(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, float):
        if value == int(value):
            return float(int(value))
        return float(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    return value


def _get_path(rule: dict[str, Any], path: str) -> Any:
    return rule.get(path)


def score(
    gold_doc: dict[str, Any],
    predicted_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    fields = gold_doc.get("fields") or []
    correct = 0
    total = 0
    mismatches: list[dict[str, Any]] = []

    for row in fields:
        total += 1
        idx = int(row["rule_index"])
        path = str(row["path"])
        expected = _norm(row.get("gold"))
        if idx >= len(predicted_rules):
            mismatches.append(
                {
                    "field_id": row.get("field_id"),
                    "expected": expected,
                    "actual": None,
                    "reason": "missing_rule",
                }
            )
            continue
        actual = _norm(_get_path(predicted_rules[idx], path))
        if actual == expected:
            correct += 1
        else:
            mismatches.append(
                {
                    "field_id": row.get("field_id"),
                    "expected": expected,
                    "actual": actual,
                    "reason": "value_mismatch",
                }
            )

    precision = (correct / total) if total else 0.0
    return {
        "metric": "extraction_precision",
        "correct": correct,
        "total": total,
        "precision": round(precision, 4),
        "mismatches": mismatches,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gold", type=Path, default=_DEFAULT_GOLD)
    p.add_argument(
        "--predicted",
        type=Path,
        default=_DEFAULT_PRED,
        help="ExtractedRulesPayload JSON ({rules:[...]})",
    )
    args = p.parse_args()

    gold = json.loads(args.gold.read_text(encoding="utf-8"))
    pred_raw = json.loads(args.predicted.read_text(encoding="utf-8"))
    rules = pred_raw.get("rules") if isinstance(pred_raw, dict) else None
    if not isinstance(rules, list):
        print("[FAIL] predicted JSON must contain a rules array", file=sys.stderr)
        return 2

    result = score(gold, rules)
    print(json.dumps(result, indent=2))
    print(
        f"extraction_precision = {result['correct']}/{result['total']} "
        f"= {result['precision']}"
    )
    return 0 if result["correct"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
