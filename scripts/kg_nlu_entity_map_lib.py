"""Phase 3 Step 11 — load and validate NLU entity type → graph mapping JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kg_ontology_lib as kol

DEFAULT_MAP_PATH = _REPO / "knowledge_graph" / "nlu_entity_graph_map_v1.json"
DEFAULT_ONTOLOGY_PATH = _REPO / "knowledge_graph" / "ontology_v1.json"

_ALLOWED_STRATEGIES = frozenset(
    {
        "property_exact_ci",
        "concept_alias_ci",
        "section_uid_from_context",
        "metadata_only",
    }
)
_ALLOWED_FALLBACKS = frozenset({"clarify", "skip", "nearest_concept"})


def load_entity_map(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_MAP_PATH
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def validate_entity_map(
    doc: dict[str, Any],
    *,
    ontology: dict[str, Any] | None = None,
    ontology_path: Path | None = None,
    map_path: Path | None = None,
) -> list[str]:
    """Structural validation; optionally ensure target labels exist in ontology."""
    errs: list[str] = []
    prefix = f"{map_path}: " if map_path else ""

    if doc.get("map_version") is None:
        errs.append(f"{prefix}missing map_version")
    types = doc.get("entity_types")
    if not isinstance(types, list) or not types:
        errs.append(f"{prefix}'entity_types' must be a non-empty list")
        return errs

    seen: set[str] = set()
    ont = ontology
    if ont is None:
        op = ontology_path or DEFAULT_ONTOLOGY_PATH
        ont = kol.load_ontology(op)
    allowed_labels = {
        str(n["label"])
        for n in ont.get("node_labels", [])
        if isinstance(n, dict) and n.get("label")
    }

    for i, row in enumerate(types):
        if not isinstance(row, dict):
            errs.append(f"{prefix}entity_types[{i}] must be an object")
            continue
        et = row.get("nlu_entity_type")
        if not et or not isinstance(et, str):
            errs.append(f"{prefix}entity_types[{i}].nlu_entity_type must be a non-empty string")
        elif et in seen:
            errs.append(f"{prefix}duplicate nlu_entity_type '{et}'")
        else:
            seen.add(et)

        tgt = row.get("target_node_label")
        if tgt is not None and (not isinstance(tgt, str) or not tgt.strip()):
            errs.append(f"{prefix}entity_types[{i}].target_node_label must be null or non-empty string")
        elif isinstance(tgt, str) and tgt not in allowed_labels:
            errs.append(
                f"{prefix}entity_types[{i}] target_node_label '{tgt}' not in ontology node labels"
            )

        m = row.get("match")
        if not isinstance(m, dict):
            errs.append(f"{prefix}entity_types[{i}].match must be an object")
        else:
            st = m.get("strategy")
            if not st or st not in _ALLOWED_STRATEGIES:
                errs.append(
                    f"{prefix}entity_types[{i}].match.strategy must be one of {sorted(_ALLOWED_STRATEGIES)}"
                )
            if st and st != "metadata_only" and tgt is None:
                errs.append(
                    f"{prefix}entity_types[{i}]: non-metadata strategy requires target_node_label"
                )

        fb = row.get("fallback_behavior")
        if not fb or fb not in _ALLOWED_FALLBACKS:
            errs.append(
                f"{prefix}entity_types[{i}].fallback_behavior must be one of {sorted(_ALLOWED_FALLBACKS)}"
            )

    return errs


def entity_row_for_type(doc: dict[str, Any], nlu_entity_type: str) -> dict[str, Any] | None:
    """Return the mapping row for a canonical entity type, or None."""
    for row in doc.get("entity_types", []):
        if isinstance(row, dict) and row.get("nlu_entity_type") == nlu_entity_type:
            return row
    return None
