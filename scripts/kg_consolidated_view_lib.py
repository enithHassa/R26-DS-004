"""Phase 3 Step 10 — ConsolidatedViewPassage anchor ids and row validation."""

from __future__ import annotations

import re
from typing import Any

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def _slug(part: str) -> str:
    s = _SLUG_RE.sub("_", part.strip()).strip("_").lower()
    return s or "x"


def make_anchor_id(
    source_doc_id: str,
    consolidated_as_of: str,
    *,
    section_uid: str | None = None,
    chunk_id: str | None = None,
) -> str:
    """Stable anchor_id for a passage inside a consolidated edition."""
    tail = (section_uid or chunk_id or "").strip()
    if not tail:
        raise ValueError("make_anchor_id requires section_uid or chunk_id")
    as_of = _slug(consolidated_as_of.replace("/", "-"))
    return f"{source_doc_id.strip()}::cv::{as_of}::{_slug(tail)}"


def validate_anchor_row(row: dict[str, Any], *, line_no: int | None = None) -> list[str]:
    """Validate one JSONL object for neo4j_load_consolidated_anchors."""
    loc = f"line {line_no}: " if line_no is not None else ""
    errs: list[str] = []

    aid = row.get("anchor_id")
    if not aid or not isinstance(aid, str) or not aid.strip():
        errs.append(f"{loc}anchor_id must be a non-empty string")

    sid = row.get("source_doc_id")
    if not sid or not isinstance(sid, str) or not sid.strip():
        errs.append(f"{loc}source_doc_id must be a non-empty string")

    as_of = row.get("consolidated_as_of")
    if not as_of or not isinstance(as_of, str) or not as_of.strip():
        errs.append(f"{loc}consolidated_as_of must be a non-empty string (e.g. ISO date)")

    for opt in ("section_label_snapshot", "chunk_id", "review_status"):
        v = row.get(opt)
        if v is not None and not isinstance(v, str):
            errs.append(f"{loc}{opt} must be a string or omitted")

    for k in row:
        if k in ("anchor_id", "source_doc_id", "consolidated_as_of", "section_label_snapshot", "chunk_id", "review_status"):
            continue
        errs.append(f"{loc}unknown key {k!r}")

    return errs


def props_for_neo4j(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten anchor row for SET (omit null chunk_id)."""
    out: dict[str, Any] = {}
    for k in (
        "anchor_id",
        "source_doc_id",
        "consolidated_as_of",
        "section_label_snapshot",
        "chunk_id",
        "review_status",
    ):
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, str) and not v.strip() and k == "chunk_id":
            continue
        out[k] = v
    return out
