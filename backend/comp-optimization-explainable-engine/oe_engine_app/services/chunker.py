"""Section-aware dual-channel chunking (text_stream + table_render)."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[4] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from ird_corpus_lib import emit_pages_to_jsonl  # noqa: E402


def build_chunks(
    *,
    pages: list[tuple[int, str]],
    source_doc_id: str,
    title: str,
    tier: str,
    tables_by_page: dict[int, list[str]] | None,
    table_method: str | None,
    max_chars: int,
    overlap: int,
) -> list[dict[str, Any]]:
    buf = io.StringIO()
    emit_pages_to_jsonl(
        pages=pages,
        source_doc_id=source_doc_id,
        doc_meta={"title": title, "tier": tier, "doc_type": "pdf", "language": "en"},
        out_fp=buf,
        max_chars=max_chars,
        overlap=overlap,
        tables_by_page=tables_by_page or None,
        table_method=table_method,
        section_aware=True,
    )
    rows: list[dict[str, Any]] = []
    for line in buf.getvalue().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        kind = rec.get("content_kind") or "text"
        rec["channel"] = "table_render" if kind == "table" else "text_stream"
        rows.append(rec)
    return rows
