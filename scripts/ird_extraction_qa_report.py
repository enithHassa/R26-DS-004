#!/usr/bin/env python3
"""Generate an extraction QA markdown report from corpus_v1 JSONL (Phase 1b).

Counts chunks, flags likely extraction errors, short text, and table coverage.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Corpus JSONL QA report")
    parser.add_argument("--corpus-jsonl", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/processed/ird/extraction_qa_report.md"))
    args = parser.parse_args()

    stats: dict[str, object] = {
        "chunks": 0,
        "text_chunks": 0,
        "table_chunks": 0,
        "by_source": Counter(),
        "by_tier": Counter(),
        "by_instrument": Counter(),
        "extract_errors": 0,
        "empty_text": 0,
        "short_text": 0,
        "section_ref_hits": 0,
        "table_candidate_hints": 0,
        "pdf_outline_breadcrumb_hits": 0,
        "lengths": [],
        "pages_seen": Counter(),
    }

    for line in args.corpus_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        o = json.loads(line)
        stats["chunks"] = int(stats["chunks"]) + 1  # type: ignore[assignment]
        kind = o.get("content_kind") or "text"
        if kind == "table":
            stats["table_chunks"] = int(stats["table_chunks"]) + 1  # type: ignore[assignment]
        else:
            stats["text_chunks"] = int(stats["text_chunks"]) + 1  # type: ignore[assignment]

        sid = o.get("source_doc_id") or "unknown"
        stats["by_source"][sid] += 1  # type: ignore[index]
        tier = o.get("tier") or "unknown"
        stats["by_tier"][str(tier)] += 1  # type: ignore[index]
        inst = o.get("instrument_type") or "unknown"
        stats["by_instrument"][str(inst)] += 1  # type: ignore[index]

        text = o.get("text") or ""
        if "<!-- extract error:" in text or "extract error:" in text:
            stats["extract_errors"] = int(stats["extract_errors"]) + 1  # type: ignore[assignment]
        if not str(text).strip():
            stats["empty_text"] = int(stats["empty_text"]) + 1  # type: ignore[assignment]
        elif len(text) < 50:
            stats["short_text"] = int(stats["short_text"]) + 1  # type: ignore[assignment]

        if o.get("section_ref"):
            stats["section_ref_hits"] = int(stats["section_ref_hits"]) + 1  # type: ignore[assignment]
        if o.get("layout_hint") == "table_candidate":
            stats["table_candidate_hints"] = int(stats["table_candidate_hints"]) + 1  # type: ignore[assignment]

        bc = o.get("pdf_outline_breadcrumb")
        if isinstance(bc, list) and len(bc) > 0:
            stats["pdf_outline_breadcrumb_hits"] = int(stats["pdf_outline_breadcrumb_hits"]) + 1  # type: ignore[assignment]

        stats["lengths"].append(len(text))  # type: ignore[union-attr]
        page = o.get("page")
        if isinstance(page, int):
            stats["pages_seen"][f"{sid}:p{page:04d}"] += 1  # type: ignore[index]

    lengths: list[int] = stats["lengths"]  # type: ignore[assignment]
    len_summary = ""
    if lengths:
        len_summary = (
            f"- char length: min={min(lengths)} max={max(lengths)} "
            f"mean={statistics.mean(lengths):.1f} "
            f"median={statistics.median(lengths):.1f}\n"
        )

    by_src = stats["by_source"]  # type: ignore[assignment]
    by_tier = stats["by_tier"]  # type: ignore[assignment]
    by_inst = stats["by_instrument"]  # type: ignore[assignment]

    lines_out = [
        "# IRD corpus extraction QA report\n",
        f"- generated_at_utc: {now_utc()}\n",
        f"- corpus_jsonl: `{args.corpus_jsonl.as_posix()}`\n",
        "\n## Summary\n",
        f"- total chunks: {stats['chunks']}\n",
        f"- text chunks: {stats['text_chunks']}\n",
        f"- table chunks (pdfplumber): {stats['table_chunks']}\n",
        f"- chunks with extract error marker: {stats['extract_errors']}\n",
        f"- empty text chunks: {stats['empty_text']}\n",
        f"- very short text (<50 chars): {stats['short_text']}\n",
        f"- chunks with heuristic section_ref: {stats['section_ref_hits']}\n",
        f"- text chunks flagged table_candidate (layout hint): {stats['table_candidate_hints']}\n",
        f"- chunks with pdf_outline_breadcrumb: {stats['pdf_outline_breadcrumb_hits']}\n",
        len_summary,
        "\n## By source_doc_id\n",
    ]
    for k, v in sorted(by_src.items(), key=lambda kv: (-kv[1], kv[0])):
        lines_out.append(f"- {k}: {v}\n")

    lines_out.append("\n## By tier\n")
    for k, v in sorted(by_tier.items(), key=lambda kv: (-kv[1], kv[0])):
        lines_out.append(f"- {k}: {v}\n")

    lines_out.append("\n## By instrument_type\n")
    for k, v in sorted(by_inst.items(), key=lambda kv: (-kv[1], kv[0])):
        lines_out.append(f"- {k}: {v}\n")

    lines_out.append("\n## Manual follow-ups (checklist)\n")
    lines_out.append(
        "- [ ] Spot-check pages with `extract error` in chunk text against source PDF.\n"
    )
    lines_out.append(
        "- [ ] Verify table chunks against PDF for merged cells / wrong columns.\n"
    )
    lines_out.append(
        "- [ ] Confirm `section_ref` regex hits match real provisions (no false positives).\n"
    )
    lines_out.append(
        "- [ ] Fill manifest dates/version_label for any row still marked `tbd`.\n"
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(lines_out), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
