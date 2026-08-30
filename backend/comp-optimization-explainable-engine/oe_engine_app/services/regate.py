"""Replay the quote gate over a stored extract. No GPT, no re-extract spend.

Only gate rejections are revisited. A row whose stored `quote_ok_full_doc` is
already true but which is still `included: false` was set aside during Act
review, so its verdict is left alone — a corrected gate must not silently
re-admit provisions a reviewer removed. Nothing here can turn `included` off.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.services.quote_gate import quote_gate
from oe_engine_app.services.windows import (
    DocText,
    FocusWindow,
    extract_focus_windows,
    load_doc_text,
)

MIN_QUOTE_CHARS = 15

GATE_FIELDS = ("quote_ok_window", "quote_ok_full_doc", "quote_source", "included")


def window_id_of(entry_id: str) -> str:
    """`oee-act-10-2021:w009:relief:2` -> `w009`."""
    parts = str(entry_id or "").split(":")
    return parts[1] if len(parts) > 2 else ""


def gate_fields(quote: str, window_text: str, doc: DocText) -> dict[str, Any]:
    gated = quote_gate(quote, window_text, doc.stream, doc.tables_blob)
    long_enough = len((quote or "").strip()) >= MIN_QUOTE_CHARS
    return {
        "quote_ok_window": gated["quote_ok_window"],
        "quote_ok_full_doc": gated["quote_ok_full_doc"],
        "quote_source": gated["quote_source"],
        "included": bool(
            gated["quote_ok_window"] and gated["quote_ok_full_doc"] and long_enough
        ),
    }


def is_gate_rejection(entity: dict[str, Any]) -> bool:
    return not entity.get("quote_ok_full_doc")


def regate_entities(
    entities: list[dict[str, Any]],
    doc: DocText,
    windows: list[FocusWindow],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {window.window_id: window for window in windows}
    changes: list[dict[str, Any]] = []
    out: list[dict[str, Any]] = []
    for entity in entities:
        if not is_gate_rejection(entity):
            out.append(dict(entity))
            continue
        window = by_id.get(window_id_of(entity.get("entry_id", "")))
        fresh = gate_fields(
            str(entity.get("quote") or ""),
            window.text if window is not None else doc.stream,
            doc,
        )
        before = {key: entity.get(key) for key in GATE_FIELDS}
        if before == fresh:
            out.append(dict(entity))
            continue
        updated = dict(entity)
        updated.update(fresh)
        updated["included"] = bool(entity.get("included")) or fresh["included"]
        changes.append(
            {
                "entry_id": entity.get("entry_id"),
                "compare_group_id": entity.get("compare_group_id"),
                "display_name": entity.get("display_name"),
                "before": before,
                "after": {key: updated.get(key) for key in GATE_FIELDS},
            }
        )
        out.append(updated)
    return out, changes


def regate_extract(
    session: Session,
    source_doc_id: str,
    *,
    write: bool = True,
) -> dict[str, Any]:
    path = get_oe_engine_settings().OE_ENGINE_EXTRACT_OUT / f"{source_doc_id}__current.json"
    if not path.is_file():
        raise FileNotFoundError(f"no stored extract for {source_doc_id}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    doc = load_doc_text(session, source_doc_id)
    entities, changes = regate_entities(
        payload.get("entities") or [], doc, extract_focus_windows(doc)
    )
    payload["entities"] = entities
    if write and changes:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return {
        "source_doc_id": source_doc_id,
        "entity_count": len(entities),
        "changed": len(changes),
        "now_included": sum(
            1 for c in changes if c["after"]["included"] and not c["before"]["included"]
        ),
        "written": bool(write and changes),
        "changes": changes,
    }
