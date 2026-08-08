"""PyMuPDF text extraction + amendment-focused prompt windowing.

Critical quality rule: never pass the whole Act to GPT. Prefer the
"sections amended" summary and blocks of the form
"Section X of the principal enactment is amended" plus nearby substituted text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

# ~8k tokens at ~4 chars/token — keeps GPT prompts bounded.
DEFAULT_MAX_FOCUS_CHARS = 32_000
_BLOCK_TAIL_CHARS = 2_200
_SUMMARY_WINDOW_CHARS = 4_000

# "Section 52 of the principal enactment is hereby amended …"
_PRINCIPAL_AMENDED_RE = re.compile(
    r"Section\s+(?P<section>\d+[A-Za-z]?)\s+of\s+the\s+principal\s+enactment\s+"
    r"is\s+(?:hereby\s+)?amended",
    re.IGNORECASE,
)

# Broader "Amendment of section 52" style headings used in some gazettes.
_AMENDMENT_OF_SECTION_RE = re.compile(
    r"Amendment\s+of\s+section\s+(?P<section>\d+[A-Za-z]?)",
    re.IGNORECASE,
)

# Intro / schedule cues for a "sections amended" list or table.
# Prefer specific "sections amended" cues before generic short-title.
_SECTIONS_AMENDED_PRIMARY_RE = re.compile(
    r"(?:"
    r"sections?\s+(?:of\s+the\s+principal\s+enactment\s+)?amended"
    r"|amendment\s+of\s+sections?"
    r"|of\s+the\s+principal\s+enactment\s+are\s+hereby\s+amended"
    r")",
    re.IGNORECASE,
)
_SECTIONS_AMENDED_FALLBACK_RE = re.compile(
    r"short\s+title\s+and\s+date\s+of\s+operation",
    re.IGNORECASE,
)

_SECTION_TOKEN_RE = re.compile(r"\bSection\s+(\d+[A-Za-z]?)\b", re.IGNORECASE)


@dataclass
class FocusedAmendmentText:
    """Focused text ready for a structured-extraction prompt."""

    full_text: str
    focused_text: str
    amends_section_candidates: list[str] = field(default_factory=list)
    page_count: int = 0
    truncated: bool = False
    char_count_full: int = 0
    char_count_focused: int = 0


def extract_pdf_pages(path: Path | str) -> list[tuple[int, str]]:
    """Return (1-based page number, page text) via PyMuPDF."""
    doc = fitz.open(str(path))
    try:
        pages: list[tuple[int, str]] = []
        for i, page in enumerate(doc):
            pages.append((i + 1, page.get_text("text") or ""))
        return pages
    finally:
        doc.close()


def extract_pdf_text(path: Path | str) -> str:
    """Full PDF text with page markers (for audit; not for GPT prompts)."""
    parts: list[str] = []
    for page_num, text in extract_pdf_pages(path):
        parts.append(f"\n\n--- Page {page_num} ---\n\n{text}")
    return "".join(parts).strip()


def extract_focused_amendment_text(
    path: Path | str,
    *,
    max_chars: int = DEFAULT_MAX_FOCUS_CHARS,
) -> FocusedAmendmentText:
    """Extract PDF text and shrink to amendment-focused prompt input."""
    pages = extract_pdf_pages(path)
    full_text = "".join(
        f"\n\n--- Page {page_num} ---\n\n{text}" for page_num, text in pages
    ).strip()
    focused = focus_amendment_text(full_text, max_chars=max_chars)
    focused.page_count = len(pages)
    return focused


def focus_amendment_text(
    full_text: str,
    *,
    max_chars: int = DEFAULT_MAX_FOCUS_CHARS,
) -> FocusedAmendmentText:
    """Build a capped prompt window from already-extracted amendment text.

    Pure function — unit-testable without a PDF.
    """
    normalized = full_text.replace("\r\n", "\n").replace("\r", "\n")
    candidates: list[str] = []
    blocks: list[str] = []

    summary = _extract_sections_amended_summary(normalized)
    if summary:
        blocks.append("### Sections amended (summary)\n" + summary)
        candidates.extend(_section_ids_in(summary))

    for match in _PRINCIPAL_AMENDED_RE.finditer(normalized):
        section = match.group("section")
        candidates.append(section)
        block = _slice_amendment_block(normalized, match.start())
        blocks.append(
            f"### Principal enactment amendment — Section {section}\n{block.strip()}"
        )

    for match in _AMENDMENT_OF_SECTION_RE.finditer(normalized):
        section = match.group("section")
        candidates.append(section)
        # Avoid duplicating a block we already captured via principal-enactment phrasing.
        already = any(f"Section {section}" in b[:120] for b in blocks)
        if already:
            continue
        block = _slice_amendment_block(normalized, match.start())
        blocks.append(f"### Amendment of section {section}\n{block.strip()}")

    if not blocks:
        # Fallback: front matter only — still never send the whole Act.
        head = normalized[: min(max_chars, _SUMMARY_WINDOW_CHARS * 2)].strip()
        blocks.append("### Amendment excerpt (fallback front matter)\n" + head)
        candidates.extend(_section_ids_in(head))

    focused = "\n\n".join(blocks)
    truncated = False
    if len(focused) > max_chars:
        focused = focused[:max_chars].rstrip() + "\n\n[… truncated for prompt budget …]"
        truncated = True

    unique_candidates = _unique_preserve(candidates)
    return FocusedAmendmentText(
        full_text=normalized,
        focused_text=focused,
        amends_section_candidates=unique_candidates,
        page_count=0,
        truncated=truncated,
        char_count_full=len(normalized),
        char_count_focused=len(focused),
    )


def _extract_sections_amended_summary(text: str) -> str:
    """Pull a window around 'sections amended' / short-title cues."""
    match = _SECTIONS_AMENDED_PRIMARY_RE.search(text)
    if match is None:
        match = _SECTIONS_AMENDED_FALLBACK_RE.search(text)
    if match is None:
        if len(text) <= _SUMMARY_WINDOW_CHARS:
            return text.strip()
        return ""

    start = max(0, match.start() - 400)
    # Stop before the first detailed principal-enactment block when possible.
    first_block = _PRINCIPAL_AMENDED_RE.search(text, pos=match.end())
    natural_end = first_block.start() if first_block is not None else len(text)
    end = min(natural_end, match.start() + _SUMMARY_WINDOW_CHARS, len(text))
    if end <= start:
        end = min(len(text), match.start() + _SUMMARY_WINDOW_CHARS)
    return text[start:end].strip()


def _slice_amendment_block(text: str, start: int) -> str:
    """Take from match start through nearby substituted text / next section amend."""
    tail = text[start:]
    next_match = _PRINCIPAL_AMENDED_RE.search(tail, pos=10)
    limit = next_match.start() if next_match is not None else _BLOCK_TAIL_CHARS
    limit = min(limit, _BLOCK_TAIL_CHARS)
    window = tail[:limit]

    first_break = window.find("\n\n")
    if first_break >= 80:
        rest = window[first_break + 2 :].lstrip()
        if not _looks_like_amendment_continuation(rest):
            return window[:first_break]
        second = window.find("\n\n", first_break + 2)
        if second != -1 and not _looks_like_amendment_continuation(
            window[second + 2 :].lstrip()
        ):
            return window[:second]
    return window


def _looks_like_amendment_continuation(text: str) -> bool:
    if not text:
        return False
    head = text[:240].lower()
    cues = (
        "substitution",
        "subsection",
        "insert",
        "repeal",
        "following",
        "provided that",
        "the words",
        "shall be",
        "by the",
    )
    return any(cue in head for cue in cues)


def _section_ids_in(text: str) -> list[str]:
    return [m.group(1) for m in _SECTION_TOKEN_RE.finditer(text)]


def _unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
