"""Heuristic edge suggestions (Phase 3 Step 7) — weak MENTIONS from alias substring matches."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_concepts_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    concepts = data.get("concepts")
    if not isinstance(concepts, list):
        raise ValueError("concepts JSON must have a 'concepts' array")
    return [c for c in concepts if isinstance(c, dict)]


def suggest_mentions_edges(
    chunk_record: dict[str, Any],
    concepts: list[dict[str, Any]],
    *,
    base_confidence: float = 0.4,
) -> list[dict[str, Any]]:
    """Emit MENTIONS rows for TextChunk → Concept when any alias appears in chunk text (case-insensitive)."""
    text = (chunk_record.get("text") or "").lower()
    chunk_id = chunk_record.get("chunk_id")
    if not text or not chunk_id:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for c in concepts:
        concept_id = c.get("concept_id")
        if not concept_id:
            continue
        cid = str(concept_id)
        aliases = c.get("aliases") or []
        hit = False
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and alias.lower() in text:
                    hit = True
                    break
        if hit and cid not in seen:
            seen.add(cid)
            out.append(
                {
                    "rel_type": "MENTIONS",
                    "from_label": "TextChunk",
                    "from_key": "chunk_id",
                    "from_id": str(chunk_id),
                    "to_label": "Concept",
                    "to_key": "concept_id",
                    "to_id": cid,
                    "confidence": float(base_confidence),
                    "review_status": "auto_alias_match",
                    "source_note": "kg_edges_heuristic_lib substring match",
                }
            )
    return out
