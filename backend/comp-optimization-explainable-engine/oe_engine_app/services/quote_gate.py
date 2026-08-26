"""Phase 4-style quote substring gate: verbatim-in after whitespace fold."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_WS_RE = re.compile(r"\s+")
# pypdf keeps the hyphen a printer used to wrap a word across lines, so the
# stream reads "twenty- five" where the Act prints "twenty-five". Folding that
# back is only ever used as a fallback, never to loosen a match that passes.
_LINE_BREAK_HYPHEN_RE = re.compile(r"(?<=[A-Za-z0-9])-\s+(?=[A-Za-z0-9])")
_QUOTE_MAP = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u00a0": " ",
}


def normalize_for_match(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    for src, dst in _QUOTE_MAP.items():
        text = text.replace(src, dst)
    return _WS_RE.sub(" ", text).strip().lower()


def join_line_break_hyphens(value: str) -> str:
    return _LINE_BREAK_HYPHEN_RE.sub("-", value or "")


def normalize_table_cells(value: str) -> str:
    """Fold pdfplumber tabs and the window's ' | ' cell markers to spaces."""
    folded = (value or "").replace("\t", " ").replace("|", " ")
    return normalize_for_match(folded)


def _contains(needle: str, haystack: str) -> bool:
    """Substring, then the same test with wrap hyphens rejoined on both sides."""
    if not needle:
        return False
    if needle in haystack:
        return True
    return join_line_break_hyphens(needle) in join_line_break_hyphens(haystack)


def quote_in_text(quote: str, source: str) -> bool:
    return _contains(normalize_for_match(quote), normalize_for_match(source))


def quote_in_table(quote: str, tables_text: str) -> bool:
    return _contains(normalize_table_cells(quote), normalize_table_cells(tables_text))


def reassembled_out(quote: str, source: str) -> bool:
    """True when words appear but not as one contiguous (whitespace-folded) span."""
    needle = normalize_for_match(quote)
    haystack = normalize_for_match(source)
    if not needle or _contains(needle, haystack):
        return False
    words = [w for w in needle.split(" ") if w]
    if len(words) < 4:
        return False
    return all(word in haystack for word in words)


def quote_gate(
    quote: str,
    window_text: str,
    stream_text: str,
    tables_text: str,
) -> dict[str, Any]:
    needle = normalize_for_match(quote)
    if not needle:
        return {
            "quote_ok_window": False,
            "quote_ok_full_doc": False,
            "quote_source": "none",
            "reassembled_out": False,
        }
    in_window = quote_in_text(quote, window_text) or quote_in_table(quote, window_text)
    in_stream = quote_in_text(quote, stream_text)
    in_tables = bool(tables_text) and quote_in_table(quote, tables_text)
    source = "none"
    if in_stream:
        source = "text_stream"
    elif in_tables:
        source = "table_render"
    return {
        "quote_ok_window": in_window,
        "quote_ok_full_doc": in_stream or in_tables,
        "quote_source": source,
        "reassembled_out": reassembled_out(quote, window_text or stream_text),
    }


PASS2_NEIGHBORHOOD_CHARS = 1_800


def pass2_window(quote: str, focus_text: str) -> str:
    if len(focus_text) <= 2 * PASS2_NEIGHBORHOOD_CHARS:
        return focus_text
    words = [w for w in re.split(r"\s+", (quote or "").strip()) if w][:8]
    if not words:
        return focus_text
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words), re.IGNORECASE)
    match = pattern.search(focus_text)
    if not match:
        return focus_text
    start = match.start()
    lo = max(0, start - PASS2_NEIGHBORHOOD_CHARS)
    hi = min(len(focus_text), start + len(quote) + PASS2_NEIGHBORHOOD_CHARS)
    return focus_text[lo:hi]
