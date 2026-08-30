#!/usr/bin/env python3
"""Generate Phase 6.9 viva figure data + markdown (coverage bars, confidence, queue).

No matplotlib required — outputs dissertation-ready markdown under ``phase6/figures/``.

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/phase6/generate_figures.py
  .\\.venv-backend\\Scripts\\python.exe evaluation/adaptive-tax/phase6/generate_figures.py --from-run evaluation/adaptive-tax/runs/phase6_9_*.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_EVAL = _HERE.parent
_REPO = _HERE.parents[2]
_FIGURES = _HERE / "figures"


def _bar(pct: float, width: int = 24) -> str:
    filled = int(round(max(0.0, min(100.0, pct)) / 100.0 * width))
    return "#" * filled + "-" * (width - filled)


def _latest_run() -> Path | None:
    runs = sorted((_EVAL / "runs").glob("phase6_9_*.json"))
    return runs[-1] if runs else None


def _load_report(path: Path | None) -> dict[str, Any]:
    if path and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    # Inline score if no run file
    import importlib.util
    import sys

    for p in (_REPO, _REPO / "backend" / "comp-adaptive-tax"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    runner = importlib.util.spec_from_file_location(
        "run_chapter4_metrics", _HERE / "run_chapter4_metrics.py"
    )
    assert runner and runner.loader
    mod = importlib.util.module_from_spec(runner)
    runner.loader.exec_module(mod)
    return mod.run_all()


def build_figures_md(report: dict[str, Any]) -> str:
    m = report.get("metrics") or {}
    lc = m.get("legal_coverage_section_grain") or {}
    conf = m.get("catalog_confidence_distribution") or {}
    uns = m.get("unsupported_rule_queue") or {}
    ver = m.get("version_strip_checklist") or {}

    lines = [
        "# Phase 6.9 viva figures (markdown export)",
        "",
        f"Generated from run `{report.get('run_id', 'inline')}` "
        f"({report.get('scored_at_utc', '')}).",
        "",
        "Use these blocks in Chapter 4 or paste screenshots from the Coverage UI.",
        "",
        "## Figure 1 — Section-grain legal coverage bars",
        "",
        "| Section | Covered | Bar | % |",
        "|---------|---------|-----|---|",
    ]
    for sec in lc.get("sections") or []:
        pct = float(sec.get("coverage_pct") or 0)
        lines.append(
            f"| {sec.get('label', sec.get('section_key'))} | "
            f"{sec.get('n_covered')}/{sec.get('n_planned')} | "
            f"`{_bar(pct)}` | {pct:.1f}% |"
        )

    dist = conf.get("distribution") or {}
    total = conf.get("total_active_supported") or sum(dist.values()) or 1
    lines.extend(
        [
            "",
            "## Figure 2 — Catalog confidence distribution",
            "",
            "| Tier | Count | % | Bar |",
            "|------|-------|---|-----|",
        ]
    )
    for tier in ("high", "medium", "low", "pending"):
        count = int(dist.get(tier) or 0)
        pct = count / total * 100.0
        lines.append(f"| {tier} | {count} | {pct:.1f}% | `{_bar(pct)}` |")

    lines.extend(
        [
            "",
            "## Figure 3 — Unsupported rule queue (Act 11/2026 novelty demo)",
            "",
            f"**Queue size:** {uns.get('count', 0)} pending handler(s)",
            "",
        ]
    )
    demo = uns.get("act_11_2026_novelty_demo") or {}
    lines.append(f"_{demo.get('narrative', '')}_")
    lines.append("")
    lines.append("**Supported (Act No. 11 of 2026):**")
    supported = demo.get("supported_act_11_2026_example")
    if supported:
        lines.append(
            f"- `{supported.get('component_id')}` — {supported.get('display_name')} "
            f"(`{supported.get('source_doc_id')}`, {supported.get('engine_support')})"
        )
    lines.append("")
    lines.append("**Unsupported (awaiting handler):**")
    for item in uns.get("items") or []:
        lines.append(
            f"- `{item.get('component_id')}` — Section {item.get('section')} — "
            f"{item.get('display_name')} — **Pending**"
        )

    lines.extend(
        [
            "",
            "## Figure 4 — Version strip screenshot checklist",
            "",
        ]
    )
    for item in ver.get("screenshot_checklist") or []:
        lines.append(f"- [ ] {item}")
    lines.append("")
    lines.append("**YA 2024/25 stamps:**")
    for k, v in (ver.get("ya_2024_25") or {}).items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("**YA 2025/26 stamps:**")
    for k, v in (ver.get("ya_2025_26") or {}).items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--from-run",
        type=Path,
        default=None,
        help="Use existing phase6_9 run JSON (default: latest or inline score)",
    )
    args = p.parse_args(argv)

    run_path = args.from_run
    if run_path is None:
        run_path = _latest_run()

    report = _load_report(run_path)
    md = build_figures_md(report)

    _FIGURES.mkdir(parents=True, exist_ok=True)
    md_path = _FIGURES / "FIGURES.md"
    md_path.write_text(md, encoding="utf-8")

    data_path = _FIGURES / "figure_data.json"
    data_path.write_text(
        json.dumps(
            {
                "run_id": report.get("run_id"),
                "figures": {
                    "legal_coverage": report.get("metrics", {}).get(
                        "legal_coverage_section_grain"
                    ),
                    "confidence": report.get("metrics", {}).get(
                        "catalog_confidence_distribution"
                    ),
                    "unsupported_queue": report.get("metrics", {}).get(
                        "unsupported_rule_queue"
                    ),
                    "version_strip": report.get("metrics", {}).get(
                        "version_strip_checklist"
                    ),
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(md)
    print()
    print(f"Wrote {md_path.relative_to(_REPO)}")
    print(f"Wrote {data_path.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
