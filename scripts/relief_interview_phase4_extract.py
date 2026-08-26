#!/usr/bin/env python3
"""Relief Interview Phase 4: gpt-4o two-pass extraction + deterministic quote gate.

Standalone by design: copies the focus-window / quote-check pattern from the
component extractors but does not import ``gpt_extract.py`` / ``pdf_extract.py``.

Pipeline per (Act, section):

    manifest path check -> one PDF read -> section focus window
      -> Pass 1 (gpt-4o, temp 0): reliefs AND rates/rules in the same sweep
      -> Pass 2 (gpt-4o, temp 0): "is this quote verbatim?" per entry
      -> deterministic substring gate: quote_ok_focus / quote_ok_full_doc
      -> staging JSON under models/adaptive-tax/relief-interview/extracted/

Nothing here writes approved/ or rates/. Promotion is Phase 5 (human review).

Usage (from repo root):

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase4_extract.py --dry-run
  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase4_extract.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import fitz  # PyMuPDF
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"
OUT_ROOT = REPO_ROOT / "models" / "adaptive-tax" / "relief-interview"
EXTRACTED_DIR = OUT_ROOT / "extracted"
RUNS_DIR = EXTRACTED_DIR / "runs"

# Extraction corpus only. Consolidated / Guide / ontology are never opened here.
BASE_ACT_ID = "ird-ira-2017-base"

EXTRACT_SOURCE_DOC_IDS: tuple[str, ...] = (
    BASE_ACT_ID,
    "ird-amend-2021-10",
    "ird-amend-2022-45",
    "ird-amend-2023-04",
    "ird-amend-2023-14",
    "ird-amend-2025-02",
    "ird-amend-2026-11",
)

FORBIDDEN_SOURCE_DOC_IDS = frozenset(
    {"ird-consolidated-2025", "ird-guide-ira", "ird-calc-ontology-v5"}
)

# 10 sections per Act (empty focus window -> skip, no API call).
SECTION_KEYS: tuple[str, ...] = (
    "5",
    "6",
    "7",
    "8",
    "11",
    "16",
    "52",
    "89",
    "First Schedule",
    "Fifth Schedule",
)

DEFAULT_MODEL = "gpt-4o"
MAX_STREAM_CHARS = 24_000
MAX_TABLE_CHARS = 10_000
WINDOW_CHARS = 6_000
SCHEDULE_WINDOW_CHARS = 11_000
MAX_WINDOWS_PER_SECTION = 5
MAX_SCHEDULE_WINDOWS = 4

# Substance markers used to prefer a schedule's body over its table-of-contents
# entry: rates, money amounts, and relief/qualifying-payment language.
_BODY_CUE_RE = re.compile(
    r"%|\bRs\.|\bper\s+centum\b|\btaxable\s+income\b|\bqualifying\s+payment\b|\brelief\b",
    re.IGNORECASE,
)

# Evidentiary floor: a 3-character "quote" proves nothing about provenance.
MIN_QUOTE_CHARS = 15

# gpt-4o list price (USD per 1M tokens) for the run-cost estimate in the log.
USD_PER_1M_PROMPT = 2.50
USD_PER_1M_COMPLETION = 10.00


# --------------------------------------------------------------------------
# Structured output schemas (Pass 1 / Pass 2)
# --------------------------------------------------------------------------
# All fields are required and non-optional: OpenAI strict structured outputs
# require every property in `required`, so "absent" is encoded as "".


class ReliefRow(BaseModel):
    compare_group_id: str
    display_name: str
    question_prompt: str
    input_kind: Literal["notice", "yes_no_amount", "amount", "boolean"]
    help: str
    auto_applied: bool
    cap_amount: str
    unit: Literal["lkr", "percent", "text"]
    effective_from: str
    effective_to: str
    act_name: str
    section_ref: str
    quote: str


class RateBandRow(BaseModel):
    band_index: int
    band_label: str
    lower: str
    upper: str
    rate_percent: str
    effective_from: str
    applies_to: str
    act_name: str
    section_ref: str
    quote: str


class RuleRow(BaseModel):
    rule_id: str
    rule_kind: Literal["surcharge", "special_formula", "rate_rule", "other"]
    description: str
    value: str
    effective_from: str
    act_name: str
    section_ref: str
    quote: str


class Pass1Payload(BaseModel):
    reliefs: list[ReliefRow]
    rate_bands: list[RateBandRow]
    rules: list[RuleRow]


class QuoteCheck(BaseModel):
    verbatim: bool
    closest_quote: str
    note: str


PASS1_SYSTEM = """You are a Sri Lankan Inland Revenue Act extraction analyst.

You are given a focus window copied verbatim from ONE official Act PDF.
Extract, from that window ONLY:

1. reliefs ΓÇö personal relief, deductions, qualifying payments, relief caps.
2. rate_bands ΓÇö progressive income tax bands (lower, upper, rate).
3. rules ΓÇö surcharges, special formulas, other rate rules.

An amending Act usually states a relief change as a substituted or newly added
item that is nothing but an amount and a date, with the word "relief" nowhere
nearby ΓÇö for example: `by the addition immediately after item (iv) of that
subparagraph, of the following new item: - "(v) Rs. 1,800,000, for each year of
assessment commencing on or after April 1, 2025"`. That IS a relief row. Capture
the amount as `cap_amount` and the date as `effective_from`, and read the
provision being amended from the marginal note. Items in such a list are often a
history of the same relief at different dates: emit one row per item, each with
its own `effective_from` and `effective_to`, and never merge them.

