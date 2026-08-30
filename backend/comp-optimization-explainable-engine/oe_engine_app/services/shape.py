"""Compare live extract entities against the Phase 4 fixture contract."""

from __future__ import annotations

from typing import Any


def _flatten_keys(payload: dict[str, Any], prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else key
        keys.add(path)
        if isinstance(value, dict):
            keys |= _flatten_keys(value, path)
    return keys


def compare_entity_shape(
    actual: dict[str, Any], planned: dict[str, Any]
) -> dict[str, Any]:
    actual_keys = _flatten_keys(actual)
    planned_keys = _flatten_keys(planned)
    missing = sorted(planned_keys - actual_keys)
    extra = sorted(actual_keys - planned_keys)
    return {
        "entity_kind": actual.get("entity_kind") or planned.get("entity_kind"),
        "ok": not missing,
        "missing_keys": missing,
        "extra_keys": extra,
        "planned_key_count": len(planned_keys),
        "actual_key_count": len(actual_keys),
    }


def first_of_kind(entities: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for entity in entities:
        if entity.get("entity_kind") == kind:
            return entity
    return None
