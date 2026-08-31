"""Re-extract one focus window and merge it into the stored extract.

A full re-extract of a long Act costs real GPT spend and rewrites provisions
that are already reviewed. When one window produced a bad shape, only that
window is re-run: rows carrying its `window_id` are replaced and every other
entity in the stored run is preserved byte for byte.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from oe_engine_app.config import get_oe_engine_settings
from oe_engine_app.services.extract import extract_window
from oe_engine_app.services.extract_llm import ExtractLLM
from oe_engine_app.services.regate import window_id_of
from oe_engine_app.services.windows import extract_focus_windows, load_doc_text


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:6]


def merge_window_entities(
    stored: list[dict[str, Any]],
    window_id: str,
    fresh: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Replace this window's rows in place; rows from other windows are kept."""
    out: list[dict[str, Any]] = []
    inserted = False
    for entity in stored:
        if window_id_of(entity.get("entry_id", "")) != window_id:
            out.append(entity)
            continue
        if not inserted:
            out.extend(fresh)
            inserted = True
    if not inserted:
        out.extend(fresh)
    return out


def reextract_window(
    session: Session,
    *,
    source_doc_id: str,
    window_id: str,
    llm: ExtractLLM,
    write: bool = True,
) -> dict[str, Any]:
    settings = get_oe_engine_settings()
    path = settings.OE_ENGINE_EXTRACT_OUT / f"{source_doc_id}__current.json"
    if not path.is_file():
        raise FileNotFoundError(f"no stored extract for {source_doc_id}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))

    doc = load_doc_text(session, source_doc_id)
    windows = {w.window_id: w for w in extract_focus_windows(doc)}
    window = windows.get(window_id)
    if window is None:
        raise KeyError(f"{window_id!r} is not a window of {source_doc_id}: {sorted(windows)}")

    stored = payload.get("entities") or []
    replaced = [e for e in stored if window_id_of(e.get("entry_id", "")) == window_id]
    fresh = extract_window(doc=doc, window=window, llm=llm, dry_run=False)
    merged = merge_window_entities(stored, window_id, fresh)

    payload["entities"] = merged
    payload["extraction_run_id"] = _run_id()
    notes = list(payload.get("notes") or [])
    notes.append(
        f"window {window_id} ({window.heading}) re-extracted; "
        f"{len(replaced)} rows replaced by {len(fresh)}"
    )
    payload["notes"] = notes
    if write:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return {
        "source_doc_id": source_doc_id,
        "window_id": window_id,
        "heading": window.heading,
        "window_chars": window.char_count,
        "replaced": len(replaced),
        "extracted": len(fresh),
        "entity_count": len(merged),
        "extraction_run_id": payload["extraction_run_id"],
        "written": write,
        "rows": [
            {
                "entry_id": e.get("entry_id"),
                "compare_group_id": e.get("compare_group_id"),
                "display_name": e.get("display_name"),
                "cap_amount": e.get("cap_amount"),
                "unit": e.get("unit"),
                "included": e.get("included"),
                "engine_scope": e.get("engine_scope"),
                "quote": (e.get("quote") or "")[:200],
            }
            for e in fresh
        ],
    }
