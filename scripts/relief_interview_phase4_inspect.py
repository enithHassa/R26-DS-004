#!/usr/bin/env python3
"""Print Phase 4 staging rows with their quote-gate verdicts (no API calls).

Usage:
  py -3 scripts/relief_interview_phase4_inspect.py                 # all staging files
  py -3 scripts/relief_interview_phase4_inspect.py --doc ird-amend-2025-02
  py -3 scripts/relief_interview_phase4_inspect.py --rejected-only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = REPO_ROOT / "models" / "adaptive-tax" / "relief-interview" / "extracted"


def label(row: dict) -> str:
    return str(
        row.get("band_label") or row.get("display_name") or row.get("description") or "?"
    )


def value(row: dict) -> str:
    parts = []
    if row.get("row_kind") == "rate_band":
        parts.append(f"{row.get('lower', '')}..{row.get('upper', '') or 'inf'}")
        parts.append(f"@{row.get('rate_percent', '')}%")
    if row.get("cap_amount"):
        parts.append(f"cap={row['cap_amount']}")
    if row.get("value"):
        parts.append(f"value={row['value']}")
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc", default=None)
    parser.add_argument("--section", default=None)
    parser.add_argument("--rejected-only", action="store_true")
    parser.add_argument("--quotes", action="store_true", help="Show quote text")
    args = parser.parse_args()

    files = sorted(EXTRACTED_DIR.glob("*.json"))
    if args.doc:
        files = [f for f in files if f.name.startswith(args.doc)]
    if args.section:
        files = [f for f in files if args.section.replace(" ", "_").lower() in f.stem]

    grand_rows = grand_incl = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data["rows"]
        grand_rows += len(rows)
        grand_incl += data["included_count"]
        print("=" * 78)
        print(
            f"{data['source_doc_id']} | {data['section_key']} | "
            f"rows={data['row_count']} included={data['included_count']}"
        )
        for row in rows:
            if args.rejected_only and row.get("included"):
                continue
            flags = (
                f"full={int(bool(row['quote_ok_full_doc']))} "
                f"focus={int(bool(row['quote_ok_focus']))} "
                f"p2={int(bool(row.get('pass2_verbatim')))} "
                f"prov={int(bool(row.get('provenance_complete')))} "
                f"ontarget={int(bool(row.get('section_ref_on_target')))} "
                f"src={row.get('quote_source', '?')}"
            )
            mark = "OK " if row.get("included") else "REJ"
            print(f"  [{mark}] {row['row_kind']:<10} {label(row)[:52]:<52} {flags}")
            if value(row):
                print(f"         {value(row)}  | {row.get('section_ref', '')}")
            if args.quotes or not row.get("included"):
                print(f"         quote: {row.get('quote', '')[:170]!r}")
                if not row.get("included"):
                    print(f"         p2note: {str(row.get('pass2_note', ''))[:150]}")

    print("=" * 78)
    print(f"TOTAL rows={grand_rows} included={grand_incl} files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
