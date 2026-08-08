#!/usr/bin/env python3
"""Citation faithfulness: sections_citedsubseteq sections_retrieved.

Reads one or more ExplainTaxResponse JSON files (or a JSONL of responses).

Example::

  .\\.venv-backend\\Scripts\\python.exe \\
    evaluation/adaptive-tax/citation_faithfulness/score_citations.py \\
    --input models/adaptive-tax/fixtures/explain_ex04_sample.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def score_one(doc: dict[str, Any], *, case_id: str = "") -> dict[str, Any]:
    cited = [str(s).strip() for s in (doc.get("sections_cited") or []) if str(s).strip()]
    retrieved = {
        str(s).strip()
        for s in (doc.get("sections_retrieved") or [])
        if str(s).strip()
    }
    extras = [s for s in cited if s not in retrieved]
    ok = len(extras) == 0
    # insufficient_evidence responses should have empty cited
    if doc.get("insufficient_evidence") is True:
        ok = len(cited) == 0
        extras = cited
    return {
        "case_id": case_id or doc.get("id") or doc.get("calc_id") or "",
        "ok": ok,
        "sections_cited": cited,
        "sections_retrieved": sorted(retrieved),
        "hallucinated": extras,
    }


def _load_cases(path: Path) -> list[tuple[str, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        out: list[tuple[str, dict[str, Any]]] = []
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            out.append((str(doc.get("id") or f"line_{i}"), doc))
        return out
    doc = json.loads(text)
    if isinstance(doc, list):
        return [(str(d.get("id") or i), d) for i, d in enumerate(doc)]
    return [(str(doc.get("id") or path.stem), doc)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input",
        type=Path,
        nargs="+",
        required=True,
        help="Explain JSON / JSONL file(s)",
    )
    args = p.parse_args()

    results = []
    for path in args.input:
        for case_id, doc in _load_cases(path):
            results.append(score_one(doc, case_id=case_id))

    n_ok = sum(1 for r in results if r["ok"])
    summary = {
        "metric": "citation_faithfulness",
        "passed": n_ok,
        "total": len(results),
        "rate": round(n_ok / len(results), 4) if results else 0.0,
        "cases": results,
    }
    print(json.dumps(summary, indent=2))
    print(f"citation_faithfulness = {n_ok}/{len(results)}")
    return 0 if n_ok == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
