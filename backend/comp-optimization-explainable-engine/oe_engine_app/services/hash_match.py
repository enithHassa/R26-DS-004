"""Act-only hash-match: identical / updated / insert."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

HashBranch = Literal["identical", "updated", "insert"]


def canonical_payload_hash(entities: list[dict[str, Any]]) -> str:
    included = [e for e in entities if e.get("included") is not False]
    blob = json.dumps(included, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def classify_act_hash(*, existing_hash: str | None, new_hash: str) -> HashBranch:
    if not existing_hash:
        return "insert"
    if existing_hash == new_hash:
        return "identical"
    return "updated"
