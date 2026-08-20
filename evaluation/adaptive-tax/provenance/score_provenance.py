#!/usr/bin/env python3
"""Score Adaptive Tax provenance completeness on named examples / a calc response.

Provenance completeness = fraction of tax-affecting trace steps that have
non-empty rule_source_ids resolving to approved Act-backed quotes
(section + source_quote + official source_doc_id).

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  $env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
  $env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/provenance/score_provenance.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_COMP = _REPO / "backend" / "comp-adaptive-tax"
_EXAMPLES = _REPO / "models" / "adaptive-tax" / "examples"

for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _expand_cases(doc: dict[str, Any]) -> list[dict[str, Any]]:
    if "variants" in doc:
        return list(doc["variants"])
    return [doc]


def score_response(response: Any) -> dict[str, Any]:
    from adaptive_tax_app.services.provenance import (
        OFFICIAL_ACT_SOURCE_DOC_IDS,
        _load_bootstrap_records,
    )

    steps = list(getattr(response, "calculation_trace", None) or [])
    records = _load_bootstrap_records()
    by_key: dict[str, Any] = {}
    for rec in records:
        by_key[rec.id] = rec
        for alias in rec.aliases:
            by_key.setdefault(alias, rec)

    total = 0
    ok = 0
    details: list[dict[str, Any]] = []
    for step in steps:
        step_id = getattr(step, "step_id", "")
        ids = list(getattr(step, "rule_source_ids", None) or [])
        total += 1
        resolved = False
        for sid in ids:
            rec = by_key.get(sid)
            if rec is not None and rec.is_valid_act_backed():
                resolved = True
                break
            # Also accept enriched refs on the response.
        if not resolved:
            for ref in getattr(response, "rule_source_refs", None) or []:
                if ref.id not in ids:
                    continue
                if (
                    (ref.status or "").lower() == "approved"
                    and (ref.section or "").strip()
                    and (ref.source_quote or "").strip()
                    and (ref.source_doc_id or "") in OFFICIAL_ACT_SOURCE_DOC_IDS
                ):
                    resolved = True
                    break
        if resolved:
            ok += 1
        details.append(
            {
                "step_id": step_id,
                "rule_source_ids": ids,
                "ok": resolved,
                "provenance": getattr(step, "provenance", None),
            }
        )

    ratio = (ok / total) if total else 0.0
    return {
        "n_steps": total,
        "n_ok": ok,
        "provenance_completeness": round(ratio, 4),
        "provenance_complete_flag": bool(
            getattr(response, "provenance_complete", False)
        ),
        "steps": details,
        "ok": ratio >= 1.0 and total > 0,
    }


def score_examples() -> dict[str, Any]:
    os.environ.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    os.environ.setdefault("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")

    from adaptive_tax_app.config import get_adaptive_tax_settings
    from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
    from adaptive_tax_app.services.param_store import clear_param_store_cache
    from adaptive_tax_app.services.provenance import clear_provenance_cache
    from adaptive_tax_app.services.rule_engine import calculate, default_file_kg

    get_adaptive_tax_settings.cache_clear()
    clear_param_store_cache()
    clear_provenance_cache()

    kg = default_file_kg()
    cases_out: list[dict[str, Any]] = []
    all_ok = True
    for path in sorted(_EXAMPLES.glob("ex*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for case in _expand_cases(doc):
            case_id = str(case.get("id") or path.stem)
            result = calculate(
                CalculateTaxRequestV1.model_validate(case["inputs"]),
                kg=kg,
            )
            scored = score_response(result)
            cases_out.append({"id": case_id, **scored})
            if not scored["ok"]:
                all_ok = False

    return {
        "metric": "provenance_completeness",
        "mode": "strict",
        "cases": cases_out,
        "ok": all_ok,
        "target": 1.0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--examples",
        action="store_true",
        default=True,
        help="Score ex01–ex08 under strict provenance (default)",
    )
    args = parser.parse_args(argv)
    _ = args
    result = score_examples()
    print(json.dumps(result, indent=2))
    print(f"provenance_completeness ok={result['ok']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
