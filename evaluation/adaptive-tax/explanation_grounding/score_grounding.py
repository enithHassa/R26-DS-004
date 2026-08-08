#!/usr/bin/env python3
"""Explanation grounding: every narrative sentence maps to chunk_id or rule_source_id.

Mapping rules (fixture / OpenAI post-hoc):

* Each ``steps_explained[].narrative`` sentence is grounded if that step has at
  least one ``evidence_chunk_ids`` entry or a non-null ``rule_source_id``.
* ``summary`` sentences are grounded if ``insufficient_evidence`` is false and
  (``sections_cited`` non-empty or any step has evidence ids).
* ``insufficient_evidence`` responses with empty narratives pass (nothing to ground).

Example::

  .\\.venv-backend\\Scripts\\python.exe \\
    evaluation/adaptive-tax/explanation_grounding/score_grounding.py \\
    --input evaluation/adaptive-tax/fixtures/explain_grounding_cases.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    parts = [p.strip() for p in _SENT_SPLIT.split(cleaned) if p.strip()]
    return parts or [cleaned]


def _step_has_evidence(step: dict[str, Any]) -> bool:
    chunks = step.get("evidence_chunk_ids") or []
    rule_id = step.get("rule_source_id")
    return bool(chunks) or bool(rule_id)


def score_one(doc: dict[str, Any], *, case_id: str = "") -> dict[str, Any]:
    if doc.get("insufficient_evidence") is True:
        summary_sents = split_sentences(str(doc.get("summary") or ""))
        step_sents = []
        for step in doc.get("steps_explained") or []:
            step_sents.extend(split_sentences(str(step.get("narrative") or "")))
        empty = not summary_sents and not step_sents
        return {
            "case_id": case_id or doc.get("id") or "",
            "ok": empty,
            "grounded_sentences": 0,
            "total_sentences": 0,
            "ungrounded": [] if empty else ["non_empty_narrative_with_insufficient_evidence"],
        }

    ungrounded: list[str] = []
    grounded = 0
    total = 0

    any_step_evidence = any(
        _step_has_evidence(s) for s in (doc.get("steps_explained") or [])
    )
    summary_ok = bool(doc.get("sections_cited")) or any_step_evidence
    for sent in split_sentences(str(doc.get("summary") or "")):
        total += 1
        if summary_ok:
            grounded += 1
        else:
            ungrounded.append(f"summary:{sent[:80]}")

    for step in doc.get("steps_explained") or []:
        sid = str(step.get("step_id") or "?")
        has_ev = _step_has_evidence(step)
        for sent in split_sentences(str(step.get("narrative") or "")):
            total += 1
            if has_ev:
                grounded += 1
            else:
                ungrounded.append(f"{sid}:{sent[:80]}")

    return {
        "case_id": case_id or doc.get("id") or "",
        "ok": len(ungrounded) == 0 and total > 0,
        "grounded_sentences": grounded,
        "total_sentences": total,
        "ungrounded": ungrounded,
    }


def _load_cases(path: Path) -> list[tuple[str, dict[str, Any]]]:
    text = path.read_text(encoding="utf-8").strip()
    if path.suffix == ".jsonl":
        out: list[tuple[str, dict[str, Any]]] = []
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            # Allow wrapper {id, explain: {...}}
            if "explain" in doc and isinstance(doc["explain"], dict):
                out.append((str(doc.get("id") or f"line_{i}"), doc["explain"]))
            else:
                out.append((str(doc.get("id") or f"line_{i}"), doc))
        return out
    doc = json.loads(text)
    return [(str(doc.get("id") or path.stem), doc)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, nargs="+", required=True)
    args = p.parse_args()

    results = []
    for path in args.input:
        for case_id, doc in _load_cases(path):
            results.append(score_one(doc, case_id=case_id))

    n_ok = sum(1 for r in results if r["ok"])
    summary = {
        "metric": "explanation_grounding",
        "passed": n_ok,
        "total": len(results),
        "rate": round(n_ok / len(results), 4) if results else 0.0,
        "cases": results,
    }
    print(json.dumps(summary, indent=2))
    print(f"explanation_grounding = {n_ok}/{len(results)}")
    return 0 if n_ok == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
