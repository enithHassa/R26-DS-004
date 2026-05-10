#!/usr/bin/env python3
"""Extract plain text from IR Act PDFs for review / LLM-assisted YAML drafting.

Depends on pypdf (see backend/requirements.txt). Usage:

  python scripts/extract_ir_pdf_text.py path/to/act.pdf
  python scripts/extract_ir_pdf_text.py --out-dir research/ir_extracts path1.pdf path2.pdf

Text is lossy vs layout; always verify against the PDF before citing in research.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 — best-effort per page
            parts.append(f"\n\n<!-- page {i + 1}: extract error: {exc} -->\n\n")
            continue
        parts.append(f"\n\n--- Page {i + 1} ---\n\n{t}")
    return "".join(parts).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract text from PDF(s) using pypdf.")
    parser.add_argument("pdfs", nargs="+", type=Path, help="PDF file paths")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write <stem>.txt alongside; default: print to stdout for a single file",
    )
    args = parser.parse_args()

    for pdf in args.pdfs:
        if not pdf.is_file():
            raise SystemExit(f"Not a file: {pdf}")
        text = extract_pdf_text(pdf)
        if args.out_dir:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            out = args.out_dir / f"{pdf.stem}.txt"
            out.write_text(text, encoding="utf-8")
            print(out)
        elif len(args.pdfs) == 1:
            print(text)
        else:
            raise SystemExit("With multiple PDFs, pass --out-dir")


if __name__ == "__main__":
    main()
