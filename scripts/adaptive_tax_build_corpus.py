#!/usr/bin/env python3
"""Build adaptive-tax corpus_v1.jsonl from models/adaptive-tax/corpus_manifest.json.

Uses scripts/extract_ir_pdf_text.py per document (first truncates, rest append).
Defaults to section-aware provision-preserving chunking.

Example (from repo root)::

  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_build_corpus.py
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_build_corpus.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_EXTRACT = _SCRIPTS / "extract_ir_pdf_text.py"
_DEFAULT_MANIFEST = _REPO / "models" / "adaptive-tax" / "corpus_manifest.json"

# Forward these manifest keys into extract --doc-meta-json
_META_KEYS = (
    "tier",
    "instrument_type",
    "doc_type",
    "title",
    "language",
    "authority_weight",
    "is_draft",
    "publication_date",
    "effective_start_date",
    "effective_end_date",
    "version_label",
    "source_url",
    "applicable_assessment_years",
)


def _load_manifest(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("documents"), list):
        raise SystemExit(f"invalid manifest (need documents[]): {path}")
    return raw


def _doc_meta_payload(doc: dict) -> dict:
    out: dict = {}
    for key in _META_KEYS:
        if key in doc and doc[key] is not None and doc[key] != "":
            out[key] = doc[key]
    return out


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
    p.add_argument(
        "--chunk-chars",
        type=int,
        default=1200,
        help="MAX_CHUNK_CHARS — only mid-split provisions larger than this",
    )
    p.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Overlap when a provision must be split",
    )
    p.add_argument(
        "--section-aware",
        action="store_true",
        default=True,
        help="Provision-preserving chunking (default on)",
    )
    p.add_argument(
        "--no-section-aware",
        action="store_true",
        help="Legacy page-window chunking",
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

    section_aware = not bool(args.no_section_aware)

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
        # Phase 6.0 — Guide / Master stay on disk but are not corpus SoT for tax evidence.
        if doc.get("usable_for_executable_extract") is False or doc.get("usable_for_explain") is False:
            if source_doc_id in {"ird-guide-ira", "ird-calc-ontology-v5"}:
                print(f"skip non-executable/explain source: {source_doc_id}")
                continue

        pdf_path = pdf_root / file_name
        if not pdf_path.is_file():
            print(f"MISSING PDF: {pdf_path}", file=sys.stderr)
            return 2

        meta = _doc_meta_payload(doc)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as tmp:
            json.dump(meta, tmp)
            meta_path = Path(tmp.name)

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
            "--doc-meta-json",
            str(meta_path),
            "--chunk-chars",
            str(args.chunk_chars),
            "--chunk-overlap",
            str(args.chunk_overlap),
        ]
        if section_aware:
            cmd.append("--section-aware")
        else:
            cmd.append("--no-section-aware")
        if i > 0:
            cmd.append("--corpus-append")

        print(
            f"[{i + 1}/{len(docs)}] {source_doc_id} <- {file_name} "
            f"(section_aware={section_aware}, max_chars={args.chunk_chars})"
        )
        if args.dry_run:
            print(" ", " ".join(cmd))
            meta_path.unlink(missing_ok=True)
            continue

        try:
            proc = subprocess.run(cmd, cwd=str(_REPO), check=False)
        finally:
            meta_path.unlink(missing_ok=True)

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
