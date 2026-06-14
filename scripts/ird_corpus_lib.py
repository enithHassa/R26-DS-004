"""Shared corpus chunking, IDs, and JSONL records for IRD Phase 1b (corpus_v1)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, TextIO

CORPUS_VERSION = "corpus_v1"

# Heuristic refs for QA / graph linking (not a substitute for structured sectioning).
_SECTION_REGEXES: tuple[tuple[re.Pattern[str], str | None], ...] = (
    (re.compile(r"\b(?:Section|SECTION)\s+(\d+[A-Za-z]?)\b"), "Section {}"),
    (re.compile(r"\b(?:Article|ARTICLE)\s+(\d+[A-Za-z]?)\b"), "Article {}"),
    (re.compile(r"\b(?:Part|PART)\s+([IVXLC\d]+)\b"), "Part {}"),
    (re.compile(r"\b(?:Schedule|SCHEDULE)\s+([A-Za-z0-9]+)\b"), "Schedule {}"),
    (re.compile(r"\b(?:Second|Third|Fourth|Fifth)\s+Schedule\b", re.I), None),
)


def make_chunk_id_text(source_doc_id: str, page: int, chunk_index: int) -> str:
    """Text chunk: source + 1-based page + chunk index within page."""
    return f"{source_doc_id}::p{page:04d}::c{chunk_index:04d}"


def make_chunk_id_table(source_doc_id: str, page: int, table_index: int) -> str:
    """Table chunk from PDF table extraction (same page, separate id space)."""
    return f"{source_doc_id}::p{page:04d}::t{table_index:04d}"


def chunk_page_text(
    page_text: str,
    max_chars: int,
    overlap: int,
) -> list[tuple[int, int, str]]:
    """Split one page into overlapping windows; returns (char_start, char_end, text)."""
    if max_chars < 64:
        raise ValueError("max_chars should be at least 64 for sensible chunks")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be in [0, max_chars)")

    if not page_text.strip():
        return []

    chunks: list[tuple[int, int, str]] = []
    start = 0
    n = len(page_text)

    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            window = page_text[start:end]
            break_at = max(window.rfind("\n"), window.rfind(" "))
            if break_at > max_chars // 2:
                end = start + break_at + 1

        piece = page_text[start:end].strip()
        if piece:
            chunks.append((start, end, piece))

        if end >= n:
            break
        next_start = end - overlap
        start = next_start if next_start > start else end

    return chunks


def extract_section_refs(text: str, *, max_refs: int = 24) -> list[str] | None:
    """Extract likely statutory references from chunk text (heuristic)."""
    found: set[str] = set()
    for pattern, fmt in _SECTION_REGEXES:
        for m in pattern.finditer(text):
            if fmt is None:
                found.add(m.group(0).strip())
            else:
                found.add(fmt.format(m.group(1)).strip())
            if len(found) >= max_refs:
                return sorted(found)
    return sorted(found) if found else None


def table_like_heuristic(text: str) -> bool:
    """True if chunk looks like a dense numeric/tabular block (weak signal)."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 4:
        return False
    tab_or_multispace = sum(1 for ln in lines if "\t" in ln or "  " in ln or ln.count(",") >= 4)
    return tab_or_multispace >= len(lines) // 2


def normalize_doc_meta(row: dict[str, str]) -> dict[str, Any]:
    """Map manifest CSV row keys to corpus chunk metadata fields."""
    raw_draft = (row.get("is_draft") or "").strip().lower()
    is_draft = raw_draft in ("true", "1", "yes", "y")

    def _f(key: str) -> str:
        return (row.get(key) or "").strip()

    return {
        "tier": _f("tier") or None,
        "instrument_type": _f("instrument_type") or None,
        "doc_type": _f("doc_type") or None,
        "publication_date": _f("publication_date"),
        "effective_start_date": _f("effective_start_date"),
        "effective_end_date": _f("effective_end_date"),
        "version_label": _f("version_label"),
        "source_url": _f("source_url"),
        "title": _f("title"),
        "authority_weight": _f("authority_weight"),
        "is_draft": is_draft,
        "language": _f("language") or "en",
    }