Be complete: return every relief, band and rule the target provision states.
Most provisions are ordinary prose, not tables ΓÇö extract those the same way.

When the Target provision is the Fifth Schedule (or an amendment of it):
- Paragraph 1 lists QUALIFYING PAYMENTS (donations to approved funds/charities,
  film/cinema contributions, and other listed categories). Emit ONE relief row
  per distinct category or sub-item, even when the word "relief" is absent and
  even when that sub-item states no Rs/% monetary ceiling. Prefer display names
  such as "Charitable donation qualifying payment", "Approved charity donation",
  etc. Never omit a middle lettered/Roman sub-item by skipping from one clause
  opening to a later clause in the same quote.
- Paragraph 2 lists RELIEFS (personal, employment, rent, solar, expenditureΓÇª).
  Emit one row per lettered item / dated amount, as already required.
- Do not skip paragraph 1 in favour of paragraph 2. If both appear in the
  window, extract both.
- An amending Act that only substitutes dates or amounts inside an existing
  lettered item (e.g. Fifth Schedule paragraph 2(f) expenditure) is still a
  relief row: capture the new date bounds as effective_from / effective_to and
  any new cap_amount stated in the substituted words.

Hard rules for `quote` (a downstream checker re-tests this mechanically):
- `quote` MUST be ONE contiguous run of characters copied from the window,
  character-for-character. Never paraphrase, never repair typos, never reorder,
  never delete words from the middle, never join text across an ellipsis.
- Never omit middle lettered items inside a quote (e.g. do not start at 1(a)
  opening and jump over (iia) to reach (iib)).
- Whitespace inside the quote is normalized before checking, so tabs and line
  breaks are fine to include. A quote may start or stop mid-sentence.
- Aim for 15-300 characters.

If ΓÇö and only if ΓÇö a row comes from a table:
- The raw PDF text lists table cells interleaved and out of logical reading
  order, so never stitch those cells into a readable sentence and never pair a
  band with a rate by guessing from that order.
- Use the "Tables on these pages" block at the end of the window instead, where
  each line is one table row with cells separated by " | " and the band and its
  rate are correctly paired. Quote a whole line from that block.
- Each body row in that block is printed under its own copy of the column
  header, so quote either the body row alone or the header and that one body
  row together. Never join two body rows, and never reach across the blank line
  that separates one block from the next.

Scope ΓÇö this matters as much as the quotes:
- Extract ONLY what belongs to the stated Target provision. The window reaches a
  little past that provision to keep clause openings intact, so neighbouring
  provisions may be visible. Ignore them entirely.
- In an amending Act, `section_ref` must name the provision of the PRINCIPAL Act
  (Inland Revenue Act, No. 24 of 2017) that is being amended ΓÇö read it from the
  marginal note ("Amendment of section 150 of Act, No. 24 of 2017") or from
  "Section 150 of the principal enactment". NEVER cite the amending Act's own
  clause number (e.g. "Section 2(1)(a)" of the amending Act is wrong).
- `display_name` must describe what the provision actually governs. Do not call
  something a relief unless the text grants a relief.

Taxpayer-facing drafts (an auditor will edit these before they appear):
- `display_name`: short card title.
- `question_prompt`: the question shown to the taxpayer.
- `input_kind`: notice (auto-applied, no claim), yes_no_amount, amount, or boolean.
- `help`: one short sentence of help under the question. Use "" if nothing useful.
- `compare_group_id`: snake_case group key. Reuse an existing group name when this
  is the same relief at a new date or amount; otherwise invent a stable id from
  the provision (e.g. personal_relief, employment_income_relief).
- Never put a rupee amount, percent, rate band, or Act quote into display_name,
  question_prompt, or help. Caps belong in `cap_amount`. Quotes belong in `quote`.

Other hard rules:
- `act_name` must be the Act title as printed in the window
  (e.g. "Inland Revenue Act, No. 24 of 2017").
- Numbers: digits only, no commas, no currency symbol ("1200000", "6").
- `effective_from`: the date from which the provision applies, as YYYY-MM-DD,
  taken from wording such as "for a year of assessment commencing from
  April 1, 2023" -> "2023-04-01". A single Act often contains several rate
  tables for different periods, so read the sentence introducing THIS table and
  do not copy a date from a neighbouring table. "" if the window does not say.
- `effective_to` (reliefs only): exclusive end date as YYYY-MM-DD when the
  window states an upper bound, e.g. "prior to April 1, 2022" / "but prior to
  April 1, 2022" -> "2022-04-01". Use "" when the window only says "on or after
  ΓÇª" with no upper bound, or does not state an end. Never invent an end date
  from a later Act or from outside knowledge.
- `applies_to`: who or what the table taxes, in a few words, copied in substance
  from the introducing sentence (e.g. "resident or non-resident individual",
  "employees' trust fund", "gains on realisation of investment assets").
- If a value is not stated in the window, use "" ΓÇö never guess.
- If the window contains nothing extractable for a list, return that list empty.
- Do not use outside knowledge of Sri Lankan tax law. The window is the only source.
"""

PASS2_SYSTEM = """You verify quote fidelity for a legal extraction pipeline.

You are given a source text window and a candidate quote. Answer one question:
does the candidate quote appear as a CONTIGUOUS SUBSTRING of the source window,
ignoring only whitespace differences (tabs, line breaks, repeated spaces)?

