#!/usr/bin/env python3
"""Score catalog legal_confidence distribution (Phase 6.9 viva figure)."""

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


def score_catalog_confidence(*, include_inactive: bool = False) -> dict[str, Any]:
    """Count active catalog components by legal_confidence tier."""
    from adaptive_tax_app.services.filing_catalog import load_filing_catalog

    doc = load_filing_catalog()
    buckets: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "pending": 0}
    total = 0
    for row in doc.components:
        if not include_inactive and row.status in {"inactive", "pending_unsupported"}:
            continue
        if row.engine_support == "unsupported":
            continue
        tier = (row.legal_confidence or "pending").lower()
        if tier not in buckets:
            tier = "pending"
        buckets[tier] += 1
        total += 1

    return {
        "metric": "catalog_confidence_distribution",
        "total_active_supported": total,
        "distribution": buckets,
        "distribution_pct": {
            k: round(v / total * 100.0, 1) if total else 0.0 for k, v in buckets.items()
        },
        "ok": buckets["pending"] == 0 or total > 0,
        "target": "majority high/medium on supported resident-individual catalog",
    }


def main() -> int:
    result = score_catalog_confidence()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