def _base_meta_fields(doc_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "tier": doc_meta.get("tier"),
        "instrument_type": doc_meta.get("instrument_type"),
        "doc_type": doc_meta.get("doc_type"),
        "publication_date": doc_meta.get("publication_date") or "",
        "effective_start_date": doc_meta.get("effective_start_date") or "",
        "effective_end_date": doc_meta.get("effective_end_date") or "",
        "version_label": doc_meta.get("version_label") or "",
        "source_url": doc_meta.get("source_url") or "",
        "title": doc_meta.get("title") or "",
        "authority_weight": doc_meta.get("authority_weight") or "",
        "is_draft": doc_meta.get("is_draft", False),
        "language": doc_meta.get("language") or "en",
    }


def build_text_chunk_record(
    *,
    source_doc_id: str,
    page: int,
    chunk_index: int,
    page_char_start: int,
    page_char_end: int,
    text: str,
    doc_meta: dict[str, Any],
    content_kind: str = "text",
    table_extract_method: str | None = None,
    pdf_outline_breadcrumb: list[str] | None = None,
) -> dict[str, Any]:
    section_ref = extract_section_refs(text)
    rec: dict[str, Any] = {
        "chunk_id": make_chunk_id_text(source_doc_id, page, chunk_index),
        "source_doc_id": source_doc_id,
        "corpus_version": CORPUS_VERSION,
        "content_kind": content_kind,
        "page": page,
        "chunk_index": chunk_index,
        "page_char_start": page_char_start,
        "page_char_end": page_char_end,
        "section_ref": section_ref,
        "pdf_outline_breadcrumb": pdf_outline_breadcrumb,
        "text": text,
        **_base_meta_fields(doc_meta),
        "layout_hint": "table_candidate" if table_like_heuristic(text) else None,
    }
    if table_extract_method:
        rec["table_extract_method"] = table_extract_method
    return rec


def build_table_chunk_record(
    *,
    source_doc_id: str,
    page: int,
    table_index: int,
    text: str,
    doc_meta: dict[str, Any],
    table_extract_method: str,
    pdf_outline_breadcrumb: list[str] | None = None,
) -> dict[str, Any]:
    section_ref = extract_section_refs(text)
    return {
        "chunk_id": make_chunk_id_table(source_doc_id, page, table_index),
        "source_doc_id": source_doc_id,
        "corpus_version": CORPUS_VERSION,
        "content_kind": "table",
        "page": page,
        "chunk_index": table_index,
        "page_char_start": 0,
        "page_char_end": len(text),
        "section_ref": section_ref,
        "pdf_outline_breadcrumb": pdf_outline_breadcrumb,
        "text": text,
        **_base_meta_fields(doc_meta),
        "layout_hint": "pdf_table",
        "table_extract_method": table_extract_method,
    }


def write_jsonl_record(fp: TextIO, record: dict[str, Any]) -> None:
    fp.write(json.dumps(record, ensure_ascii=False) + "\n")


