#!/usr/bin/env python3
"""Score Adaptive Tax Phase 5 Coverage metric from coverage_checklist_v1.json.

Coverage = N_covered / N_planned

An area counts as covered only when harvested, approved, engine_wired, and
provenance_complete are all true. Optional areas (e.g. sec52_carry_forward) are
excluded from the core denominator unless --include-optional is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[3]
_DEFAULT_CHECKLIST = (
    _REPO / "models" / "adaptive-tax" / "harvest" / "coverage_checklist_v1.json"
)


def _is_covered(area: dict[str, Any]) -> bool:
    return bool(
        area.get("harvested")
        and area.get("approved")
        and area.get("engine_wired")
        and area.get("provenance_complete")
    )


def score_coverage(
    checklist: dict[str, Any],
    *,
    include_optional: bool = False,
) -> dict[str, Any]:
    areas = list(checklist.get("areas") or [])
    if not include_optional:
        areas = [a for a in areas if not a.get("optional")]

    planned = len(areas)
    covered_areas = [a for a in areas if _is_covered(a)]
    covered = len(covered_areas)
    ratio = (covered / planned) if planned else 0.0

    return {
        "n_planned": planned,
        "n_covered": covered,
        "coverage": round(ratio, 4),
        "coverage_pct": round(ratio * 100.0, 2),
        "covered_area_ids": [str(a.get("area_id")) for a in covered_areas],
        "pending_area_ids": [
            str(a.get("area_id")) for a in areas if not _is_covered(a)
        ],
        "include_optional": include_optional,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checklist",
        type=Path,
        default=_DEFAULT_CHECKLIST,
        help="Path to coverage_checklist_v1.json",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Include optional areas (e.g. sec52_carry_forward) in denominator",
    )
    args = parser.parse_args(argv)

    path: Path = args.checklist
    if not path.is_file():
        print(f"ERROR: checklist not found: {path}", file=sys.stderr)
        return 2

    doc = json.loads(path.read_text(encoding="utf-8"))
    result = score_coverage(doc, include_optional=args.include_optional)
    print(json.dumps(result, indent=2))
    print(
        f"Coverage = {result['n_covered']}/{result['n_planned']} "
        f"({result['coverage_pct']}%)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
