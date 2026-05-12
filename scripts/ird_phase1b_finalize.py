#!/usr/bin/env python3
"""Phase 1b closure: validate manifest, build corpus JSONL, QA report, SQLite ingest.

Run from repository root. Uses the same defaults as ``ird_manifest_build_corpus.py``.

Example::

  python scripts/ird_phase1b_finalize.py --manifest data/raw/ird/source_manifest.csv \\
    --extract-tables --skip-missing
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent

if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ird_corpus_lib import read_manifest_csv  # noqa: E402


def validate_manifest(manifest: Path, *, require_tier_a_file: bool) -> list[str]:
    """Return validation warnings (empty if OK)."""
    warnings: list[str] = []
    rows = read_manifest_csv(manifest)
    if not rows:
        warnings.append("manifest has no data rows")
        return warnings

    required = {"source_doc_id", "tier"}
    header = set(rows[0].keys())
    missing_cols = required - header
    if missing_cols:
        warnings.append(f"manifest CSV missing columns: {sorted(missing_cols)}")

    tier_a_without_file = 0
    for i, row in enumerate(rows, start=2):
        sid = (row.get("source_doc_id") or "").strip()
        if not sid:
            warnings.append(f"row {i}: empty source_doc_id")
            continue
        tier = (row.get("tier") or "").strip().upper()
        fn = (row.get("file_name") or "").strip()
        url = (row.get("source_url") or "").strip()
        if tier == "A" and not fn and not url:
            tier_a_without_file += 1
    if require_tier_a_file and tier_a_without_file:
        warnings.append(
            f"{tier_a_without_file} Tier A row(s) have neither file_name nor source_url"
        )
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1b finalize pipeline")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--files-root",
        type=Path,
        default=Path("data/raw/ird/downloads"),
    )
    parser.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=Path("data/processed/ird/corpus_v1.jsonl"),
    )
    parser.add_argument(
        "--sqlite-db",
        type=Path,
        default=Path("data/processed/ird/corpus_v1.sqlite"),
    )
    parser.add_argument(
        "--qa-out",
        type=Path,
        default=Path("data/processed/ird/extraction_qa_report.md"),
    )
    parser.add_argument("--extract-tables", action="store_true")
    parser.add_argument("--fetch-html-urls", action="store_true")
    parser.add_argument("--html-split-headings", action="store_true")
    parser.add_argument("--tier", type=str, default="")
    parser.add_argument("--skip-missing", action="store_true")
    parser.add_argument("--no-pdf-outline", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--skip-qa", action="store_true")
    parser.add_argument("--skip-sqlite", action="store_true")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable for subprocess steps",
    )
    args = parser.parse_args()

    if not args.skip_validate:
        warns = validate_manifest(args.manifest, require_tier_a_file=True)
        for w in warns:
            print(f"validate: {w}")
        if any("missing columns" in x or "no data rows" in x for x in warns):
            raise SystemExit("manifest validation failed")

    build_cmd = [
        args.python,
        str(_REPO_ROOT / "scripts" / "ird_manifest_build_corpus.py"),
        "--manifest",
        str(args.manifest),
        "--files-root",
        str(args.files_root),
        "--corpus-jsonl",
        str(args.corpus_jsonl),
        "--chunk-chars",
        "1200",
        "--chunk-overlap",
        "150",
    ]
    if args.extract_tables:
        build_cmd.append("--extract-tables")
    if args.fetch_html_urls:
        build_cmd.append("--fetch-html-urls")
    if args.html_split_headings:
        build_cmd.append("--html-split-headings")
    if args.tier:
        build_cmd.extend(["--tier", args.tier])
    if args.skip_missing:
        build_cmd.append("--skip-missing")
    if args.no_pdf_outline:
        build_cmd.append("--no-pdf-outline")

    if not args.skip_build:
        subprocess.check_call(build_cmd, cwd=_REPO_ROOT)

    if not args.skip_qa:
        if not args.corpus_jsonl.is_file():
            print("skip QA: corpus JSONL not found")
        else:
            subprocess.check_call(
                [
                    args.python,
                    str(_REPO_ROOT / "scripts" / "ird_extraction_qa_report.py"),
                    "--corpus-jsonl",
                    str(args.corpus_jsonl),
                    "--out",
                    str(args.qa_out),
                ],
                cwd=_REPO_ROOT,
            )

    if not args.skip_sqlite:
        if not args.corpus_jsonl.is_file():
            print("skip SQLite: corpus JSONL not found")
        else:
            subprocess.check_call(
                [
                    args.python,
                    str(_REPO_ROOT / "scripts" / "ird_corpus_sqlite.py"),
                    "ingest",
                    "--corpus-jsonl",
                    str(args.corpus_jsonl),
                    "--db",
                    str(args.sqlite_db),
                ],
                cwd=_REPO_ROOT,
            )

    print("phase1b_finalize: complete")


if __name__ == "__main__":
    main()
