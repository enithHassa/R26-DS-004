#!/usr/bin/env python3
"""Phase 6.9 metrics: legal coverage, confidence, unsupported queue, regression suite.

Extends Phase 5.9 Chapter 4 runner with Phase 6 filing-catalog + viva dashboard metrics.

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  $env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
  $env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/phase6/run_chapter4_metrics.py --write-metrics-md
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/phase6/generate_figures.py
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
_PHASE5 = _EVAL / "phase5" / "run_chapter4_metrics.py"


def _load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_pytest_files(paths: list[Path], *, label: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{_COMP}{os.pathsep}{_REPO}"
    env.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    env.setdefault("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *[str(p) for p in paths], "-q", "--tb=line"],
        cwd=str(_REPO),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return {
        "metric": label,
        "ok": proc.returncode == 0,
        "pytest_returncode": proc.returncode,
        "files": [p.name for p in paths],
        "summary_line": out.strip().splitlines()[-1] if out.strip() else "",
        "target": "all tests pass",
    }


def _legal_coverage() -> dict[str, Any]:
    from adaptive_tax_app.services.legal_coverage import build_legal_coverage

    cov = build_legal_coverage()
    sec5 = next(s for s in cov.sections if s.section_key == "5")
    return {
        "metric": "legal_coverage_section_grain",
        "ok": cov.area_summary.n_covered == cov.area_summary.n_planned,
        "area_coverage_pct": cov.area_summary.coverage_pct,
        "n_areas_covered": cov.area_summary.n_covered,
        "n_areas_planned": cov.area_summary.n_planned,
        "section_5_pct": sec5.coverage_pct,
        "section_5_components": f"{sec5.n_covered}/{sec5.n_planned}",
        "sections": [
            {
                "section_key": s.section_key,
                "label": s.label,
                "n_covered": s.n_covered,
                "n_planned": s.n_planned,
                "coverage_pct": s.coverage_pct,
            }
            for s in cov.sections
        ],
        "target": "checklist 100% + section grain reported for viva",
    }


def _unsupported_queue() -> dict[str, Any]:
    from adaptive_tax_app.services.filing_catalog import list_unsupported_components

    rows = list_unsupported_components()
    act_11_2026_novelty = [
        {
            "component_id": r.component_id,
            "display_name": r.display_name,
            "section": r.section,
            "source_doc_id": r.source_doc_id,
            "status": r.status,
        }
        for r in rows
        if (r.source_doc_id or "") == "ird-amend-2026-11"
        or "2026" in (r.confidence_reason or "")
    ]
    # Supported Act 11/2026 example (not in unsupported queue)
    from adaptive_tax_app.services.filing_catalog import component_by_id

    bf = component_by_id("qp_brought_forward")
    return {
        "metric": "unsupported_rule_queue",
        "ok": len(rows) >= 1,
        "count": len(rows),
        "items": [
            {
                "component_id": r.component_id,
                "display_name": r.display_name,
                "section": r.section,
                "engine_handler": r.engine_handler,
                "status": r.status,
                "source_doc_id": r.source_doc_id,
            }
            for r in rows
        ],
        "act_11_2026_novelty_demo": {
            "unsupported_candidates": act_11_2026_novelty,
            "supported_act_11_2026_example": (
                {
                    "component_id": bf.component_id,
                    "display_name": bf.display_name,
                    "source_doc_id": bf.source_doc_id,
                    "status": bf.status,
                    "engine_support": bf.engine_support,
                }
                if bf
                else None
            ),
            "narrative": (
                "Act No. 11 of 2026 enables Sec 52(4) carry-forward (qp_brought_forward, "
                "supported). Unsupported queue holds rules awaiting handlers (e.g. qp_bank_merger)."
            ),
        },
        "target": "queue visible; Act 11/2026 novelty distinguishable",
    }


def _version_strip_checklist() -> dict[str, Any]:
    from adaptive_tax_app.services.filing_catalog import knowledge_versions_from_catalog

    ya24 = knowledge_versions_from_catalog(assessment_year="2024_25", param_set="current")
    ya25 = knowledge_versions_from_catalog(assessment_year="2025_26", param_set="current")
    required = (
        "act_version",
        "act_version_label",
        "catalog_version",
        "rule_pack_version",
        "knowledge_graph_version",
        "extraction_version",
    )
    ok = all(k in ya24 and ya24[k] for k in required) and all(
        k in ya25 and ya25[k] for k in required
    )
    return {
        "metric": "version_strip_checklist",
        "ok": ok,
        "ya_2024_25": ya24,
        "ya_2025_26": ya25,
        "screenshot_checklist": [
            "Calculator result: Calculated Using strip visible",
            "Report page: sticky Calculated Using strip",
            "Strip shows act_version_label + catalog_version + rule_pack_version",
            "YA switch changes rule_pack_version label",
        ],
        "target": "knowledge_versions stamps present for both YAs",
    }


def run_all() -> dict[str, Any]:
    os.environ.setdefault("COMP_ADAPTIVE_TAX_KG_MODE", "file")
    os.environ.setdefault("COMP_ADAPTIVE_TAX_PROVENANCE_MODE", "strict")

    phase5 = _load(_PHASE5)
    base = phase5.run_all()
    base["phase"] = "6.9"
    base["run_id"] = f"phase6_9_{datetime.now(timezone.utc).strftime('%Y_%m_%d_%H%M%S')}"

    conf = _load(_HERE / "score_catalog_confidence.py")
    cites = _load(_HERE / "score_executable_cites.py")

    filing_line_tests = [
        _COMP / "tests" / "test_phase6_foundation.py",
        _COMP / "tests" / "test_phase68_viva.py",
        _COMP / "tests" / "test_employment_sec5.py",
        _COMP / "tests" / "test_investment_income.py",
        _COMP / "tests" / "test_sec52_qualifying_payments.py",
        _COMP / "tests" / "test_business_income.py",
        _COMP / "tests" / "test_other_income.py",
        _COMP / "tests" / "test_qp_ya_acceptance.py",
    ]
    existing = [p for p in filing_line_tests if p.is_file()]

    phase6_metrics = {
        "legal_coverage_section_grain": _legal_coverage(),
        "catalog_confidence_distribution": conf.score_catalog_confidence(),
        "unsupported_rule_queue": _unsupported_queue(),
        "version_strip_checklist": _version_strip_checklist(),
        "executable_cites_no_guide_master": cites.score_executable_cites(),
        "phase6_filing_line_regression": _run_pytest_files(
            existing, label="phase6_filing_line_regression"
        ),
    }

    base["metrics"].update(phase6_metrics)
    base["notes"] = (
        "Phase 6.9 Chapter 4 metrics — extends Phase 5.9 with filing-catalog coverage, "
        "confidence distribution, unsupported queue, version strip checklist, and "
        "Guide/Master executable-cite guard."
    )

    all_ok = all(
        bool(m.get("ok"))
        for m in base["metrics"].values()
        if isinstance(m, dict) and "ok" in m
    )
    base["ok"] = all_ok
    return base


def _metrics_md(report: dict[str, Any]) -> str:
    phase5 = _load(_PHASE5)
    lines = phase5._metrics_md(report).splitlines()  # noqa: SLF001

    m = report["metrics"]
    lc = m["legal_coverage_section_grain"]
    conf = m["catalog_confidence_distribution"]
    uns = m["unsupported_rule_queue"]
    ver = m["version_strip_checklist"]
    cite = m["executable_cites_no_guide_master"]
    reg = m["phase6_filing_line_regression"]

    insert_at = next(i for i, line in enumerate(lines) if line.startswith("Reproduce:"))
    phase6_rows = [
        "",
        "## Phase 6.9 (filing catalog + viva)",
        "",
        "| Metric | Method | Result | Notes |",
        "|--------|--------|--------|-------|",
        (
            f"| **Legal coverage (section grain)** | "
            f"`GET /knowledge/legal-coverage` / `legal_coverage.py` | "
            f"**areas {lc['n_areas_covered']}/{lc['n_areas_planned']} = "
            f"{lc['area_coverage_pct']}%**; Sec 5 {lc['section_5_components']} | "
            f"Viva dashboard `/adaptive-tax/coverage` |"
        ),
        (
            f"| **Catalog confidence distribution** | "
            f"`phase6/score_catalog_confidence.py` | "
            f"**high={conf['distribution']['high']}, medium={conf['distribution']['medium']}, "
            f"low={conf['distribution']['low']}, pending={conf['distribution']['pending']}** | "
            f"Supported active catalog components |"
        ),
        (
            f"| **Unsupported rule queue** | "
            f"`GET /filing-catalog/unsupported` | "
            f"**{uns['count']} pending** | "
            f"Act 11/2026: supported `qp_brought_forward`; unsupported e.g. `qp_bank_merger` |"
        ),
        (
            f"| **Version strip (Calculated Using)** | "
            f"`knowledge_versions_from_catalog()` | "
            f"**{'pass' if ver['ok'] else 'FAIL'}** | "
            f"Screenshot checklist in `phase6/viva_figure_checklist.md` |"
        ),
        (
            f"| **Guide/Master not executable** | "
            f"`phase6/score_executable_cites.py` | "
            f"**{'pass' if cite['ok'] else 'FAIL'}** "
            f"({cite['n_golden_cases_scanned']} goldens scanned) | "
            f"No `ird-guide-ira` / Master KB in bootstrap or approved catalog |"
        ),
        (
            f"| **Phase 6 filing-line regression** | "
            f"pytest filing-line suite | "
            f"**{'pass' if reg['ok'] else 'FAIL'}** ({reg.get('summary_line', '')}) | "
            f"Phase 5 goldens + phase6/68 + emp/inv/QP/biz/other |"
        ),
        "",
    ]
    return "\n".join(lines[:insert_at] + phase6_rows + lines[insert_at:])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write-run", action="store_true", default=True)
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
    print(f"Chapter 4 metrics (Phase 6.9) ok={report['ok']}")

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
