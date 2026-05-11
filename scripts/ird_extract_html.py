#!/usr/bin/env python3
"""Fetch or read IRD HTML (.aspx, .html) and emit corpus_v1 JSONL.

HTML is treated as a single logical document (page=1) unless --split-headings splits on h2/h3.

  python scripts/ird_extract_html.py --url "https://..." --source-doc-id ird-hub-income-tax \\
    --corpus-jsonl data/processed/ird/corpus_v1.jsonl --corpus-append

  python scripts/ird_extract_html.py --html-file page.aspx --source-doc-id ird-local-summary \\
    --doc-meta-json meta.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import httpx

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ird_corpus_lib import CORPUS_VERSION, emit_pages_to_jsonl, normalize_doc_meta


class _HTMLToText(HTMLParser):
    """Best-effort visible text extraction (no external HTML deps)."""

    _BLOCK = frozenset({"br", "p", "div", "tr", "table", "h1", "h2", "h3", "h4", "li"})

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript"}:
            self._skip += 1
        elif t in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1
        elif t in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    parser.feed(html)
    return parser.text()


def fetch_html(url: str, *, timeout: float) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def split_html_by_headings(html: str) -> list[tuple[int, str]]:
    """Split rough 'pages' on <h2> / <h3> for long hub pages."""
    parts = re.split(r"(?i)(?=<h[23]\b)", html)
    out: list[tuple[int, str]] = []
    for i, chunk in enumerate(parts):
        if not chunk.strip():
            continue
        t = html_to_text(chunk)
        if t:
            out.append((i + 1, t))
    if not out:
        return [(1, html_to_text(html))]
    if len(out) == 1:
        return [(1, out[0][1])]
    return out


def load_pages_from_html(html: str, *, split_headings: bool) -> list[tuple[int, str]]:
    if split_headings:
        return split_html_by_headings(html)
    return [(1, html_to_text(html))]


def _load_doc_meta(path: Path | None, overrides: dict[str, str]) -> dict[str, object]:
    base: dict[str, object] = {}
    if path and path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise SystemExit("--doc-meta-json must contain a JSON object")
        base.update(raw)
    base.update({k: v for k, v in overrides.items() if v})
    str_row = {k: str(v) if v is not None else "" for k, v in base.items()}
    return normalize_doc_meta(str_row)


def main() -> None:
    parser = argparse.ArgumentParser(description="IRD HTML to corpus_v1 JSONL")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", type=str, help="Fetch HTML from URL")
    src.add_argument("--html-file", type=Path, help="Read local HTML / ASPX file")
    parser.add_argument("--source-doc-id", type=str, required=True)
    parser.add_argument("--corpus-jsonl", type=Path, required=True)
    parser.add_argument("--doc-meta-json", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--chunk-chars", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--corpus-append", action="store_true")
    parser.add_argument(
        "--split-headings",
        action="store_true",
        help="Split on h2/h3 into pseudo-pages for chunking",
    )
    parser.add_argument("--title", type=str, default="")
    parser.add_argument("--tier", type=str, default="")
    parser.add_argument("--source-url", type=str, default="", dest="source_url")
    args = parser.parse_args()

    if args.url:
        html = fetch_html(args.url, timeout=args.timeout)
        meta_url = args.url
    else:
        assert args.html_file is not None
        html = args.html_file.read_text(encoding="utf-8", errors="replace")
        meta_url = ""

    pages = load_pages_from_html(html, split_headings=args.split_headings)
    doc_meta = _load_doc_meta(
        args.doc_meta_json,
        {
            "tier": args.tier,
            "instrument_type": "html_summary",
            "doc_type": "html",
            "source_url": args.source_url or meta_url,
            "title": args.title,
        },
    )

    args.corpus_jsonl.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.corpus_append else "w"
    with args.corpus_jsonl.open(mode, encoding="utf-8") as out:
        tn, tabn = emit_pages_to_jsonl(
            pages=pages,
            source_doc_id=args.source_doc_id,
            doc_meta=doc_meta,
            out_fp=out,
            max_chars=args.chunk_chars,
            overlap=args.chunk_overlap,
            tables_by_page=None,
            table_method=None,
        )
    print(f"HTML corpus: text={tn} tables={tabn} -> {args.corpus_jsonl} ({CORPUS_VERSION})")


if __name__ == "__main__":
    main()
