#!/usr/bin/env python3
"""Adaptive Tax Phase 6.9 viva demo — extends Phase 5.9 with catalog coverage + queue.

Offline by default. Adds:
  - Section-grain legal coverage snapshot
  - Unsupported rule queue (Act 11/2026 novelty narrative)
  - knowledge_versions / Calculated Using stamps
  - Guide/Master executable-cite guard

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  $env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_phase6_demo.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_PHASE5 = _SCRIPTS / "adaptive_tax_phase5_demo.py"
_EVAL6 = _REPO / "evaluation" / "adaptive-tax" / "phase6"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _banner(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main() -> int:
    os.environ.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    os.environ.setdefault("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")

    for p in (_REPO, _REPO / "backend" / "comp-adaptive-tax"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    phase5 = _load(_PHASE5)
    rc = phase5.run_offline()
    if rc != 0:
        return rc

    _banner("6) Phase 6.8 — legal coverage (section grain)")
    from adaptive_tax_app.services.legal_coverage import build_legal_coverage

    lc = build_legal_coverage()
    print(
        f"Checklist areas: {lc.area_summary.n_covered}/{lc.area_summary.n_planned} "
        f"({lc.area_summary.coverage_pct}%)"
    )
    for sec in lc.sections:
        print(
            f"  {sec.label}: {sec.n_covered}/{sec.n_planned} "
            f"({sec.coverage_pct}%)"
        )

    _banner("7) Unsupported rule queue + Act 11/2026 novelty")
    from adaptive_tax_app.services.filing_catalog import (
        component_by_id,
        list_unsupported_components,
    )

    unsupported = list_unsupported_components()
    print(f"Pending unsupported: {len(unsupported)}")
    for row in unsupported:
        print(f"  - {row.component_id} (Sec {row.section}) — {row.display_name}")
    bf = component_by_id("qp_brought_forward")
    if bf:
        print()
        print(
            f"Supported Act 11/2026 example: {bf.component_id} "
            f"source_doc_id={bf.source_doc_id} engine_support={bf.engine_support}"
        )

    _banner("8) Calculated Using / version strip stamps")
    from adaptive_tax_app.services.filing_catalog import knowledge_versions_from_catalog

    for ya in ("2024_25", "2025_26"):
        kv = knowledge_versions_from_catalog(assessment_year=ya, param_set="current")
        print(f"YA {ya}: {json.dumps(kv, indent=2)}")

    _banner("9) Guide/Master executable-cite guard")
    cites = _load(_EVAL6 / "score_executable_cites.py")
    cite_result = cites.score_executable_cites()
    print(f"ok={cite_result['ok']} violations={len(cite_result['violations'])}")
    if not cite_result["ok"]:
        for v in cite_result["violations"]:
            print(f"  VIOLATION: {v}")
        return 1

    print()
    print("Phase 6.9 demo complete.")
    print("  UI: /adaptive-tax/coverage  |  figures: evaluation/adaptive-tax/phase6/generate_figures.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
