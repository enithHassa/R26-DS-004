#!/usr/bin/env python3
"""Verify Guide / Master Tax KB never appear as executable provenance (Phase 6.9)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_COMP = _REPO / "backend" / "comp-adaptive-tax"

for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

BLOCKED = frozenset(
    {
        "ird-guide-ira",
        "ird-master-tax-kb",
        "master-tax-kb",
        "guide-to-inland-revenue",
    }
)


def _check_path(label: str, doc_id: str | None, violations: list[dict[str, str]]) -> None:
    if not doc_id:
        return
    normalized = doc_id.strip().lower()
    if normalized in BLOCKED or "guide" in normalized or "master" in normalized:
        if normalized in BLOCKED or "master-tax" in normalized or normalized == "ird-guide-ira":
            violations.append({"where": label, "source_doc_id": doc_id})


def score_executable_cites() -> dict[str, Any]:
    """Scan bootstrap, catalog, and golden calc responses for blocked source_doc_id."""
    from adaptive_tax_app.services.filing_catalog import load_filing_catalog
    from adaptive_tax_app.services.provenance import OFFICIAL_ACT_SOURCE_DOC_IDS, _load_bootstrap_records

    violations: list[dict[str, str]] = []

    for rec in _load_bootstrap_records():
        _check_path(f"bootstrap:{rec.id}", rec.source_doc_id, violations)

    doc = load_filing_catalog()
    for row in doc.components:
        if row.status == "approved" or row.engine_support == "supported":
            _check_path(f"catalog:{row.component_id}", row.source_doc_id, violations)

    # Golden examples (strict provenance path)
    examples_dir = _REPO / "models" / "adaptive-tax" / "examples"
    n_examples = 0
    for path in sorted(examples_dir.glob("ex*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        cases = raw.get("variants") or [raw]
        for case in cases:
            n_examples += 1
            for ref in case.get("expected_rule_source_refs") or []:
                _check_path(f"{path.name}:expected_ref", ref.get("source_doc_id"), violations)
            for ref in case.get("rule_source_refs") or []:
                _check_path(f"{path.name}:ref", ref.get("source_doc_id"), violations)

    # Blocked set must not overlap official allow-list
    overlap = sorted(BLOCKED & {d.lower() for d in OFFICIAL_ACT_SOURCE_DOC_IDS})

    return {
        "metric": "executable_cites_no_guide_master",
        "ok": len(violations) == 0 and len(overlap) == 0,
        "violations": violations,
        "blocked_ids_checked": sorted(BLOCKED),
        "official_allowlist_size": len(OFFICIAL_ACT_SOURCE_DOC_IDS),
        "n_golden_cases_scanned": n_examples,
        "target": "Guide PDF and Master Tax KB never in executable provenance",
    }


def main() -> int:
    result = score_executable_cites()
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