- verbatim: true if every character appears, in the same order, with nothing
  deleted from the middle.
- A quote that starts or stops mid-sentence is still verbatim. Do NOT require it
  to end at a punctuation mark, and do not penalise a missing trailing
  semicolon, full stop, or closing quotation mark.
- verbatim is false if words were reordered, omitted from the middle,
  paraphrased, or stitched together from separate table cells.
- closest_quote: if false, copy the closest genuinely contiguous passage from
  the window; otherwise "".
- note: one short sentence explaining the decision.
Do not speculate about legal meaning.
"""


# --------------------------------------------------------------------------
# Manifest path authority
# --------------------------------------------------------------------------


def confirm_pdf_paths() -> tuple[dict[str, Path], list[dict[str, Any]], list[str]]:
    """Resolve extract IDs via manifest file_name; never hardcode plan-doc names."""
    if not MANIFEST_PATH.is_file():
        return {}, [], [f"corpus_manifest.json not found at {MANIFEST_PATH}"]

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pdf_root = REPO_ROOT / manifest["pdf_root"]
    by_id = {d["source_doc_id"]: d for d in manifest["documents"]}

    resolved: dict[str, Path] = {}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for sid in EXTRACT_SOURCE_DOC_IDS:
        if sid in FORBIDDEN_SOURCE_DOC_IDS:
            errors.append(f"{sid} is not an extraction source")
            continue
        doc = by_id.get(sid)
        if doc is None:
            errors.append(f"source_doc_id missing from corpus_manifest.json: {sid}")
            rows.append({"source_doc_id": sid, "file_name": "", "exists": False})
            continue
        file_name = doc["file_name"]
        path = pdf_root / file_name
        exists = path.is_file()
        rows.append(
            {
                "source_doc_id": sid,
                "file_name": file_name,
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "act_title": doc.get("title", ""),
                "exists": exists,
            }
        )
        if not exists:
            errors.append(
                f"PDF missing for {sid}: expected {path.as_posix()} "
                f"(manifest file_name={file_name!r})"
            )
        else:
            resolved[sid] = path

    return resolved, rows, errors


# --------------------------------------------------------------------------
# PDF text + section focus windows
# --------------------------------------------------------------------------


@dataclass
class ActText:
    """Two deterministic renderings of one Act PDF, from a single read.

    ``stream`` is the linear text layer. Rate schedules are laid out
    column-major there, so a band and its rate are never contiguous ΓÇö and
    reading them linearly pairs the wrong cells. ``tables`` is the
    layout-reconstructed rendering of the same table objects, which restores
    the row pairing. Both are verbatim renderings of the same PDF, so a quote
    matching either is Act-backed.
    """

    stream: str
    page_offsets: list[int]
    page_tables: dict[int, str]

    @property
    def tables_blob(self) -> str:
        return "\n\n".join(self.page_tables[p] for p in sorted(self.page_tables))

    def pages_in_span(self, start: int, end: int) -> list[int]:
        pages: list[int] = []
        for idx, offset in enumerate(self.page_offsets):
            page_end = (
                self.page_offsets[idx + 1] if idx + 1 < len(self.page_offsets) else len(self.stream)
            )
            if offset < end and page_end > start:
                pages.append(idx + 1)
        return pages


def _render_tables(page: Any, page_no: int) -> str:
    try:
        finder = page.find_tables()
    except Exception:  # noqa: BLE001 ΓÇö table detection is best-effort
        return ""
    lines: list[str] = []
    for table in getattr(finder, "tables", []):
        try:
            rows = table.extract()
        except Exception:  # noqa: BLE001
            continue
        rendered = []
        for row in rows:
            cells = [(cell or "").replace("\n", " ").strip() for cell in row]
            if any(cells):
                rendered.append(" | ".join(cells))
        if not rendered:
            continue
        if len(rendered) > 2:
            # Repeat the column header above each body row. A rate row means
            # nothing without its header, so the model quotes the two together;
            # emitting them adjacent for every row keeps that quote a genuine
            # contiguous substring of this table instead of a stitch across it.
            header, body = rendered[0], rendered[1:]
            lines.extend(f"{header}\n{row}" for row in body)
        else:
            lines.append("\n".join(rendered))
    if not lines:
        return ""
    return f"[table on page {page_no}]\n" + "\n\n".join(lines)


# Running headers PyMuPDF places at the top of continuation pages. Leaving them
# in the linear stream splits a sentence across the page break so a contiguous
# quote of the statutory prose fails the substring gate.
_RUNNING_HEADER_RE = re.compile(
    r"(?ix)"
    r"^\s*"
    r"(?:\d{1,4}\s*\n)?"
    r"Inland\s+Revenue(?:\s*\(Amendment\))?\s*"
    r"(?:\n\s*)?"
    r"Act,?\s*No\.?\s*\d+\s+of\s+\d{4}\s*\n?"
)

# Marginal notes ("Amendment of section 52 of the principal enactment") often
# land at the end of a page or mid-stream next to the body. They are not statute
# prose and they break contiguous quotes of the substituted subsection text.
_MARGINAL_NOTE_RE = re.compile(
    r"(?ix)"
    r"(?:Amendment\s+of(?:\s+the)?|"
    r"Insertion\s+of\s+new|"
    r"Replacement\s+of)"
    r"[\s\n]+"
    r"(?:section|schedule|the\s+\w+\s+schedule)"
    r"[^\n]{0,80}?"
    r"(?:\n[^\n]{0,60}){0,4}?"
    r"enactment"
)


def _strip_running_headers(page_text: str) -> str:
    """Remove Act running headers and marginal notes from a page's text layer."""
    text = _RUNNING_HEADER_RE.sub("", page_text or "", count=1)
    return _MARGINAL_NOTE_RE.sub(" ", text)


