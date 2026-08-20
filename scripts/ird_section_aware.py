"""Section-aware provision-preserving chunk helpers for adaptive-tax corpus.

Used by ``ird_corpus_lib.emit_pages_to_jsonl(..., section_aware=True)``.
Does not invent legal rules — deterministic structure detection only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CHUNK_SCHEMA_VERSION_SECTION_AWARE = "section_aware_v1"

_RE_SECTION_LINE = re.compile(
    r"(?m)^[ \t]*(?:Section[ \t]+(\d+[A-Za-z]?)[ \t]*[\.\:\-–]?|"
    r"(\d+[A-Za-z]?)\.[ \t]+(?=[A-Z(]))"
)
_RE_SUBSECTION_LINE = re.compile(r"(?m)^[ \t]*\((\d+[A-Za-z]?)\)[ \t]+")
_RE_FIRST_SCHEDULE = re.compile(r"(?im)^[ \t]*First[ \t]+Schedule\b")
_RE_NAMED_SCHEDULE = re.compile(
    r"(?im)^[ \t]*((?:Second|Third|Fourth|Fifth|Sixth)[ \t]+Schedule)\b"
)
_RE_SECTION_MENTION = re.compile(r"(?i)\bsection[ \t]+(\d+[A-Za-z]?)\b")
_RE_SUBSECTION_MENTION = re.compile(r"(?i)\bsub-?section[ \t]*\(([0-9A-Za-z]+)\)")
_RE_PARA_MENTION = re.compile(
    r"(?i)\b(?:paragraph|para\.?)[ \t]+(\d+[A-Za-z]?(?:\([^)]+\))*)"
)
_RE_TOC = re.compile(
    r"(?i)\barrangement\s+of\s+sections\b|\btable\s+of\s+contents\b|\bsection\s+title\s+page\b"
)
_RE_HEADER_FOOTER = re.compile(
    r"printed\s+on\s+the\s+order\s+of\s+government|"
    r"parliament\s+of\s+the\s+democratic|"
    r"gazette\s+of\s+the\s+democratic",
    re.I,
)
_RE_OPERATIVE = re.compile(
    r"\b(?:shall|means|includes|deduct|chargeable|assessable|relief|"
    r"qualifying\s+payment|employment\s+income|taxable\s+income|"
    r"carry\s*(?:-|\s*)forward|rate\s+of\s+tax)\b",
    re.I,
)
_RE_CROSS_REF = re.compile(
    r"\bas\s+(?:referred|defined|provided)\s+in\s+section\b|"
    r"\bin\s+accordance\s+with\s+section\b|"
    r"\bsubject\s+to\s+(?:the\s+provisions\s+of\s+)?section\b",
    re.I,
)


def parent_provision_id_for(
    section_num: str | None,
    paragraph_ref: str | None,
    *,
    schedule_ref: str | None = None,
) -> str:
    """Stable id for a provision (e.g. sec52_4, first_schedule)."""
    if schedule_ref and not section_num:
        slug = re.sub(r"[^a-z0-9]+", "_", schedule_ref.lower()).strip("_")
        return slug or "schedule"
    if not section_num:
        return "unknown_provision"
    sec = section_num.lower()
    if paragraph_ref:
        para = paragraph_ref.lower()
        if para.startswith(sec):
            para = para[len(sec) :]
        para = re.sub(r"[()]", "_", para)
        para = re.sub(r"_+", "_", para).strip("_")
        return f"sec{sec}_{para}" if para else f"sec{sec}"
    return f"sec{sec}"


def classify_chunk_flags(text: str) -> dict[str, bool]:
    """Heuristic TOC / header / cross-ref / operative flags."""
    t = text or ""
    is_toc = bool(_RE_TOC.search(t))
    if not is_toc:
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        if len(lines) >= 8:
            dotted = sum(1 for ln in lines if re.match(r"^\d+[A-Za-z]?\.\s+\S+", ln))
            if dotted >= 5 and dotted / len(lines) >= 0.4:
                is_toc = True
    is_header = bool(_RE_HEADER_FOOTER.search(t)) and len(t) < 900
    if len(t.strip()) < 40:
        is_header = True
    looks_op = (
        not is_toc and not is_header and len(t) >= 80 and bool(_RE_OPERATIVE.search(t))
    )
    is_xref = bool(_RE_CROSS_REF.search(t)) and not looks_op
    return {
        "is_toc": is_toc,
        "is_header_footer": is_header,
        "is_cross_reference": is_xref,
        "is_operative_provision": looks_op,
    }


@dataclass
class ProvisionContext:
    """Running primary provision while scanning Act text."""

    section_num: str | None = None
    paragraph_num: str | None = None
    schedule_ref: str | None = None

    @property
    def paragraph_ref(self) -> str | None:
        if self.section_num and self.paragraph_num:
            return f"{self.section_num}({self.paragraph_num})"
        return None

    @property
    def section_ref_primary(self) -> str | None:
        if self.schedule_ref and not self.section_num:
            return self.schedule_ref
        if self.section_num:
            return self.section_num
        return None

    def parent_id(self) -> str:
        return parent_provision_id_for(
            self.section_num,
            self.paragraph_ref,
            schedule_ref=self.schedule_ref if not self.section_num else None,
        )

    def copy(self) -> ProvisionContext:
        return ProvisionContext(
            section_num=self.section_num,
            paragraph_num=self.paragraph_num,
            schedule_ref=self.schedule_ref,
        )


@dataclass
class ProvisionSegment:
    """One coherent provision (or preamble) span within a page."""

    page_char_start: int
    page_char_end: int
    text: str
    context: ProvisionContext
    starts_new_heading: bool = False


@dataclass
class _Boundary:
    pos: int
    kind: str
    section_num: str | None = None
    paragraph_num: str | None = None
    schedule_ref: str | None = None


def _collect_boundaries(page_text: str) -> list[_Boundary]:
    bounds: list[_Boundary] = []
    for m in _RE_SECTION_LINE.finditer(page_text):
        num = m.group(1) or m.group(2)
        if not num:
            continue
        bounds.append(_Boundary(pos=m.start(), kind="section", section_num=num))
    for m in _RE_SUBSECTION_LINE.finditer(page_text):
        bounds.append(
            _Boundary(pos=m.start(), kind="subsection", paragraph_num=m.group(1))
        )
    for m in _RE_FIRST_SCHEDULE.finditer(page_text):
        bounds.append(
            _Boundary(pos=m.start(), kind="schedule", schedule_ref="First Schedule")
        )
    for m in _RE_NAMED_SCHEDULE.finditer(page_text):
        bounds.append(
            _Boundary(
                pos=m.start(),
                kind="schedule",
                schedule_ref=re.sub(r"\s+", " ", m.group(1).strip()),
            )
        )
    bounds.sort(key=lambda b: (b.pos, 0 if b.kind == "section" else 1))
    out: list[_Boundary] = []
    seen_pos: set[int] = set()
    for b in bounds:
        if b.pos in seen_pos:
            continue
        seen_pos.add(b.pos)
        out.append(b)
    return out


def split_page_into_provisions(
    page_text: str,
    *,
    running: ProvisionContext | None = None,
) -> tuple[list[ProvisionSegment], ProvisionContext]:
    """Split page text on section/subsection/schedule headings; inherit running context."""
    ctx = (running or ProvisionContext()).copy()
    if not page_text.strip():
        return [], ctx

    bounds = _collect_boundaries(page_text)
    segments: list[ProvisionSegment] = []

    if not bounds:
        segments.append(
            ProvisionSegment(
                page_char_start=0,
                page_char_end=len(page_text),
                text=page_text.strip(),
                context=ctx.copy(),
                starts_new_heading=False,
            )
        )
        return [s for s in segments if s.text], ctx

    first = bounds[0]
    if first.pos > 0:
        pre = page_text[: first.pos].strip()
        if pre:
            segments.append(
                ProvisionSegment(
                    page_char_start=0,
                    page_char_end=first.pos,
                    text=pre,
                    context=ctx.copy(),
                    starts_new_heading=False,
                )
            )

    for i, b in enumerate(bounds):
        end = bounds[i + 1].pos if i + 1 < len(bounds) else len(page_text)
        piece = page_text[b.pos : end]
        if b.kind == "section" and b.section_num:
            ctx.section_num = b.section_num
            ctx.paragraph_num = None
            ctx.schedule_ref = None
        elif b.kind == "subsection" and b.paragraph_num:
            ctx.paragraph_num = b.paragraph_num
        elif b.kind == "schedule" and b.schedule_ref:
            ctx.schedule_ref = b.schedule_ref
            ctx.section_num = None
            ctx.paragraph_num = None
        text = piece.strip()
        if text:
            segments.append(
                ProvisionSegment(
                    page_char_start=b.pos,
                    page_char_end=end,
                    text=text,
                    context=ctx.copy(),
                    starts_new_heading=True,
                )
            )

    return segments, ctx


def split_provision_with_continuity(
    text: str,
    *,
    max_chars: int,
    overlap: int,
    chunk_page_text_fn: Any,
) -> list[tuple[str, int, int]]:
    """Split oversized provision; returns (piece, part_index_1based, parts_total)."""
    t = text.strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [(t, 1, 1)]

    windows = chunk_page_text_fn(t, max_chars=max_chars, overlap=overlap)
    parts = len(windows)
    return [(piece, i + 1, parts) for i, (_s, _e, piece) in enumerate(windows)]


def detect_section_metadata(text: str, primary: ProvisionContext) -> dict[str, Any]:
    """Primary vs referenced section/paragraph metadata for one chunk."""
    flags = classify_chunk_flags(text)
    primary_section = primary.section_ref_primary
    paragraph_ref = primary.paragraph_ref
    schedule_ref = primary.schedule_ref

    section_refs: list[str] = []
    if primary_section:
        if str(primary_section).lower().endswith("schedule"):
            section_refs.append(str(primary_section))
        else:
            section_refs.append(f"Section {primary_section}")

    referenced: list[str] = []
    for m in _RE_SECTION_MENTION.finditer(text):
        start = m.start()
        prefix = text[max(0, start - 12) : start].lower()
        if "subsection" in prefix or "sub-section" in prefix:
            continue
        label = f"Section {m.group(1)}"
        if label not in section_refs and label not in referenced:
            referenced.append(label)

    for m in _RE_PARA_MENTION.finditer(text):
        label = f"paragraph {m.group(1)}"
        if label not in referenced:
            referenced.append(label)

    subsection_only = [m.group(1) for m in _RE_SUBSECTION_MENTION.finditer(text)]
    all_refs = list(dict.fromkeys([*section_refs, *referenced]))

    if primary_section and not str(primary_section).lower().endswith("schedule"):
        section_ref_value: Any = f"Section {primary_section}"
    elif schedule_ref:
        section_ref_value = schedule_ref
    elif all_refs:
        section_ref_value = all_refs
    else:
        section_ref_value = None

    pid = None
    if primary_section or schedule_ref:
        pid = primary.parent_id()

    # Flag for optional human/GPT metadata assist (never auto-run in rebuild).
    needs_review = False
    if not flags["is_toc"] and not flags["is_header_footer"]:
        if section_ref_value is None and flags["is_operative_provision"]:
            needs_review = True
        elif section_ref_value is None and len(text.strip()) >= 200:
            needs_review = True

    return {
        "section_ref": section_ref_value,
        "section_refs": all_refs or None,
        "schedule_ref": schedule_ref,
        "paragraph_ref": paragraph_ref,
        "referenced_sections": referenced or None,
        "subsection_only_refs": subsection_only or None,
        "parent_provision_id": pid,
        **flags,
        "needs_review": needs_review,
        "metadata_source": "deterministic",
        "chunk_schema_version": CHUNK_SCHEMA_VERSION_SECTION_AWARE,
    }