def emit_pages_to_jsonl(
    *,
    pages: list[tuple[int, str]],
    source_doc_id: str,
    doc_meta: dict[str, Any],
    out_fp: TextIO,
    max_chars: int,
    overlap: int,
    tables_by_page: dict[int, list[str]] | None = None,
    table_method: str | None = None,
    outline_breadcrumb_by_page: dict[int, list[str] | None] | None = None,
) -> tuple[int, int]:
    """Emit text chunks per page, then pdfplumber tables for that page (if any).

    Returns (text_chunk_count, table_chunk_count).
    """
    text_n = 0
    table_n = 0

    for page_num, page_text in pages:
        bc: list[str] | None = None
        if outline_breadcrumb_by_page is not None:
            bc = outline_breadcrumb_by_page.get(page_num)

        windows = chunk_page_text(page_text, max_chars=max_chars, overlap=overlap)
        for chunk_index, (c_start, c_end, text) in enumerate(windows):
            rec = build_text_chunk_record(
                source_doc_id=source_doc_id,
                page=page_num,
                chunk_index=chunk_index,
                page_char_start=c_start,
                page_char_end=c_end,
                text=text,
                doc_meta=doc_meta,
                pdf_outline_breadcrumb=bc,
            )
            write_jsonl_record(out_fp, rec)
            text_n += 1

        if tables_by_page and table_method and page_num in tables_by_page:
            for table_index, tsv in enumerate(tables_by_page[page_num]):
                if not tsv.strip():
                    continue
                rec = build_table_chunk_record(
                    source_doc_id=source_doc_id,
                    page=page_num,
                    table_index=table_index,
                    text=tsv,
                    doc_meta=doc_meta,
                    table_extract_method=table_method,
                    pdf_outline_breadcrumb=bc,
                )
                write_jsonl_record(out_fp, rec)
                table_n += 1

    return text_n, table_n


def read_manifest_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def primary_section_label(record: dict[str, Any]) -> str | None:
    """Best-effort single section label for KG TextChunk / Section linking (Phase 3)."""
    refs = record.get("section_ref")
    if isinstance(refs, list) and refs:
        first = refs[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    bc = record.get("pdf_outline_breadcrumb")
    if isinstance(bc, list) and bc:
        last = bc[-1]
        if isinstance(last, str) and last.strip():
            return last.strip()
    return None


def normalize_chunk_for_kg(record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with Phase 3 KG-oriented fields materialized.

    - ``effective_from``: mirrors manifest ``effective_start_date`` when non-empty (roadmap name).
    - ``section_label``: first ``section_ref`` or tail of ``pdf_outline_breadcrumb`` if missing.
    """
    out = dict(record)
    esd_raw = out.get("effective_start_date")
    esd = esd_raw.strip() if isinstance(esd_raw, str) else ""
    existing_ef = out.get("effective_from")
    if existing_ef is None or (isinstance(existing_ef, str) and not existing_ef.strip()):
        out["effective_from"] = esd if esd else None
    elif isinstance(existing_ef, str):
        ef = existing_ef.strip()
        out["effective_from"] = ef if ef else None
    sl = out.get("section_label")
    if sl is None or (isinstance(sl, str) and not sl.strip()):
        out["section_label"] = primary_section_label(out)
    return out


def validate_kg_chunk_metadata(
    record: dict[str, Any],
    *,
    line_no: int | None = None,
    strict_doc_meta: bool = False,
) -> list[str]:
    """Validate one corpus row for KG ETL. Empty list means OK."""
    loc = f"line {line_no}: " if line_no is not None else ""

    def _err(msg: str) -> str:
        return f"{loc}{msg}"

    errors: list[str] = []

    cid = record.get("chunk_id")
    if not cid or not isinstance(cid, str):
        errors.append(_err("chunk_id must be a non-empty string"))
    elif not str(cid).strip():
        errors.append(_err("chunk_id must be a non-empty string"))

    sid = record.get("source_doc_id")
    if not sid or not isinstance(sid, str):
        errors.append(_err("source_doc_id must be a non-empty string"))
    elif not str(sid).strip():
        errors.append(_err("source_doc_id must be a non-empty string"))

    cv = record.get("corpus_version")
    if cv is not None and cv != CORPUS_VERSION:
        errors.append(_err(f"corpus_version should be '{CORPUS_VERSION}' when present (got {cv!r})"))

    if strict_doc_meta:
        tier = record.get("tier")
        if tier is None or (isinstance(tier, str) and not tier.strip()):
            errors.append(_err("tier must be non-empty when strict_doc_meta"))
        inst = record.get("instrument_type")
        if inst is None or (isinstance(inst, str) and not inst.strip()):
            errors.append(_err("instrument_type must be non-empty when strict_doc_meta"))

    return errors