def read_act_text(path: Path) -> ActText:
    """One PDF read producing the linear text layer plus rendered tables."""
    doc = fitz.open(str(path))
    try:
        parts: list[str] = []
        offsets: list[int] = []
        tables: dict[int, str] = {}
        cursor = 0
        for idx, page in enumerate(doc):
            text = _strip_running_headers(page.get_text("text") or "")
            offsets.append(cursor)
            parts.append(text)
            cursor += len(text) + 1  # +1 for the join newline
            rendered = _render_tables(page, idx + 1)
            if rendered:
                tables[idx + 1] = rendered
        return ActText(stream="\n".join(parts), page_offsets=offsets, page_tables=tables)
    finally:
        doc.close()


def _section_patterns(section_key: str, *, is_base_act: bool) -> list[re.Pattern[str]]:
    """Ordered patterns locating a provision.

    Amendment Acts number their own clauses ("5. Section 16 of the principal
    enactment is hereby amended"), so a bare "5." heading there is the amending
    clause, not section 5. Only the base Act may match on heading numbering.
    """
    key = section_key.strip()
    if key.lower().endswith("schedule"):
        word = key.split()[0]
        return [
            re.compile(rf"\b{word}\s+SCHEDULE\b", re.IGNORECASE),
        ]
    esc = re.escape(key)
    if is_base_act:
        return [
            re.compile(rf"(?m)^\s*{esc}\.\s*\("),
            re.compile(rf"\bSection\s+{esc}\b", re.IGNORECASE),
        ]
    # Amendment Acts cite the principal Act either as "the principal enactment"
    # or literally as "Act, No. 24 of 2017" (common in marginal notes).
    principal = r"(?:the\s+principal\s+enactment|Act,?\s*No\.?\s*24\s+of\s+2017)"
    return [
        re.compile(rf"\bSection\s+{esc}\s+of\s+{principal}", re.IGNORECASE),
        re.compile(rf"\bAmendment\s+of\s+section\s+{esc}\b", re.IGNORECASE),
    ]


def _content_score(text: str) -> int:
    """How much rate/relief substance a candidate window holds.

    A schedule heading appears in the table of contents as well as in the
    schedule itself, hundreds of pages apart. Scoring lets the body win.
    """
    return len(_BODY_CUE_RE.findall(text))


def build_focus_window(act: ActText, section_key: str, *, is_base_act: bool) -> str:
    """Concatenate the highest-signal windows around a provision. '' when absent.

    Appends the layout-reconstructed tables from the same pages, so tabular
    rates can be quoted with their rows correctly paired.
    """
    full_text = act.stream
    # Marginal notes in amendment Acts are extracted mid-clause, so reach further
    # back there to keep the opening words of the amending clause in the window.
    pre_chars = 600 if is_base_act else 2_500
    is_schedule = section_key.strip().lower().endswith("schedule")
    forward = SCHEDULE_WINDOW_CHARS if is_schedule else WINDOW_CHARS
    max_windows = MAX_SCHEDULE_WINDOWS if is_schedule else MAX_WINDOWS_PER_SECTION

    spans: list[tuple[int, int]] = []
    for pattern in _section_patterns(section_key, is_base_act=is_base_act):
        for match in pattern.finditer(full_text):
            start = max(0, match.start() - pre_chars)
            end = min(len(full_text), match.start() + forward)
            spans.append((start, end))
        if spans:
            break

    if not spans:
        return ""

    spans.sort()
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    # Keep the densest windows that fit under MAX_STREAM_CHARS. Document-order
    # concatenation used to fill the budget with early TOC hits and truncate the
    # real schedule body at the end of the Act.
    ranked = sorted(merged, key=lambda s: _content_score(full_text[s[0] : s[1]]), reverse=True)
    chosen_spans: list[list[int]] = []
    used = 0
    for start, end in ranked:
        block_len = end - start
        sep = 7 if chosen_spans else 0  # len("\n\n[...]\n\n")
        if chosen_spans and used + sep + block_len > MAX_STREAM_CHARS:
            continue
        chosen_spans.append([start, end])
        used += sep + block_len
        if len(chosen_spans) >= max_windows:
            break
    chosen = sorted(chosen_spans)

    blocks = [full_text[s:e].strip() for s, e in chosen]
    focused = "\n\n[...]\n\n".join(b for b in blocks if b)
    if len(focused) > MAX_STREAM_CHARS:
        focused = focused[:MAX_STREAM_CHARS].rstrip()

    seen_pages: list[int] = []
    for start, end in chosen:
        for page in act.pages_in_span(start, end):
            if page in act.page_tables and page not in seen_pages:
                seen_pages.append(page)
    if seen_pages:
        rendered = "\n\n".join(act.page_tables[p] for p in seen_pages)
        if len(rendered) > MAX_TABLE_CHARS:
            rendered = rendered[:MAX_TABLE_CHARS].rstrip()
        focused += (
            "\n\n### Tables on these pages, reconstructed from the same PDF\n"
            "Each line is one table row; cells are separated by ' | '.\n\n" + rendered
        )
    return focused


