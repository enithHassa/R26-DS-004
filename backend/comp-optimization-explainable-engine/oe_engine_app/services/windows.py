"""6k–11k character extract windows from ingested dual-channel chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from db.models import OeEngineChunk, OeEngineDocument
from oe_engine_app.schemas.extract import ExtractWindow

WINDOW_MIN_CHARS = 6_000
WINDOW_TARGET_CHARS = 8_000
WINDOW_MAX_CHARS = 11_000
NAMED_SCHEDULE_WINDOW_CHARS = 24_000
NAMED_SCHEDULE_TEXT_CAP = 28_000

_BODY_CUE_RE = re.compile(
    r"%|\bRs\.|\bper\s+centum\b|\btaxable\s+income\b|\bqualifying\s+payment\b|\brelief\b",
    re.IGNORECASE,
)
_BREAK_RE = re.compile(r"\n\s*\n+")
_RATE_TABLE_RE = re.compile(r"taxable\s+income", re.IGNORECASE)
_NEXT_SCHEDULE_RE = re.compile(
    r"(?:^|\n)\s*(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH)\s+SCHEDULE\b",
    re.IGNORECASE,
)
_CONS_EXTRA_RE = re.compile(
    r"qualifying payment.{0,200}carried forward|carried forward.{0,200}qualifying payment",
    re.IGNORECASE | re.DOTALL,
)
_GUIDE_KEEP_RE = re.compile(
    r"personal relief"
    r"|aggregate reliefs"
    r"|qualifying payments?(?:\s+and\s+reliefs)?"
    r"|employment income relief"
    r"|tax[-\s]?free threshold"
    r"|basic relief"
    r"|this relief is available"
    r"|approved charitable institution"
    r"|senior citizen.{0,120}interest"
    r"|interest income.{0,80}senior"
    r"|rental income from an investment"
    r"|foreign currency.{0,100}service rendered"
    r"|qualifying payments and reliefs",
    re.IGNORECASE | re.DOTALL,
)
_TOC_DOTS_RE = re.compile(r"\.{4,}")
_GUIDE_SKIP_RE = re.compile(
    r"transfer pricing|TP Audit Procedure|Dispute Resolution Panel",
    re.IGNORECASE,
)


def format_table_slice(text: str) -> str:
    """Present pdfplumber TSV rows with the ' | ' separators the extract prompt quotes."""
    if not text:
        return ""
    return text.replace("\t", " | ")


# Sri Lankan Act PDFs set body text in a narrow column, so pypdf returns a hard
# newline every few words ("including promotional\nexpenditure of such film").
# Asked to quote that, GPT-4o drops the break instead of spacing it, producing
# "promotionalexpenditure" and failing the gate. Reflow each paragraph before
# the model sees it; list markers keep their own line so structure survives.
_PARA_BREAK_RE = re.compile(r"\n[ \t]*\n\s*")
_WRAP_HYPHEN_RE = re.compile(r"(?<=[A-Za-z0-9])-\n(?=[a-z])")
_LIST_MARKER = r"\(\s*(?:[ivxlcdm]{1,5}|[a-z]|\d{1,2})\s*\)"
_SOFT_WRAP_RE = re.compile(rf"\n(?![ \t]*(?:{_LIST_MARKER}|Provided\b))", re.IGNORECASE)
_RUNS_RE = re.compile(r"[ \t]{2,}")


def reflow_column_text(text: str) -> str:
    """Join wrapped lines within a paragraph; keep paragraph and list breaks."""
    if not text:
        return ""
    paragraphs: list[str] = []
    for part in _PARA_BREAK_RE.split(text):
        joined = _WRAP_HYPHEN_RE.sub("-", part)
        joined = _SOFT_WRAP_RE.sub(" ", joined)
        joined = _RUNS_RE.sub(" ", joined).strip()
        if joined:
            paragraphs.append(joined)
    return "\n\n".join(paragraphs)


@dataclass
class DocText:
    source_doc_id: str
    title: str
    tier: str
    stream: str
    tables_blob: str
    page_spans: list[tuple[int, int, int]] = field(default_factory=list)
    tables_by_page: dict[int, str] = field(default_factory=dict)

    def pages_in_span(self, start: int, end: int) -> list[int]:
        pages: list[int] = []
        for page, lo, hi in self.page_spans:
            if lo < end and hi > start and page not in pages:
                pages.append(page)
        return pages

    def tables_for_pages(self, pages: list[int]) -> str:
        blocks = [self.tables_by_page[p] for p in pages if p in self.tables_by_page]
        return "\n\n".join(blocks)


@dataclass
class FocusWindow:
    window_id: str
    heading: str
    start: int
    end: int
    stream_slice: str
    tables_slice: str
    page_start: int | None
    page_end: int | None

    def _tables_block(self) -> str:
        rendered = format_table_slice(self.tables_slice)
        if not rendered:
            return ""
        return (
            "### Tables on these pages, reconstructed from the same PDF\n"
            "Each line is one table row; cells are separated by ' | '.\n\n"
            + rendered
        )

    def _prefer_tables_first(self) -> bool:
        heading = f"{self.heading} {self.window_id}".lower()
        if "first schedule" in heading or self.window_id == "first_schedule":
            return True
        return bool(_RATE_TABLE_RE.search(self.tables_slice or ""))

    def _text_cap(self) -> int:
        if self.window_id in {"first_schedule", "fifth_schedule"}:
            return NAMED_SCHEDULE_TEXT_CAP
        return WINDOW_MAX_CHARS

    @property
    def text(self) -> str:
        prose = reflow_column_text(self.stream_slice)
        if not self.tables_slice:
            body = prose
        else:
            tables_block = self._tables_block()
            if self._prefer_tables_first():
                body = tables_block + "\n\n" + prose
            else:
                body = prose + "\n\n" + tables_block
        cap = self._text_cap()
        if len(body) > cap:
            return body[:cap]
        return body

    @property
    def char_count(self) -> int:
        return len(self.text)

    def to_schema(self) -> ExtractWindow:
        return ExtractWindow(
            window_id=self.window_id,
            heading=self.heading,
            char_count=self.char_count,
            page_start=self.page_start,
            page_end=self.page_end,
            channel_hint="table_render" if self.tables_slice else "text_stream",
        )


def load_doc_text(session: Session, source_doc_id: str) -> DocText:
    doc = session.get(OeEngineDocument, source_doc_id)
    if doc is None:
        raise ValueError(f"unknown source_doc_id (ingest first): {source_doc_id}")
    chunks = (
        session.query(OeEngineChunk)
        .filter(OeEngineChunk.source_doc_id == source_doc_id)
        .order_by(OeEngineChunk.page, OeEngineChunk.chunk_index)
        .all()
    )
    if not chunks:
        raise ValueError(f"no chunks for {source_doc_id}")
    stream_parts: list[str] = []
    page_spans: list[tuple[int, int, int]] = []
    tables_by_page: dict[int, list[str]] = {}
    cursor = 0
    for chunk in chunks:
        if chunk.channel == "table_render":
            tables_by_page.setdefault(chunk.page, []).append(chunk.text)
            continue
        start = cursor
        stream_parts.append(chunk.text)
        cursor += len(chunk.text) + 1
        page_spans.append((chunk.page, start, cursor))
    stream = "\n".join(stream_parts)
    tables_joined = {page: "\n\n".join(blocks) for page, blocks in tables_by_page.items()}
    tables_blob = "\n\n".join(tables_joined[p] for p in sorted(tables_joined))
    return DocText(
        source_doc_id=doc.source_doc_id,
        title=doc.title,
        tier=doc.tier,
        stream=stream,
        tables_blob=tables_blob,
        page_spans=page_spans,
        tables_by_page=tables_joined,
    )


def _heading_near(stream: str, start: int) -> str:
    lookback = stream[max(0, start - 400) : start + 120]
    for pattern in (
        r"(FIFTH\s+SCHEDULE)",
        r"(FIRST\s+SCHEDULE)",
        r"(SECOND\s+SCHEDULE)",
        r"((?:Section|section)\s+\d+[A-Za-z]?)",
    ):
        matches = list(re.finditer(pattern, lookback, re.IGNORECASE))
        if matches:
            return matches[-1].group(1).strip()
    snippet = stream[start : start + 80].replace("\n", " ").strip()
    return snippet or f"offset_{start}"


def _make_window(doc: DocText, start: int, end: int, window_id: str) -> FocusWindow:
    start = max(0, start)
    end = min(len(doc.stream), end)
    pages = doc.pages_in_span(start, end)
    return FocusWindow(
        window_id=window_id,
        heading=_heading_near(doc.stream, start),
        start=start,
        end=end,
        stream_slice=doc.stream[start:end],
        tables_slice=doc.tables_for_pages(pages),
        page_start=pages[0] if pages else None,
        page_end=pages[-1] if pages else None,
    )


def _next_break(stream: str, around: int) -> int:
    lo = max(0, around - 800)
    hi = min(len(stream), around + 800)
    region = stream[lo:hi]
    best = around
    best_dist = 10_000
    for match in _BREAK_RE.finditer(region):
        pos = lo + match.end()
        dist = abs(pos - around)
        if dist < best_dist:
            best = pos
            best_dist = dist
    return best


def list_windows(
    doc: DocText,
    *,
    min_chars: int = WINDOW_MIN_CHARS,
    target_chars: int = WINDOW_TARGET_CHARS,
    max_chars: int = WINDOW_MAX_CHARS,
) -> list[FocusWindow]:
    stream = doc.stream
    if not stream.strip():
        return []
    if len(stream) <= max_chars:
        return [_make_window(doc, 0, len(stream), "w000")]
    windows: list[FocusWindow] = []
    cursor = 0
    idx = 0
    while cursor < len(stream):
        remaining = len(stream) - cursor
        if remaining <= max_chars:
            end = len(stream)
        else:
            tentative = cursor + target_chars
            end = _next_break(stream, tentative)
            if end - cursor < min_chars:
                end = min(len(stream), cursor + max_chars)
            if end - cursor > max_chars:
                end = cursor + max_chars
        windows.append(_make_window(doc, cursor, end, f"w{idx:03d}"))
        idx += 1
        if end >= len(stream):
            break
        cursor = end
    return windows


def _content_score(text: str) -> int:
    return len(_BODY_CUE_RE.findall(text))


def _clip_named_schedule_end(stream: str, start: int, end: int, heading: str) -> int:
    """Stop a named schedule window at the next schedule heading."""
    ordinal = heading.split()[0].upper() if heading.split() else ""
    search_from = min(end, start + min(80, max(1, end - start)))
    for match in _NEXT_SCHEDULE_RE.finditer(stream, search_from, end):
        if match.group(1).upper() != ordinal:
            return match.start()
    return end


_TOC_NEIGHBOR_RE = re.compile(
    r"ARRANGEMENT OF SECTIONS|Section Title Page|\bSched\.\s+(?:First|Fifth)\s+Schedule",
    re.IGNORECASE,
)
_SCHEDULE_BODY_RE = re.compile(
    r"\(SECTION|\(Section|TAX RATES|QUALIFYING PAYMENTS|SPECIAL INDIVIDUAL RELIEFS",
    re.IGNORECASE,
)
_NEXT_PART_RE = re.compile(r"(?:^|\n)\s*PART\s+(?:[IVX]+|\d+)\b", re.IGNORECASE)


def _heading_hit_quality(doc: DocText, start: int, heading: str) -> int:
    """Prefer the real schedule/part body over a contents-page mention."""
    before = doc.stream[max(0, start - 240) : start]
    preview = doc.stream[start : start + 420]
    if _TOC_NEIGHBOR_RE.search(before) or _TOC_NEIGHBOR_RE.search(preview):
        return -1
    if _is_toc_window(preview):
        return -1
    if _SCHEDULE_BODY_RE.search(preview):
        return 1
    if heading.upper().startswith("PART") and "RELIEF" in preview.upper():
        return 1
    return 0


def _clip_part_window_end(stream: str, start: int, end: int) -> int:
    """Stop a Part VI A window at the next Part heading."""
    for match in _NEXT_PART_RE.finditer(stream, start + 8, end):
        if match.start() > start:
            return match.start()
    return end


def locate_named_window(
    doc: DocText,
    heading: str,
    *,
    window_chars: int = NAMED_SCHEDULE_WINDOW_CHARS,
) -> FocusWindow | None:
    """Highest-substance hit for a schedule/section heading (skips TOC)."""
    pattern = re.compile(
        rf"\b{r'\s+'.join(re.escape(part) for part in heading.split())}\b",
        re.IGNORECASE,
    )
    ranked: list[tuple[int, int, int, int]] = []
    for match in pattern.finditer(doc.stream):
        start = match.start()
        end = min(len(doc.stream), start + window_chars)
        if heading.upper().startswith("PART"):
            end = _clip_part_window_end(doc.stream, start, end)
        else:
            end = _clip_named_schedule_end(doc.stream, start, end, heading)
        quality = _heading_hit_quality(doc, start, heading)
        score = _content_score(doc.stream[start:end])
        ranked.append((quality, score, start, end))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    _quality, _score, start, end = ranked[0]
    slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")
    return _make_window(doc, start, end, slug)


SCHEMA_VALIDATE_HEADINGS: tuple[tuple[str, str], ...] = (
    ("Fifth Schedule", "fifth_schedule"),
    ("First Schedule", "first_schedule"),
)

ACT_ADMIN_EXTRA_HEADINGS: tuple[tuple[str, str], ...] = (
    ("PART VI A", "part_vi_a"),
)


def schema_validate_windows(doc: DocText) -> list[FocusWindow]:
    found: list[FocusWindow] = []
    for heading, slug in SCHEMA_VALIDATE_HEADINGS:
        window = locate_named_window(doc, heading)
        if window is None:
            raise ValueError(f"could not locate {heading!r} in {doc.source_doc_id}")
        window.window_id = slug
        window.heading = heading
        found.append(window)
    return found


def _overlap_chars(left: FocusWindow, right: FocusWindow) -> int:
    lo = max(left.start, right.start)
    hi = min(left.end, right.end)
    return max(0, hi - lo)


def named_schedule_windows(doc: DocText, *, extra: bool = False) -> list[FocusWindow]:
    found: list[FocusWindow] = []
    headings = SCHEMA_VALIDATE_HEADINGS
    if extra:
        headings = headings + ACT_ADMIN_EXTRA_HEADINGS
    for heading, slug in headings:
        window = locate_named_window(doc, heading)
        if window is None:
            continue
        window.window_id = slug
        window.heading = heading
        found.append(window)
    return found


def _is_toc_window(text: str) -> bool:
    return len(_TOC_DOTS_RE.findall(text or "")) >= 12


def _is_guide_skip_window(window: FocusWindow) -> bool:
    if _is_toc_window(window.stream_slice):
        return True
    if _GUIDE_SKIP_RE.search(window.stream_slice) and not re.search(
        r"personal relief|this relief is available", window.stream_slice, re.I
    ):
        return True
    heading = (window.heading or "").lower()
    text = window.stream_slice.lower()
    if "first schedule" in heading and "tax payable" in text and "personal relief" not in text:
        return True
    return False


def extract_focus_windows(
    doc: DocText,
    *,
    schema_validate: bool = False,
    act_admin: bool = False,
) -> list[FocusWindow]:
    """Sliding windows, plus dedicated First/Fifth Schedule windows on long Acts.

    Short amendment PDFs stay as one sliding pass. The base Act is long enough
    that 8k slices split those schedules; named windows keep each schedule intact
    and drop the overlapping slices so slabs are not extracted twice.
    Guide PDFs keep individual-relief / qualifying-payment chapters only — not the
    reprinted First/Fifth rate tables, which are often stale vs the Act year views.
    Act-admin extracts stop at the named schedules (Catalog Admin style) so later
    reprint chapters do not emit the same relief again.
    """
    if schema_validate:
        return schema_validate_windows(doc)
    sliding = list_windows(doc)
    if doc.tier == "guide":
        focused = [
            window
            for window in sliding
            if _GUIDE_KEEP_RE.search(window.stream_slice) and not _is_guide_skip_window(window)
        ]
        return focused or sliding
    if len(doc.stream) <= WINDOW_MAX_CHARS * 2:
        return sliding
    named = named_schedule_windows(doc, extra=act_admin)
    if not named:
        return sliding
    kept = [window for window in sliding if all(_overlap_chars(window, nw) <= 500 for nw in named)]
    if doc.tier == "consolidated":
        extras = [window for window in kept if _CONS_EXTRA_RE.search(window.stream_slice)]
        return named + extras
    if act_admin:
        return named
    return named + kept


def windows_to_json(windows: list[FocusWindow]) -> list[dict[str, Any]]:
    return [w.to_schema().model_dump(mode="json") for w in windows]
