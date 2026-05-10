"""Phase 3 Step 7 — validate curated edge JSONL rows against ontology_v1."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kg_ontology_lib as kol

_STRUCTURAL_KEYS = frozenset(
    {
        "rel_type",
        "from_label",
        "from_key",
        "from_id",
        "to_label",
        "to_key",
        "to_id",
    }
)


def allowed_edge_property_keys(ontology: dict[str, Any]) -> set[str]:
    raw = ontology.get("optional_edge_properties")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if isinstance(x, str)}


def edge_properties_for_neo4j(row: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Strip structural keys; omit None; only whitelisted metadata keys."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k in _STRUCTURAL_KEYS or v is None:
            continue
        if k not in allowed:
            continue
        out[k] = v
    return out


def validate_edge_row(
    row: dict[str, Any],
    ontology: dict[str, Any],
    *,
    line_no: int | None = None,
) -> list[str]:
    """Return errors; empty means OK."""
    loc = f"line {line_no}: " if line_no is not None else ""
    errs: list[str] = []

    for k in (
        "rel_type",
        "from_label",
        "from_key",
        "from_id",
        "to_label",
        "to_key",
        "to_id",
    ):
        v = row.get(k)
        if v is None or not isinstance(v, str) or not v.strip():
            errs.append(f"{loc}missing or empty '{k}'")

    allowed_meta = allowed_edge_property_keys(ontology)
    for k in row:
        if k in _STRUCTURAL_KEYS:
            continue
        if k not in allowed_meta:
            errs.append(f"{loc}unknown or disallowed key '{k}' (not in ontology optional_edge_properties)")

    if errs:
        return errs

    rel_type = str(row["rel_type"])
    spec = kol.relationship_spec(ontology, rel_type)
    if spec is None:
        errs.append(f"{loc}unknown rel_type '{rel_type}'")
        return errs

    fl = str(row["from_label"])
    tl = str(row["to_label"])
    if fl not in spec.get("from_labels", []):
        errs.append(f"{loc}from_label '{fl}' not allowed for {rel_type}")
    if tl not in spec.get("to_labels", []):
        errs.append(f"{loc}to_label '{tl}' not allowed for {rel_type}")

    exp_fk = kol.node_id_property(ontology, fl)
    exp_tk = kol.node_id_property(ontology, tl)
    fk = str(row["from_key"])
    tk = str(row["to_key"])
    if exp_fk != fk:
        errs.append(f"{loc}from_key must be '{exp_fk}' for label {fl} (got {fk!r})")
    if exp_tk != tk:
        errs.append(f"{loc}to_key must be '{exp_tk}' for label {tl} (got {tk!r})")

    conf = row.get("confidence")
    if conf is not None:
        if not isinstance(conf, (int, float)):
            errs.append(f"{loc}confidence must be a number")
        elif not 0.0 <= float(conf) <= 1.0:
            errs.append(f"{loc}confidence must be in [0, 1]")

    return errs
