#!/usr/bin/env python3
"""Phase 2 Step 13: merge benchmark JSONL splits (e.g. dev + test) into one eval file for held-out runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        required=True,
        help="JSONL files in merge order (e.g. benchmark_dev.jsonl benchmark_test.jsonl)",
    )
    p.add_argument("--output", "-o", type=Path, required=True, help="Merged JSONL path")
    p.add_argument(
        "--dedupe-example-id",
        action="store_true",
        help="Keep first row per example_id when the same id appears in later files",
    )
    args = p.parse_args()

    for path in args.inputs:
        if not path.is_file():
            print(f"input not found: {path}", file=sys.stderr)
            return 2

    seen: set[str] = set()
    out_rows: list[dict[str, object]] = []
    for path in args.inputs:
        for row in _load_rows(path):
            if args.dedupe_example_id:
                eid = str(row.get("example_id", ""))
                if eid and eid in seen:
                    continue
                if eid:
                    seen.add(eid)
            out_rows.append(row)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for row in out_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"wrote {len(out_rows)} lines to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