def extract_section_prose(focus_text: str, *, max_chars: int = 3500) -> str:
    """Act prose for schedule rate rows ΓÇö intro plus inline table text from the PDF."""
    if not focus_text or not str(focus_text).strip():
        return ""
    prose = str(focus_text).split("### Tables on these pages")[0]
    prose = prose.replace("\n\n[...]\n\n", "\n\nΓÇª\n\n").strip()
    if not prose:
        return ""

    lower = prose.lower()
    start = 0
    for anchor in (
        "first schedule",
        "fifth schedule",
        "tax rates for",
        "taxable income of a resident",
        "taxable income of a",
    ):
        idx = lower.find(anchor)
        if idx >= 0:
            start = idx if "schedule" in anchor else max(0, idx - 160)
            break

    chunk = prose[start:].strip()
    end = len(chunk)
    for stop in (
        "\nSECOND SCHEDULE",
        "\nTHIRD SCHEDULE",
        "\nFOURTH SCHEDULE",
        "\n2. Tax rates for",
        "\n2. Tax rates on",
        "\n\nΓÇª\n\n",
    ):
        idx = chunk.find(stop)
        if idx > 400:
            end = min(end, idx)
    chunk = chunk[:end].strip()
    if len(chunk) > max_chars:
        chunk = chunk[:max_chars].rsplit("\n", 1)[0] + "ΓÇª"
    return chunk.strip()


# --------------------------------------------------------------------------
# Deterministic quote gate (final authority)
# --------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")
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


PASS2_NEIGHBORHOOD_CHARS = 1_800


def _locate_quote(quote: str, text: str) -> int:
    """Raw-text offset of a quote, tolerating PDF line wraps. -1 when absent."""
    words = [w for w in re.split(r"\s+", (quote or "").strip()) if w][:8]
    if not words:
        return -1
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words), re.IGNORECASE)
    match = pattern.search(text)
    return match.start() if match else -1


def pass2_window(quote: str, focus_text: str) -> str:
    """Tighten the Pass-2 prompt around a located quote to bound token spend.

    Falls back to the whole focus window when the quote cannot be located, so
    the model can still surface the closest verbatim passage.
    """
    if len(focus_text) <= 2 * PASS2_NEIGHBORHOOD_CHARS:
        return focus_text
    start = _locate_quote(quote, focus_text)
    if start < 0:
        return focus_text
    lo = max(0, start - PASS2_NEIGHBORHOOD_CHARS)
    hi = min(len(focus_text), start + len(quote) + PASS2_NEIGHBORHOOD_CHARS)
    return focus_text[lo:hi]


def quote_gate(
    quote: str, focus_norm: str, stream_norm: str, tables_norm: str
) -> dict[str, Any]:
    """Verbatim-substring test against both renderings of the source PDF."""
    needle = normalize_for_match(quote)
    if not needle:
        return {"quote_ok_focus": False, "quote_ok_full_doc": False, "quote_source": "none"}
    in_stream = needle in stream_norm
    in_tables = bool(tables_norm) and needle in tables_norm
    return {
        "quote_ok_focus": needle in focus_norm,
        "quote_ok_full_doc": in_stream or in_tables,
        "quote_source": "text_stream" if in_stream else ("table_render" if in_tables else "none"),
    }


# --------------------------------------------------------------------------
# OpenAI calls
# --------------------------------------------------------------------------


class Budget:
    """Hard call cap so a bad run cannot silently burn credits."""

    def __init__(self, max_calls: int) -> None:
        self.max_calls = max_calls
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise RuntimeError(
                f"Call budget exhausted ({self.max_calls}). Re-run with --max-calls to continue."
            )

    def record(self, usage: Any) -> None:
        self.calls += 1
        if usage is not None:
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0

    @property
    def usd(self) -> float:
        return (
            self.prompt_tokens / 1_000_000 * USD_PER_1M_PROMPT
            + self.completion_tokens / 1_000_000 * USD_PER_1M_COMPLETION
        )


def _parse(client: Any, **kwargs: Any) -> Any:
    """openai>=2 moved parse off .beta; support both."""
    try:
        return client.chat.completions.parse(**kwargs)
    except AttributeError:
        return client.beta.chat.completions.parse(**kwargs)


def call_with_retry(client: Any, budget: Budget, model: str, **kwargs: Any) -> Any:
    budget.check()
    delay = 2.0
    last: Exception | None = None
    for _ in range(4):
        try:
            completion = _parse(client, model=model, temperature=0, **kwargs)
            budget.record(getattr(completion, "usage", None))
            return completion
        except Exception as exc:  # noqa: BLE001 ΓÇö retry transient API errors
            last = exc
            message = str(exc).lower()
            if "insufficient_quota" in message or "billing" in message:
                raise RuntimeError(f"OPENAI_CREDITS_EXHAUSTED: {exc}") from exc
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"OpenAI call failed after retries: {last}")


