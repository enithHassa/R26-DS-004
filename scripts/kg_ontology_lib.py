"""Load and validate Phase 3 knowledge-graph ontology (nodes + relationships)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ONTOLOGY_PATH = _REPO_ROOT / "knowledge_graph" / "ontology_v1.json"

_REL_TYPE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def load_ontology(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_ONTOLOGY_PATH
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def validate_ontology(doc: dict[str, Any], *, path: Path | None = None) -> list[str]:
    """Return human-readable errors; empty list means OK."""
    errors: list[str] = []
    prefix = f"{path}: " if path else ""

    for key in ("ontology_version", "node_labels", "relationship_types"):
        if key not in doc:
            errors.append(f"{prefix}missing top-level key '{key}'")

    labels = doc.get("node_labels")
    if not isinstance(labels, list) or not labels:
        errors.append(f"{prefix}'node_labels' must be a non-empty list")
        return errors

    seen_nodes: set[str] = set()
    for i, node in enumerate(labels):
        if not isinstance(node, dict):
            errors.append(f"{prefix}node_labels[{i}] must be an object")
            continue
        label = node.get("label")
        if not label or not isinstance(label, str):
            errors.append(f"{prefix}node_labels[{i}].label must be a non-empty string")
        elif label in seen_nodes:
            errors.append(f"{prefix}duplicate node label '{label}'")
        else:
            seen_nodes.add(label)
        id_prop = node.get("id_property")
        if not id_prop or not isinstance(id_prop, str):
            errors.append(f"{prefix}node_labels[{i}].id_property must be a non-empty string")
        kps = node.get("key_properties")
        if not isinstance(kps, list) or not kps or not all(isinstance(x, str) for x in kps):
            errors.append(f"{prefix}node_labels[{i}].key_properties must be a non-empty string list")
        elif id_prop and id_prop not in kps:
            errors.append(f"{prefix}node_labels[{i}].id_property '{id_prop}' not in key_properties")

    rels = doc.get("relationship_types")
    if not isinstance(rels, list) or not rels:
        errors.append(f"{prefix}'relationship_types' must be a non-empty list")
        return errors

    seen_rels: set[str] = set()
    for i, rel in enumerate(rels):
        if not isinstance(rel, dict):
            errors.append(f"{prefix}relationship_types[{i}] must be an object")
            continue
        rtype = rel.get("type")
        if not rtype or not isinstance(rtype, str):
            errors.append(f"{prefix}relationship_types[{i}].type must be a non-empty string")
        elif rtype in seen_rels:
            errors.append(f"{prefix}duplicate relationship type '{rtype}'")
        elif not _REL_TYPE_RE.match(rtype):
            errors.append(
                f"{prefix}relationship_types[{i}].type '{rtype}' must be UPPER_SNAKE "
                "(uppercase letters, digits, underscores; start with a letter)"
            )
        else:
            seen_rels.add(rtype)

        for end in ("from_labels", "to_labels"):
            ends = rel.get(end)
            if not isinstance(ends, list) or not ends or not all(isinstance(x, str) for x in ends):
                errors.append(
                    f"{prefix}relationship_types[{i}].{end} must be a non-empty list of strings"
                )
                continue
            for lbl in ends:
                if lbl not in seen_nodes:
                    errors.append(
                        f"{prefix}relationship_types[{i}].{end} references unknown node label '{lbl}'"
                    )

    return errors


def node_id_property(ontology: dict[str, Any], label: str) -> str | None:
    """Return the canonical id property for a node label, or None."""
    for n in ontology.get("node_labels", []):
        if isinstance(n, dict) and n.get("label") == label:
            ip = n.get("id_property")
            return str(ip) if isinstance(ip, str) else None
    return None


def relationship_spec(ontology: dict[str, Any], rel_type: str) -> dict[str, Any] | None:
    """Return the relationship_types entry for ``rel_type``, or None."""
    for r in ontology.get("relationship_types", []):
        if isinstance(r, dict) and r.get("type") == rel_type:
            return r
    return None
