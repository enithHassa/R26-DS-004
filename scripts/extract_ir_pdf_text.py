#!/usr/bin/env python3
"""Extract plain text from IR Act PDFs for review / LLM-assisted YAML drafting.

Depends on pypdf (see backend/requirements.txt). Optional table extraction uses pdfplumber.

  python scripts/extract_ir_pdf_text.py path/to/act.pdf
  python scripts/extract_ir_pdf_text.py --out-dir research/ir_extracts path1.pdf path2.pdf

Corpus v1 (Phase 1b): chunk pages and emit JSONL with manifest-aligned metadata::

  python scripts/extract_ir_pdf_text.py act.pdf --out-dir data/processed/ird/text \\
    --source-doc-id ird-ira-2017-base \\
    --corpus-jsonl data/processed/ird/corpus_v1.jsonl \\
    --extract-tables

Chunk IDs: ``{source_doc_id}::p{page:04d}::c{idx:04d}`` (text) and ``::t{idx:04d}`` (tables).

Text is lossy vs layout; always verify against the PDF before citing in research.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from pypdf import PdfReader

from ird_corpus_lib import CORPUS_VERSION, emit_pages_to_jsonl, normalize_doc_meta
from ird_pdf_outline import flatten_pdf_outline, outline_breadcrumb_map


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    """Return (1-based page number, raw page text) for each PDF page."""
    reader = PdfReader(str(path))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 — best-effort per page
            t = f"<!-- extract error: {exc} -->"
        pages.append((i + 1, t))
    return pages


def extract_pdf_text(path: Path) -> str:
    parts: list[str] = []
    for page_num, t in extract_pdf_pages(path):
        parts.append(f"\n\n--- Page {page_num} ---\n\n{t}")
    return "".join(parts).strip()


def extract_pdf_tables_by_page(path: Path) -> dict[int, list[str]] | None:
    """Return page -> list of TSV table blobs via pdfplumber; None if unavailable."""
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError:
        return None

    out: dict[int, list[str]] = {}
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            tables = page.extract_tables() or []
            rows_out: list[str] = []
            for table in tables:
                if not table:
                    continue
                lines: list[str] = []
                for row in table:
                    cells = [
                        ""
                        if c is None
                        else str(c).strip().replace("\n", " ").replace("\t", " ")
                        for c in row
                    ]
                    lines.append("\t".join(cells))
                blob = "\n".join(lines).strip()
                if blob:
                    rows_out.append(blob)
            if rows_out:
                out[page_num] = rows_out
    return out


def _load_doc_meta(path: Path | None, overrides: dict[str, str]) -> dict[str, object]:
    base: dict[str, object] = {}
    if path and path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SystemExit("--doc-meta-json must contain a JSON object")
        base.update(raw)
    base.update({k: v for k, v in overrides.items() if v})
    # normalize_doc_meta expects str values
    str_row = {k: str(v) if v is not None else "" for k, v in base.items()}
    return normalize_doc_meta(str_row)


def _resolve_source_doc_ids(
    pdfs: list[Path], source_doc_id: str | None, source_doc_ids: str | None
) -> list[str]:
    if len(pdfs) == 1:
        if not source_doc_id:
            raise SystemExit("--source-doc-id is required when using --corpus-jsonl with a single PDF")
        return [source_doc_id]
    if not source_doc_ids:
        raise SystemExit("--source-doc-ids is required when using --corpus-jsonl with multiple PDFs")
    ids = [x.strip() for x in source_doc_ids.split(",") if x.strip()]
    if len(ids) != len(pdfs):
        raise SystemExit(f"--source-doc-ids must list exactly {len(pdfs)} ids (got {len(ids)})")
    return ids


def emit_corpus_jsonl_for_pdf(
    *,
    pdf_path: Path,
    source_doc_id: str,
    corpus_jsonl: Path,
    max_chars: int,
    overlap: int,
    file_mode: str,
    doc_meta: dict[str, object],
    extract_tables: bool,
    use_pdf_outline: bool = True,
) -> tuple[int, int]:
    pages = extract_pdf_pages(pdf_path)
    corpus_jsonl.parent.mkdir(parents=True, exist_ok=True)

    outline_map: dict[int, list[str] | None] | None = None
    if use_pdf_outline:
        reader = PdfReader(str(pdf_path))
        flat = flatten_pdf_outline(reader)
        if flat:
            outline_map = outline_breadcrumb_map(flat, [p for p, _ in pages])

    tables_by_page: dict[int, list[str]] | None = None
    table_method: str | None = None
    if extract_tables:
        tables_by_page = extract_pdf_tables_by_page(pdf_path)
        if tables_by_page is None:
            print("warning: pdfplumber not installed; skipping table extraction")
        elif not tables_by_page:
            table_method = None
        else:
            table_method = "pdfplumber"

    with corpus_jsonl.open(file_mode, encoding="utf-8") as out:
        return emit_pages_to_jsonl(
            pages=pages,
            source_doc_id=source_doc_id,
            doc_meta=doc_meta,
            out_fp=out,
            max_chars=max_chars,
            overlap=overlap,
            tables_by_page=tables_by_page,
            table_method=table_method,
            outline_breadcrumb_by_page=outline_map,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from PDF(s) using pypdf.")
    parser.add_argument("pdfs", nargs="+", type=Path, help="PDF file paths")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write <stem>.txt alongside; default: print to stdout for a single file",
    )
    parser.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=None,
        help=f"Append/write chunked corpus as JSONL ({CORPUS_VERSION} schema)",
    )
    parser.add_argument("--source-doc-id", type=str, default=None, help="Manifest source_doc_id (single PDF)")
    parser.add_argument(
        "--source-doc-ids",
        type=str,
        default=None,
        help="Comma-separated source_doc_ids, one per PDF (multiple PDFs)",
    )
    parser.add_argument(
        "--doc-meta-json",
        type=Path,
        default=None,
        help="JSON object with manifest-aligned fields (tier, instrument_type, dates, ...)",
    )
    parser.add_argument("--tier", type=str, default="", help="Shortcut: tier A/B/C for doc-meta")
    parser.add_argument("--instrument-type", type=str, default="", dest="instrument_type")
    parser.add_argument("--doc-type", type=str, default="", dest="doc_type")
    parser.add_argument("--source-url", type=str, default="", dest="source_url")
    parser.add_argument("--title", type=str, default="", help="Document title for metadata")
    parser.add_argument("--chunk-chars", type=int, default=1200, help="Max characters per chunk")
    parser.add_argument("--chunk-overlap", type=int, default=150, help="Overlap between chunks")
    parser.add_argument(
        "--corpus-append",
        action="store_true",
        help="Append to corpus JSONL instead of truncating first",
    )
    parser.add_argument(
        "--extract-tables",
        action="store_true",
        help="Extract PDF tables via pdfplumber as additional chunks (::t#### ids)",
    )
    parser.add_argument(
        "--no-pdf-outline",
        action="store_true",
        help="Do not attach pdf_outline_breadcrumb from PDF bookmarks",
    )
    args = parser.parse_args()

    doc_ids: list[str] | None = None
    if args.corpus_jsonl:
        doc_ids = _resolve_source_doc_ids(args.pdfs, args.source_doc_id, args.source_doc_ids)

    meta_overrides = {
        "tier": args.tier,
        "instrument_type": args.instrument_type,
        "doc_type": args.doc_type,
        "source_url": args.source_url,
        "title": args.title,
    }

    for i, pdf in enumerate(args.pdfs):
        if not pdf.is_file():
            raise SystemExit(f"Not a file: {pdf}")
        text = extract_pdf_text(pdf)
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            out = args.out_dir / f"{pdf.stem}.txt"
            out.write_text(text, encoding="utf-8")
            print(out)
        elif len(args.pdfs) == 1 and not args.corpus_jsonl:
            print(text)
        elif len(args.pdfs) > 1 and not args.out_dir and not args.corpus_jsonl:
            raise SystemExit("With multiple PDFs, pass --out-dir and/or --corpus-jsonl")

        if args.corpus_jsonl and doc_ids:
            doc_meta = _load_doc_meta(args.doc_meta_json, meta_overrides)
            first_file = i == 0 and not args.corpus_append
            mode = "w" if first_file else "a"
            tn, tabn = emit_corpus_jsonl_for_pdf(
                pdf_path=pdf,
                source_doc_id=doc_ids[i],
                corpus_jsonl=args.corpus_jsonl,
                max_chars=args.chunk_chars,
                overlap=args.chunk_overlap,
                file_mode=mode,
                doc_meta=doc_meta,
                extract_tables=args.extract_tables,
                use_pdf_outline=not args.no_pdf_outline,
            )
            print(
                f"corpus chunks for {pdf.name}: text={tn} tables={tabn} -> {args.corpus_jsonl}"
            )


if __name__ == "__main__":
    main()