def run_pass1(
    client: Any,
    budget: Budget,
    model: str,
    *,
    act_title: str,
    source_doc_id: str,
    section_key: str,
    focus_text: str,
    pass1_focus: str = "",
) -> tuple[Pass1Payload, dict[str, Any]]:
    focus_instruction = pass1_focus.strip() or (
        "Extract reliefs, rate_bands, and rules from the focus window below.\n"
        "Copy every `quote` verbatim from this window."
    )
    user_prompt = (
        f"Act (from corpus manifest): {act_title}\n"
        f"source_doc_id: {source_doc_id}\n"
        f"Target provision: {section_key}\n\n"
        f"{focus_instruction}\n\n"
        "--- BEGIN FOCUS WINDOW ---\n"
        f"{focus_text}\n"
        "--- END FOCUS WINDOW ---\n"
    )
    completion = call_with_retry(
        client,
        budget,
        model,
        messages=[
            {"role": "system", "content": PASS1_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_format=Pass1Payload,
    )
    message = completion.choices[0].message
    if message.refusal:
        raise RuntimeError(f"Pass 1 refused: {message.refusal}")
    payload = message.parsed or Pass1Payload(reliefs=[], rate_bands=[], rules=[])
    usage = getattr(completion, "usage", None)
    meta = {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
    }
    return payload, meta


def _merge_pass1(a: Pass1Payload, b: Pass1Payload) -> Pass1Payload:
    """Concatenate Pass-1 lists; callers re-index entry_ids on assemble."""
    return Pass1Payload(
        reliefs=list(a.reliefs) + list(b.reliefs),
        rate_bands=list(a.rate_bands) + list(b.rate_bands),
        rules=list(a.rules) + list(b.rules),
    )


_SCHEDULE_PASS1_FOCUSES = (
    (
        "FIFTH SCHEDULE ΓÇö PARAGRAPH 1 ONLY (qualifying payments / donations).\n"
        "Extract every distinct paragraph-1 category or sub-item, INCLUDING "
        "uncapped ones. Cover: 1(a) approved charity ceilings for (iia) "
        "individuals AND (iib) entities as SEPARATE rows; every 1(b)(i) "
        "through 1(b)(x) listed public donee (Government, local authority, "
        "university/HEI, Buddhist & Pali university, Government fund, local "
        "authority fund, Sevana, provincial fund, Api Wenuwen Api, National "
        "Kidney Fund, etc.); plus Samurdhi shop, film/cinema, bank-merger "
        "cost, and any other ┬╢1 category with a stated Rs/% cap. "
        "Ignore paragraph 2 reliefs in this pass. Emit one relief row per "
        "category / Roman sub-item.\n"
        "CONTIGUITY (1(a)): (iia) and (iib) MUST be separate rows. Each "
        "`quote` must be a contiguous run INSIDE that lettered ceiling clause "
        "only ΓÇö never start at the opening of 1(a) and jump over (iia) to "
        "reach (iib).\n"
        "UNCAPPED 1(b): emit one row per distinct 1(b)(i)ΓÇô(x) even when no "
        "Rs/% appears; set cap_amount to \"\". Do NOT skip a 1(b) sub-item "
        "merely because it lacks a monetary or percentage ceiling.\n"
        "EXCLUDE 1(c): do NOT extract PresidentΓÇÖs Fund remittance / "
        "paragraph 1(c).\n"
        "CRITICAL: each row's `quote` MUST be a contiguous passage that names "
        "THAT category (and states ITS own cap when one exists, e.g. 'Rupees "
        "seventy five thousand' / 'one-third of the taxable income'). Never "
        "reuse the same schedule-wide 'aggregate qualifying payments' "
        "sentence for every category. Put the stated monetary ceiling in "
        "`cap_amount` as digits only when the quote states one; use \"\" "
        "when the window states no monetary ceiling for that category."
    ),
    (
        "FIFTH SCHEDULE ΓÇö PARAGRAPH 2 ONLY (reliefs).\n"
        "Extract every lettered relief item and every dated amount history "
        "(personal, employment, rent, senior, foreign FX, solar, expenditure, "
        "etc.), including amending substitutions that only change dates or "
        "caps (e.g. subparagraph (f) with 'prior to April 1, 2022' and "
        "900,000). Ignore paragraph 1 qualifying payments in this pass. "
        "Emit one relief row per item/amount. Copy every quote verbatim.\n"
        "For a substitution that both closes an open period ('but prior to "
        "April 1, 2022') and adds a nine-month amount for the YA commencing "
        "April 1, 2022: emit TWO relief rows when both amounts/dates are "
        "stated ΓÇö one with the closed open period (effective_to from 'prior "
        "to ΓÇª') and one for the nine-month YA amount (effective_from = that "
        "YA start; effective_to = next YA start when the window limits it to "
        "that one year of assessment)."
    ),
)


def run_pass2(
    client: Any,
    budget: Budget,
    model: str,
    *,
    quote: str,
    focus_text: str,
) -> QuoteCheck:
    user_prompt = (
        "--- BEGIN SOURCE WINDOW ---\n"
        f"{focus_text}\n"
        "--- END SOURCE WINDOW ---\n\n"
        f"Candidate quote:\n{quote}\n"
    )
    completion = call_with_retry(
        client,
        budget,
        model,
        messages=[
            {"role": "system", "content": PASS2_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        response_format=QuoteCheck,
    )
    message = completion.choices[0].message
    if message.refusal:
        return QuoteCheck(verbatim=False, closest_quote="", note=f"refusal: {message.refusal}")
    return message.parsed or QuoteCheck(verbatim=False, closest_quote="", note="no parse")


# --------------------------------------------------------------------------
# Row assembly
# --------------------------------------------------------------------------


def section_ref_on_target(section_ref: str, section_key: str) -> bool:
    """Does the cited provision match the section we asked for?

    Review signal for window bleed into a neighbouring provision ΓÇö not a veto,
    since a genuine cross-reference can be legitimate.
    """
    ref = (section_ref or "").lower()
    key = section_key.strip().lower()
    if key.endswith("schedule"):
        return key.split()[0] in ref
    return re.search(rf"\b{re.escape(key)}\b", ref) is not None


def provenance_complete(row: dict[str, Any]) -> bool:
    return all(str(row.get(k, "")).strip() for k in ("act_name", "section_ref", "quote", "source_doc_id"))


def assemble_rows(
    payload: Pass1Payload,
    *,
    source_doc_id: str,
    section_key: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, r in enumerate(payload.reliefs):
        rows.append(
            {
                "row_kind": "relief",
                "entry_id": f"{source_doc_id}:{section_key}:relief:{idx}",
                "source_doc_id": source_doc_id,
                "section_key": section_key,
                **r.model_dump(mode="json"),
            }
        )
    for idx, b in enumerate(payload.rate_bands):
        rows.append(
            {
                "row_kind": "rate_band",
                "entry_id": f"{source_doc_id}:{section_key}:band:{idx}",
                "source_doc_id": source_doc_id,
                "section_key": section_key,
                **b.model_dump(mode="json"),
            }
        )
    for idx, u in enumerate(payload.rules):
        rows.append(
            {
                "row_kind": "rule",
                "entry_id": f"{source_doc_id}:{section_key}:rule:{idx}",
                "source_doc_id": source_doc_id,
                "section_key": section_key,
                **u.model_dump(mode="json"),
            }
        )
    return rows


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relief Interview Phase 4 extraction")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build focus windows and report call/cost estimate; no API calls",
    )
    parser.add_argument("--max-calls", type=int, default=400, help="Hard API call cap")
    parser.add_argument(
        "--only-doc",
        action="append",
        default=None,
        help="Limit to one or more source_doc_id values",
    )
    parser.add_argument(
        "--only-section",
        action="append",
        default=None,
        help="Limit to one or more section keys (Phase 5 re-extract of a single provision)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract sections that already have staging JSON",
    )
    args = parser.parse_args(argv)

    resolved, path_rows, errors = confirm_pdf_paths()

    print("=== Phase 4 path check (corpus_manifest authority) ===")
    for row in path_rows:
        print(f"  [{'OK' if row['exists'] else 'MISSING'}] {row['source_doc_id']} -> {row['file_name']}")
    if errors:
        print("\nPATH CHECK FAILED ΓÇö stopping before any PDF read.", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    doc_ids = [d for d in EXTRACT_SOURCE_DOC_IDS if not args.only_doc or d in args.only_doc]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    titles = {d["source_doc_id"]: d.get("title", "") for d in manifest["documents"]}

    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log: dict[str, Any] = {
        "run_id": run_id,
        "model": args.model,
        "temperature": 0,
        "dry_run": bool(args.dry_run),
        "path_check": path_rows,
        "sections": [],
    }

    client = None
    budget = Budget(args.max_calls)
    if not args.dry_run:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
        if not api_key:
            print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
            return 2
        client = OpenAI(api_key=api_key)

    total_sections = 0
    skipped_sections = 0
    total_rows = 0
    included_rows = 0
    pass2_disagreements = 0

    print(f"\n=== Phase 4 extraction (model={args.model}, temp=0) ===")
    for source_doc_id in doc_ids:
        pdf_path = resolved[source_doc_id]
        act = read_act_text(pdf_path)
        stream_norm = normalize_for_match(act.stream)
        tables_norm = normalize_for_match(act.tables_blob)
        act_title = titles.get(source_doc_id, "")
        print(
            f"\n{source_doc_id} ({pdf_path.name}, {len(act.stream):,} chars, "
            f"{len(act.page_tables)} pages with tables)"
        )

        section_keys = [
            key
            for key in SECTION_KEYS
            if not args.only_section
            or any(key.lower() == want.lower() for want in args.only_section)
        ]
        for section_key in section_keys:
            safe_key = section_key.replace(" ", "_").lower()
            out_path = EXTRACTED_DIR / f"{source_doc_id}__{safe_key}.json"

            focus_text = build_focus_window(
                act, section_key, is_base_act=source_doc_id == BASE_ACT_ID
            )
            if not focus_text:
                skipped_sections += 1
                print(f"  - {section_key:<16} empty focus -> skip (no API call)")
                log["sections"].append(
                    {
                        "source_doc_id": source_doc_id,
                        "section_key": section_key,
                        "status": "skipped_empty_focus",
                    }
                )
                continue

            total_sections += 1

            if args.dry_run:
                print(f"  - {section_key:<16} focus {len(focus_text):,} chars -> 1 Pass-1 call")
                log["sections"].append(
                    {
                        "source_doc_id": source_doc_id,
                        "section_key": section_key,
                        "status": "dry_run",
                        "focus_chars": len(focus_text),
                    }
                )
                continue

            if out_path.is_file() and not args.force:
                print(f"  - {section_key:<16} staging exists -> skip (use --force)")
                log["sections"].append(
                    {
                        "source_doc_id": source_doc_id,
                        "section_key": section_key,
                        "status": "skipped_existing",
                    }
                )
                continue

            focus_norm = normalize_for_match(focus_text)
            try:
                is_fifth = section_key.strip().lower() == "fifth schedule"
                if is_fifth:
                    payload = Pass1Payload(reliefs=[], rate_bands=[], rules=[])
                    meta = {"prompt_tokens": 0, "completion_tokens": 0}
                    for focus_instruction in _SCHEDULE_PASS1_FOCUSES:
                        part, part_meta = run_pass1(
                            client,
                            budget,
                            args.model,
                            act_title=act_title,
                            source_doc_id=source_doc_id,
                            section_key=section_key,
                            focus_text=focus_text,
                            pass1_focus=focus_instruction,
                        )
                        payload = _merge_pass1(payload, part)
                        for k in ("prompt_tokens", "completion_tokens"):
                            if part_meta.get(k) is not None:
                                meta[k] = (meta.get(k) or 0) + part_meta[k]
                else:
                    payload, meta = run_pass1(
                        client,
                        budget,
                        args.model,
                        act_title=act_title,
                        source_doc_id=source_doc_id,
                        section_key=section_key,
                        focus_text=focus_text,
                    )
            except RuntimeError as exc:
                if "OPENAI_CREDITS_EXHAUSTED" in str(exc):
                    print(f"\n!! {exc}", file=sys.stderr)
                    _write_log(log, budget, run_id)
                    return 4
                print(f"  ! {section_key}: pass1 failed: {exc}", file=sys.stderr)
                log["sections"].append(
                    {
                        "source_doc_id": source_doc_id,
                        "section_key": section_key,
                        "status": "pass1_error",
                        "error": str(exc),
                    }
                )
                continue

            rows = assemble_rows(payload, source_doc_id=source_doc_id, section_key=section_key)

            for row in rows:
                gate = quote_gate(row.get("quote", ""), focus_norm, stream_norm, tables_norm)
                row.update(gate)
                row["provenance_complete"] = provenance_complete(row)
                row["section_ref_on_target"] = section_ref_on_target(
                    row.get("section_ref", ""), section_key
                )
                try:
                    window = pass2_window(row.get("quote", ""), focus_text)
                    row["pass2_window_chars"] = len(window)
                    check = run_pass2(
                        client, budget, args.model, quote=row.get("quote", ""), focus_text=window
                    )
                    row["pass2_verbatim"] = check.verbatim
                    row["pass2_note"] = check.note
                    row["pass2_closest_quote"] = check.closest_quote
                except RuntimeError as exc:
                    if "OPENAI_CREDITS_EXHAUSTED" in str(exc):
                        print(f"\n!! {exc}", file=sys.stderr)
                        _write_log(log, budget, run_id)
                        return 4
                    row["pass2_verbatim"] = False
                    row["pass2_note"] = f"pass2_error: {exc}"
                    row["pass2_closest_quote"] = ""

                # Inclusion authority is the deterministic full-doc substring gate
                # plus complete provenance. Pass 2 is a supporting signal only:
                # a disagreement is surfaced for Phase 5 review, not a veto.
                row["quote_long_enough"] = (
                    len(normalize_for_match(row.get("quote", ""))) >= MIN_QUOTE_CHARS
                )
                row["included"] = bool(
                    row["quote_ok_full_doc"]
                    and row["provenance_complete"]
                    and row["quote_long_enough"]
                )
                row["pass2_disagrees"] = bool(row["included"] and not row["pass2_verbatim"])

            kept = sum(1 for r in rows if r["included"])
            disagreed = sum(1 for r in rows if r.get("pass2_disagrees"))
            total_rows += len(rows)
            included_rows += kept
            pass2_disagreements += disagreed

            staging = {
                "spec_version": "1.0.0",
                "run_id": run_id,
                "model": args.model,
                "temperature": 0,
                "source_doc_id": source_doc_id,
                "act_title": act_title,
                "pdf_file_name": pdf_path.name,
                "section_key": section_key,
                "focus_chars": len(focus_text),
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "row_count": len(rows),
                "included_count": kept,
                "pass2_disagreements": disagreed,
                "rows": rows,
                "focus_text": focus_text,
                "note": "Staging only. Never promoted without Phase 5 human review.",
            }
            out_path.write_text(json.dumps(staging, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            print(
                f"  - {section_key:<16} rows={len(rows):<3} included={kept:<3} "
                f"calls={budget.calls} ~${budget.usd:.2f}"
            )
            log["sections"].append(
                {
                    "source_doc_id": source_doc_id,
                    "section_key": section_key,
                    "status": "ok",
                    "focus_chars": len(focus_text),
                    "row_count": len(rows),
                    "included_count": kept,
                    "pass1_tokens": meta,
                    "staging_path": out_path.relative_to(REPO_ROOT).as_posix(),
                }
            )

    log["totals"] = {
        "sections_with_focus": total_sections,
        "sections_skipped_empty_focus": skipped_sections,
        "rows_extracted": total_rows,
        "rows_included": included_rows,
        "pass2_disagreements": pass2_disagreements,
    }
    _write_log(log, budget, run_id)

    print("\n=== Phase 4 summary ===")
    print(f"  sections with focus : {total_sections}")
    print(f"  sections skipped    : {skipped_sections}")
    print(f"  rows extracted      : {total_rows}")
    print(f"  rows included       : {included_rows}")
    print(f"  pass2 disagreements : {pass2_disagreements} (review flag, not a veto)")
    print(f"  API calls           : {budget.calls}")
    print(f"  estimated cost      : ~${budget.usd:.2f}")
    return 0


def _write_log(log: dict[str, Any], budget: Budget, run_id: str) -> None:
    log["usage"] = {
        "api_calls": budget.calls,
        "prompt_tokens": budget.prompt_tokens,
        "completion_tokens": budget.completion_tokens,
        "estimated_usd": round(budget.usd, 4),
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"run_{run_id}.json"
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nRun log: {path.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    raise SystemExit(main())
