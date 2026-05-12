"""Load chunk_id → text from corpus_v1 JSONL for citation snippets (Phase 2 Step 14)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_chunk_texts(path: Path | None) -> dict[str, str]:
    """Return mapping of chunk_id to raw chunk text; empty if path missing."""
    if path is None:
        return {}
    p = Path(path)
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    with p.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj: dict[str, Any] = json.loads(line)
            cid = obj.get("chunk_id")
            if not cid:
                continue
            out[str(cid)] = str(obj.get("text") or "")
    return out
