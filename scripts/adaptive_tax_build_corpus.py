#!/usr/bin/env python3
"""Build adaptive-tax corpus_v1.jsonl from models/adaptive-tax/corpus_manifest.json.

Uses scripts/extract_ir_pdf_text.py per document (first truncates, rest append).

Example (from repo root)::

  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_build_corpus.py
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_build_corpus.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_EXTRACT = _SCRIPTS / "extract_ir_pdf_text.py"
_DEFAULT_MANIFEST = _REPO / "models" / "adaptive-tax" / "corpus_manifest.json"


def _load_manifest(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("documents"), list):
        raise SystemExit(f"invalid manifest (need documents[]): {path}")
    return raw


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    p.add_argument(
        "--pdf-root",
        type=Path,
        default=None,
        help="Override manifest pdf_root (default: relative to repo)",
    )
    p.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=None,
        help="Override manifest corpus_jsonl path",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Override manifest text_out_dir",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="Process only first N docs")
    args = p.parse_args()

    if not args.manifest.is_file():
        print(f"manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    if not _EXTRACT.is_file():
        print(f"extract script not found: {_EXTRACT}", file=sys.stderr)
        return 2

    manifest = _load_manifest(args.manifest)
    pdf_root = args.pdf_root or (_REPO / str(manifest.get("pdf_root", "data/raw/adaptive-tax")))
    corpus_jsonl = args.corpus_jsonl or (
        _REPO / str(manifest.get("corpus_jsonl", "data/processed/adaptive-tax/corpus_v1.jsonl"))
    )
    out_dir = args.out_dir or (
        _REPO / str(manifest.get("text_out_dir", "data/processed/adaptive-tax/text"))
    )

    docs = list(manifest["documents"])
    if args.limit is not None:
        docs = docs[: max(0, args.limit)]

    py = sys.executable
    total_chunks = 0
    for i, doc in enumerate(docs):
        if not isinstance(doc, dict):
            print(f"skip invalid document row {i}", file=sys.stderr)
            continue
        file_name = str(doc.get("file_name") or "").strip()
        source_doc_id = str(doc.get("source_doc_id") or "").strip()
        if not file_name or not source_doc_id:
            print(f"skip row {i}: missing file_name/source_doc_id", file=sys.stderr)
            continue

        pdf_path = pdf_root / file_name
        if not pdf_path.is_file():
            print(f"MISSING PDF: {pdf_path}", file=sys.stderr)
            return 2

        cmd = [
            py,
            str(_EXTRACT),
            str(pdf_path),
            "--out-dir",
            str(out_dir),
            "--source-doc-id",
            source_doc_id,
            "--corpus-jsonl",
            str(corpus_jsonl),
        ]
        if i > 0:
            cmd.append("--corpus-append")

        for flag, key in (
            ("--tier", "tier"),
            ("--instrument-type", "instrument_type"),
            ("--doc-type", "doc_type"),
            ("--title", "title"),
        ):
            val = doc.get(key)
            if val is not None and str(val).strip():
                cmd.extend([flag, str(val)])

        print(f"[{i + 1}/{len(docs)}] {source_doc_id} <- {file_name}")
        if args.dry_run:
            print(" ", " ".join(cmd))
            continue

        proc = subprocess.run(cmd, cwd=str(_REPO), check=False)
        if proc.returncode != 0:
            print(f"extract failed for {source_doc_id} (exit {proc.returncode})", file=sys.stderr)
            return proc.returncode or 1

    if args.dry_run:
        print(f"dry-run OK: {len(docs)} document(s)")
        return 0

    if corpus_jsonl.is_file():
        with corpus_jsonl.open(encoding="utf-8") as f:
            total_chunks = sum(1 for line in f if line.strip())
        print(f"wrote {corpus_jsonl} ({total_chunks} chunk rows)")
    else:
        print(f"expected corpus missing: {corpus_jsonl}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
