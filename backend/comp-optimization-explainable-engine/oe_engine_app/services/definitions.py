"""Pull the Act's own definitions of the terms a relief leans on.

"an individual who is a senior citizen" decides who may claim, but the test for
it sits in the interpretation section pages away, so the card asks a filer to
qualify themselves against a term the Act never shows them. Definitions are read
from the same document the relief was extracted from, so the wording is the
Act's rather than a paraphrase.

Only multi-word terms that appear in the relief's own quote or eligibility text
are attached. Single words like "individual" or "person" are defined too, and
matching them would put a definition on almost every card.
"""

from __future__ import annotations

import re
from typing import Any

MAX_DEFINITIONS_PER_RELIEF = 3
MAX_DEFINITION_CHARS = 700
_LEAD_CHARS = 120
_MAX_BODY_CHARS = 1200
_MIN_BODY_CHARS = 40

_WS_RE = re.compile(r"\s+")
_TERM_RE = re.compile(r"\u201c([^\u201d]{2,60})\u201d")
_DEFINING_VERB_RE = re.compile(r"\b(means|includes)\b", re.IGNORECASE)
_INTERPRETATION_RE = re.compile(
    r"\b(\d{1,3})\.\s*(?:\(\s*1\s*\)\s*)?In this Act", re.IGNORECASE
)


def _flatten(text: str) -> str:
    return _WS_RE.sub(" ", text or "")


def _trim_to_last_clause(body: str) -> str:
    cut = body.rfind(";")
    return body[:cut] if cut > _MIN_BODY_CHARS else body


def interpretation_section_ref(document: str) -> str:
    """"195" for the section that opens "In this Act", or "" when not found."""
    match = _INTERPRETATION_RE.search(_flatten(document))
    return match.group(1) if match else ""


def extract_definitions(document: str) -> dict[str, str]:
    """Every quoted term the Act defines, keyed by the term in lower case."""
    flat = _flatten(document)
    spots = [(m.start(), m.end(), m.group(1)) for m in _TERM_RE.finditer(flat)]
    out: dict[str, str] = {}
    for index, (start, end, term) in enumerate(spots):
        if not _DEFINING_VERB_RE.search(flat[end : end + _LEAD_CHARS]):
            continue
        stop = spots[index + 1][0] if index + 1 < len(spots) else end + _MAX_BODY_CHARS
        body = _trim_to_last_clause(flat[start : min(stop, len(flat))]).strip()
        key = _flatten(term).strip().lower()
        if key and body:
            out.setdefault(key, body)
    return out


def _relief_text(payload: dict[str, Any]) -> str:
    eligibility = payload.get("eligibility")
    parts = [str(payload.get("quote") or ""), str(payload.get("eligibility_text") or "")]
    if isinstance(eligibility, dict):
        parts.append(str(eligibility.get("text") or ""))
        parts.append(str(eligibility.get("quote") or ""))
    return _flatten(" ".join(part for part in parts if part)).lower()


def _clip(body: str) -> str:
    if len(body) <= MAX_DEFINITION_CHARS:
        return body
    return f"{body[:MAX_DEFINITION_CHARS].rsplit(' ', 1)[0]}..."


def definitions_for(
    payload: dict[str, Any],
    definitions: dict[str, str],
    section_ref: str = "",
) -> list[dict[str, str]]:
    """Defined terms this relief uses, in the order the relief mentions them."""
    text = _relief_text(payload)
    if not text:
        return []
    found: list[tuple[int, str]] = []
    for term in definitions:
        if len(term.split()) < 2:
            continue
        at = text.find(term)
        if at >= 0:
            found.append((at, term))
    found.sort()
    return [
        {
            "term": term,
            "text": _clip(definitions[term]),
            "section_ref": section_ref,
        }
        for _at, term in found[:MAX_DEFINITIONS_PER_RELIEF]
    ]
