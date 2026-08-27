"""Re-extract: archive previous run JSON; side-by-side diff including eligibility/evidence."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from oe_engine_app.config import get_oe_engine_settings

DIFF_FIELDS = (
    "compare_group_id",
    "display_name",
    "cap_amount",
    "unit",
    "quote",
    "paragraph_ref",
    "section_ref",
    "filing_line",
    "stacking",
    "required_evidence",
    "eligibility",
    "effective_from",
    "effective_to",
    "input_kind",
)


def archive_dir() -> Path:
    return get_oe_engine_settings().OE_ENGINE_EXTRACT_OUT / "archive"


def current_run_path(source_doc_id: str) -> Path:
    return get_oe_engine_settings().OE_ENGINE_EXTRACT_OUT / f"{source_doc_id}__current.json"


def _load(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _diff_value(old: Any, new: Any) -> dict[str, Any] | None:
    if old == new:
        return None
    return {"old": old, "new": new}


def side_by_side_diff(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    old_entities = {
        str(e.get("entry_id")): e
        for e in (previous.get("entities") or [])
        if e.get("entry_id")
    }
    new_entities = {
        str(e.get("entry_id")): e
        for e in (current.get("entities") or [])
        if e.get("entry_id")
    }
    rows: list[dict[str, Any]] = []
    for eid, new in new_entities.items():
        old = old_entities.get(eid)
        if old is None:
            rows.append({"entry_id": eid, "change": "added", "fields": {}})
            continue
        fields: dict[str, Any] = {}
        for key in DIFF_FIELDS:
            changed = _diff_value(old.get(key), new.get(key))
            if changed is not None:
                fields[key] = changed
        if fields:
            rows.append({"entry_id": eid, "change": "updated", "fields": fields})
    for eid in old_entities:
        if eid not in new_entities:
            rows.append({"entry_id": eid, "change": "removed", "fields": {}})
    return {
        "previous_extraction_run_id": previous.get("extraction_run_id"),
        "current_extraction_run_id": current.get("extraction_run_id"),
        "source_doc_id": current.get("source_doc_id") or previous.get("source_doc_id"),
        "changes": rows,
    }


def archive_previous_and_diff(current: dict[str, Any]) -> dict[str, Any] | None:
    """Move prior current JSON to archive/; write a side-by-side diff. None if first run."""
    source_doc_id = str(current.get("source_doc_id") or "")
    if not source_doc_id:
        return None
    pointer = current_run_path(source_doc_id)
    previous = _load(pointer)
    out_dir = get_oe_engine_settings().OE_ENGINE_EXTRACT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    if previous is None:
        return None
    dest_dir = archive_dir() / source_doc_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    prev_id = str(previous.get("extraction_run_id") or "previous")
    archived = dest_dir / f"{prev_id}.json"
    archived.write_text(json.dumps(previous, indent=2, ensure_ascii=False), encoding="utf-8")
    diff = side_by_side_diff(previous, current)
    diff_path = out_dir / f"{source_doc_id}__diff.json"
    diff_path.write_text(json.dumps(diff, indent=2, ensure_ascii=False), encoding="utf-8")
    return diff


def copy_run_into_archive(path: Path) -> Path | None:
    if not path.is_file():
        return None
    dest = archive_dir() / path.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    return dest
