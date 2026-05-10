"""Phase 3 Step 12 — load and validate NLU intent → graph entry map JSON."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

DEFAULT_MAP_PATH = _REPO / "knowledge_graph" / "nlu_intent_graph_map_v1.json"

_ENTRY_STRATEGIES = frozenset(
    {
        "match_concept_by_id",
        "match_relief_by_id",
        "retrieval_first",
        "cypher_template",
    }
)
_FALLBACKS = frozenset({"clarify", "skip", "retrieval_first", "nearest_concept"})

_PARAM_PLACEHOLDER_RE = re.compile(r"\$(\w+)")


def load_intent_map(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_MAP_PATH
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def validate_intent_map(doc: dict[str, Any], *, map_path: Path | None = None) -> list[str]:
    errs: list[str] = []
    prefix = f"{map_path}: " if map_path else ""

    if doc.get("map_version") is None:
        errs.append(f"{prefix}missing map_version")

    intents = doc.get("intents")
    if not isinstance(intents, list) or not intents:
        errs.append(f"{prefix}'intents' must be a non-empty list")
        return errs

    seen: set[str] = set()
    has_default = False
    for i, row in enumerate(intents):
        if not isinstance(row, dict):
            errs.append(f"{prefix}intents[{i}] must be an object")
            continue
        intent = row.get("nlu_intent")
        if not intent or not isinstance(intent, str):
            errs.append(f"{prefix}intents[{i}].nlu_intent must be a non-empty string")
        else:
            if intent in seen:
                errs.append(f"{prefix}duplicate nlu_intent '{intent}'")
            else:
                seen.add(intent)
            if intent == "_default":
                has_default = True

        ent = row.get("entry")
        if not isinstance(ent, dict):
            errs.append(f"{prefix}intents[{i}].entry must be an object")
            continue

        st = ent.get("strategy")
        if not st or st not in _ENTRY_STRATEGIES:
            errs.append(
                f"{prefix}intents[{i}].entry.strategy must be one of {sorted(_ENTRY_STRATEGIES)}"
            )

        params = ent.get("parameters")
        if not isinstance(params, dict):
            errs.append(f"{prefix}intents[{i}].entry.parameters must be an object")
        elif st == "match_concept_by_id":
            cid = params.get("concept_id")
            if not cid or not isinstance(cid, str):
                errs.append(
                    f"{prefix}intents[{i}]: match_concept_by_id requires parameters.concept_id"
                )
        elif st == "match_relief_by_id":
            rid = params.get("relief_id")
            if not rid or not isinstance(rid, str):
                errs.append(
                    f"{prefix}intents[{i}]: match_relief_by_id requires parameters.relief_id"
                )

        tpl = ent.get("cypher_template")
        if st == "retrieval_first":
            if tpl is not None and not isinstance(tpl, str):
                errs.append(f"{prefix}intents[{i}].entry.cypher_template must be null or string")
        elif st != "retrieval_first":
            if not tpl or not isinstance(tpl, str):
                errs.append(
                    f"{prefix}intents[{i}]: strategy {st} requires a cypher_template string"
                )
            elif isinstance(params, dict) and tpl:
                for name in _PARAM_PLACEHOLDER_RE.findall(tpl):
                    if name not in params:
                        errs.append(
                            f"{prefix}intents[{i}]: template uses ${name} but parameters omit it"
                        )

        hints = row.get("expansion_hints")
        if hints is not None and (
            not isinstance(hints, list) or not all(isinstance(x, str) for x in hints)
        ):
            errs.append(f"{prefix}intents[{i}].expansion_hints must be a string list or omitted")

        fb = row.get("fallback_behavior")
        if not fb or fb not in _FALLBACKS:
            errs.append(
                f"{prefix}intents[{i}].fallback_behavior must be one of {sorted(_FALLBACKS)}"
            )

    if not has_default:
        errs.append(f"{prefix}recommended: include nlu_intent '_default' for unknown routing")

    return errs


def intent_row_for_intent(doc: dict[str, Any], nlu_intent: str | None) -> dict[str, Any] | None:
    """Return mapping row for intent, or `_default` row, or None if missing."""
    rows = [r for r in doc.get("intents", []) if isinstance(r, dict)]
    by_id = {r["nlu_intent"]: r for r in rows if isinstance(r.get("nlu_intent"), str)}
    if nlu_intent and nlu_intent in by_id:
        return by_id[nlu_intent]
    return by_id.get("_default")
