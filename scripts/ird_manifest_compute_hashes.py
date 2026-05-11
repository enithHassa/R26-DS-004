#!/usr/bin/env python3
"""Fill sha256 and ingested_at_utc for manifest rows where file_name exists on disk.

Reads a CSV manifest, looks up each ``file_name`` under ``--files-root``, writes a new CSV.

Usage::

  python scripts/ird_manifest_compute_hashes.py \\
    --manifest data/raw/ird/source_manifest.csv \\
    --files-root data/raw/ird/downloads \\
    --out data/raw/ird/source_manifest_filled.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ird_corpus_lib import read_manifest_csv  # noqa: E402


def now_utc_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill manifest sha256 from files on disk")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--files-root", type=Path, default=Path("data/raw/ird/downloads"))
    parser.add_argument("--out", type=Path, default=None, help="Default: overwrite --manifest")
    parser.add_argument("--ingested-by", type=str, default="", help="Optional name for ingested_by column")
    args = parser.parse_args()

    rows = read_manifest_csv(args.manifest)
    if not rows:
        raise SystemExit("manifest is empty or missing header")

    out_path = args.out or args.manifest
    fieldnames = list(rows[0].keys())
    if "sha256" not in fieldnames:
        raise SystemExit("manifest must include sha256 column")
    if "ingested_at_utc" not in fieldnames:
        raise SystemExit("manifest must include ingested_at_utc column")

    stamp = now_utc_iso()
    updated = 0
    missing = 0

    for row in rows:
        fn = (row.get("file_name") or "").strip()
        if not fn:
            continue
        p = args.files_root / fn
        if not p.is_file():
            print(f"missing file (skip hash): {p}")
            missing += 1
            continue
        row["sha256"] = sha256_file(p)
        row["ingested_at_utc"] = stamp
        if args.ingested_by:
            row["ingested_by"] = args.ingested_by
        updated += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {out_path} (hashes updated for {updated} rows, {missing} files missing)")


if __name__ == "__main__":
    main()
