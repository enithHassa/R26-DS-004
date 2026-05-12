#!/usr/bin/env python3
"""Build corpus_v1 JSONL from a filled source manifest CSV (Phase 1b batch).

Each manifest row should include ``source_doc_id`` and either ``file_name`` (under
``--files-root``) or ``source_url`` for HTML when ``--fetch-html-urls`` is set.

PDF rows use the same extraction path as ``extract_ir_pdf_text.py`` (optional pdfplumber tables).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from extract_ir_pdf_text import (  # noqa: E402
    extract_pdf_pages,
    extract_pdf_tables_by_page,
)
from ird_pdf_outline import flatten_pdf_outline, outline_breadcrumb_map  # noqa: E402
from ird_corpus_lib import (  # noqa: E402
    CORPUS_VERSION,
    emit_pages_to_jsonl,
    normalize_doc_meta,
    read_manifest_csv,
)
from ird_extract_html import fetch_html, load_pages_from_html  # noqa: E402
from pypdf import PdfReader  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Manifest-driven IRD corpus_v1 build")
    parser.add_argument("--manifest", type=Path, required=True, help="Filled manifest CSV")
    parser.add_argument(
        "--files-root",
        type=Path,
        default=Path("data/raw/ird/downloads"),
        help="Root for manifest file_name paths",
    )
    parser.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=Path("data/processed/ird/corpus_v1.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument("--chunk-chars", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument(
        "--extract-tables",
        action="store_true",
        help="PDF: add pdfplumber table chunks",
    )
    parser.add_argument(
        "--fetch-html-urls",
        action="store_true",
        help="HTML: fetch source_url when file is missing or not local",
    )
    parser.add_argument(
        "--html-split-headings",
        action="store_true",
        help="HTML: split on h2/h3 into pseudo-pages",
    )
    parser.add_argument("--http-timeout", type=float, default=30.0)
    parser.add_argument(
        "--tier",
        type=str,
        default="",
        help="If set, only rows with this tier (e.g. A)",
    )
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Skip rows whose PDF file is missing instead of failing",
    )
    parser.add_argument(
        "--no-pdf-outline",
        action="store_true",
        help="PDF: do not attach pdf_outline_breadcrumb from bookmarks",
    )
    args = parser.parse_args()

    rows = read_manifest_csv(args.manifest)
    args.corpus_jsonl.parent.mkdir(parents=True, exist_ok=True)

    first_out = True
    tier_filter = args.tier.strip().upper()

    for row in rows:
        sid = (row.get("source_doc_id") or "").strip()
        if not sid:
            continue
        if tier_filter and (row.get("tier") or "").strip().upper() != tier_filter:
            continue

        doc_meta = normalize_doc_meta(row)
        fn = (row.get("file_name") or "").strip()
        url = (row.get("source_url") or "").strip()
        path = Path(fn) if fn and (Path(fn).is_absolute() or "/" in fn or "\\" in fn) else None
        if path is None and fn:
            path = args.files_root / fn

        mode = "w" if first_out else "a"
        wrote = False

        if path and path.is_file():
            ext = path.suffix.lower()
            if ext == ".pdf":
                pages = extract_pdf_pages(path)
                outline_map: dict[int, list[str] | None] | None = None
                if not args.no_pdf_outline:
                    reader = PdfReader(str(path))
                    flat = flatten_pdf_outline(reader)
                    if flat:
                        outline_map = outline_breadcrumb_map(flat, [p for p, _ in pages])
                tables_by_page = None
                table_method = None
                if args.extract_tables:
                    tables_by_page = extract_pdf_tables_by_page(path)
                    if tables_by_page is None:
                        print(f"warning: pdfplumber missing; skipping tables for {path.name}")
                    elif tables_by_page:
                        table_method = "pdfplumber"
                with args.corpus_jsonl.open(mode, encoding="utf-8") as out:
                    emit_pages_to_jsonl(
                        pages=pages,
                        source_doc_id=sid,
                        doc_meta=doc_meta,
                        out_fp=out,
                        max_chars=args.chunk_chars,
                        overlap=args.chunk_overlap,
                        tables_by_page=tables_by_page,
                        table_method=table_method,
                        outline_breadcrumb_by_page=outline_map,
                    )
                wrote = True
                print(f"pdf: {sid} <- {path}")
            elif ext in {".html", ".htm", ".aspx"}:
                html = path.read_text(encoding="utf-8", errors="replace")
                pages = load_pages_from_html(html, split_headings=args.html_split_headings)
                with args.corpus_jsonl.open(mode, encoding="utf-8") as out:
                    emit_pages_to_jsonl(
                        pages=pages,
                        source_doc_id=sid,
                        doc_meta=doc_meta,
                        out_fp=out,
                        max_chars=args.chunk_chars,
                        overlap=args.chunk_overlap,
                        tables_by_page=None,
                        table_method=None,
                    )
                wrote = True
                print(f"html: {sid} <- {path}")
            else:
                print(f"skip (unsupported ext {ext}): {sid} {path}")
        elif args.fetch_html_urls and url:
            try:
                html = fetch_html(url, timeout=args.http_timeout)
            except Exception as exc:  # noqa: BLE001
                print(f"skip (fetch failed {sid}): {exc}")
                continue
            pages = load_pages_from_html(html, split_headings=args.html_split_headings)
            with args.corpus_jsonl.open(mode, encoding="utf-8") as out:
                emit_pages_to_jsonl(
                    pages=pages,
                    source_doc_id=sid,
                    doc_meta=doc_meta,
                    out_fp=out,
                    max_chars=args.chunk_chars,
                    overlap=args.chunk_overlap,
                    tables_by_page=None,
                    table_method=None,
                )
            wrote = True
            print(f"html(fetch): {sid} <- {url}")
        else:
            if fn and not (path and path.is_file()):
                msg = f"missing file for {sid}: {path}"
                if args.skip_missing:
                    print(f"skip: {msg}")
                else:
                    raise SystemExit(msg)
            elif not url:
                print(f"skip (no file/url): {sid}")

        if wrote:
            first_out = False

    if first_out:
        print("warning: no chunks were written (check manifest paths, --files-root, or --fetch-html-urls)")
    else:
        print(f"done -> {args.corpus_jsonl} ({CORPUS_VERSION})")


if __name__ == "__main__":
    main()
