"""Split a relief that lists its recipients as (i)(ii)(iii) into sub-items.

Fifth Schedule 1(b) is one relief in the Act but ten separate donees, and a
taxpayer can give to more than one of them. Collapsing that into a single rupee
box loses which donee each amount went to, so the enumeration is read off the
quote and every item keeps its own verbatim fragment as provenance.

Extraction stops this particular quote mid-list, so the enumeration is completed
from the ingested document rather than re-running the model over an Act whose
other provisions have already been reviewed. That text is raw PDF, so two
artefacts have to be undone first: pypdf repeats a span of the donee list, and
the running page header falls in the middle of item (vii).
"""

from __future__ import annotations

import re
from typing import Any

_ROMAN_SEQUENCE = (
    "i",
    "ii",
    "iii",
    "iv",
    "v",
    "vi",
    "vii",
    "viii",
    "ix",
    "x",
    "xi",
    "xii",
    "xiii",
    "xiv",
    "xv",
)
# A list is only a list once it reaches (ii); a lone "(iii)" is this row's own label.
MIN_SUB_ITEMS = 2
MAX_LOOKAHEAD_CHARS = 800
MAX_EXTENSION_CHARS = 4000
MIN_REPEAT_CHARS = 40
_LABEL_MAX_CHARS = 90
_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_ITEM_END_RE = re.compile(r";|\s\([a-z]\)\s")


def _marker(roman: str) -> re.Pattern[str]:
    return re.compile(rf"\(\s*{roman}\s*\)", re.IGNORECASE)


def _flatten(text: str) -> str:
    return _WS_RE.sub(" ", text or "")


def _tidy(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip().strip(";:,.- ").strip()


def _short_label(text: str) -> str:
    clean = _tidy(text)
    if len(clean) <= _LABEL_MAX_CHARS:
        return clean
    return f"{clean[:_LABEL_MAX_CHARS].rsplit(' ', 1)[0]}..."


def _first_tandem_repeat(text: str, min_len: int) -> tuple[int, int] | None:
    """Start and period of the first span that appears twice back to back.

    A repeat of period k puts the same min_len-char probe at i and i + k, so one
    pass over the probes finds every candidate period without trying them all.
    """
    seen: dict[str, int] = {}
    for at in range(len(text) - min_len + 1):
        probe = text[at : at + min_len]
        start = seen.setdefault(probe, at)
        if start == at:
            continue
        period = at - start
        if period >= min_len and text[start : start + period] == text[at : at + period]:
            return start, period
    return None


def collapse_immediate_repeats(text: str, min_len: int = MIN_REPEAT_CHARS) -> str:
    """Drop one copy of a span that pypdf emitted twice back to back."""
    out = text
    while (found := _first_tandem_repeat(out, min_len)) is not None:
        start, period = found
        out = out[: start + period] + out[start + 2 * period :]
    return out


def strip_running_header(text: str, act_name: str) -> str:
    """Remove "218 Inland Revenue Act, No. 24 of 2017" left mid-sentence by the PDF.

    The registry spells the Act without the comma the printed header uses, so the
    title is matched token by token rather than verbatim.
    """
    words = _WORD_RE.findall(act_name or "")
    if not words:
        return text
    title = r"[\s,.]*".join(re.escape(word) for word in words)
    header = re.compile(rf"\s*\d{{1,4}}\s+{title}\s*", re.IGNORECASE)
    return header.sub(" ", text)


def find_enumeration_spans(text: str) -> list[tuple[str, int, int]]:
    """Positions of a sequential (i), (ii), (iii)... run, in order."""
    spans: list[tuple[str, int, int]] = []
    search_from = 0
    for roman in _ROMAN_SEQUENCE:
        match = _marker(roman).search(text, search_from)
        if match is None:
            break
        if spans:
            spans[-1] = (spans[-1][0], spans[-1][1], match.start())
        spans.append((roman, match.end(), len(text)))
        search_from = match.end()
    return spans


def split_enumeration(text: str) -> list[dict[str, str]]:
    spans = find_enumeration_spans(text)
    if len(spans) < MIN_SUB_ITEMS:
        return []
    items: list[dict[str, str]] = []
    for roman, start, end in spans:
        body = _tidy(text[start:end])
        if body:
            items.append({"roman": roman, "text": body})
    return items


def complete_from_document(quote: str, document: str) -> str:
    """Extend a quote that stops mid-list, using the document it came from."""
    spans = find_enumeration_spans(quote or "")
    if not spans or not document:
        return quote
    anchor = _tidy(quote[: spans[-1][1]])
    if not anchor:
        return quote
    flat = _flatten(document)
    at = flat.find(anchor)
    if at < 0:
        return quote
    window = collapse_immediate_repeats(flat[at : at + len(anchor) + MAX_EXTENSION_CHARS])
    cursor = len(anchor)
    end = cursor
    for roman in _ROMAN_SEQUENCE[_ROMAN_SEQUENCE.index(spans[-1][0]) + 1 :]:
        match = _marker(roman).search(window[end : end + MAX_LOOKAHEAD_CHARS])
        if match is None:
            break
        end += match.end()
    if end == cursor:
        return quote
    rest = window[end : end + MAX_LOOKAHEAD_CHARS]
    stop = _ITEM_END_RE.search(rest)
    tail = window[cursor:end] + (rest[: stop.start()] if stop else rest)
    return f"{anchor}{tail}"


def sub_items_for(payload: dict[str, Any], document: str = "") -> list[dict[str, str]]:
    """Sub-item rows for one relief, or [] when it is not an enumerated relief."""
    quote = str(payload.get("quote") or "")
    if not quote:
        return []
    source = complete_from_document(quote, document) if document else quote
    source = strip_running_header(source, str(payload.get("act_name") or ""))
    parts = split_enumeration(source)
    if len(parts) < MIN_SUB_ITEMS:
        return []
    group = str(payload.get("compare_group_id") or "relief")
    return [
        {
            "component_id": f"{group}:{part['roman']}",
            "roman": part["roman"],
            "label": _short_label(part["text"]),
            "quote": part["text"],
        }
        for part in parts
    ]
