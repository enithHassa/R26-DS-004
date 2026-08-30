#!/usr/bin/env python3
"""Relief Interview Phase 1: path check → commencement harvest → YA report → empty skeletons.

Authority for PDF paths is models/adaptive-tax/corpus_manifest.json only
(source_doc_id → file_name → data/raw/adaptive-tax/{file_name}). Do not hardcode
filenames from the plan doc.

Usage (from repo root):

  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase1_commencement.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"
OUT_ROOT = REPO_ROOT / "models" / "adaptive-tax" / "relief-interview"
APPROVED_DIR = OUT_ROOT / "approved"
RATES_DIR = OUT_ROOT / "rates"
HARVEST_DIR = OUT_ROOT / "harvest"
REPORT_PATH = REPO_ROOT / "docs" / "reports" / "relief_interview_phase1_ya_mapping.md"
HARVEST_JSON = HARVEST_DIR / "commencement_records.json"

# Extraction corpus only (never Consolidated / Guide / ontology).
EXTRACT_SOURCE_DOC_IDS: tuple[str, ...] = (
    "ird-ira-2017-base",
    "ird-amend-2021-10",
    "ird-amend-2022-45",
    "ird-amend-2023-04",
    "ird-amend-2023-14",
    "ird-amend-2025-02",
    "ird-amend-2026-11",
)

HYPOTHESIS_YAS: tuple[str, ...] = (
    "2018_19",
    "2019_20",
    "2020_21",
    "2021_22",
    "2022_23",
    "2023_24",
    "2024_25",
    "2025_26",
)

# YA 2026/27 and later are out of scope for this feature.
MAX_IN_SCOPE_YA = "2025_26"

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass
class PathCheckRow:
    source_doc_id: str
    file_name: str
    resolved_path: str
    exists: bool


@dataclass
class CommencementRecord:
    source_doc_id: str
    act_title_hint: str
    section_ref: str
    operation_date: str  # ISO YYYY-MM-DD
    derived_assessment_year: str
    quote: str
    parse_kind: str  # column_iii_row | whole_act | table_blanket | short_title_clause


@dataclass
class ActHarvest:
    source_doc_id: str
    file_name: str
    pages_scanned: int
    records: list[CommencementRecord] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def confirm_pdf_paths(manifest: dict) -> tuple[list[PathCheckRow], dict[str, Path], list[str]]:
    """Resolve extract IDs via manifest file_name; fail on missing/mismatched files."""
    pdf_root = REPO_ROOT / manifest["pdf_root"]
    by_id = {d["source_doc_id"]: d for d in manifest["documents"]}
    rows: list[PathCheckRow] = []
    resolved: dict[str, Path] = {}
    errors: list[str] = []

    for sid in EXTRACT_SOURCE_DOC_IDS:
        if sid not in by_id:
            errors.append(f"source_doc_id missing from corpus_manifest.json: {sid}")
            rows.append(
                PathCheckRow(
                    source_doc_id=sid,
                    file_name="",
                    resolved_path="",
                    exists=False,
                )
            )
            continue
        file_name = by_id[sid]["file_name"]
        pdf_path = pdf_root / file_name
        exists = pdf_path.is_file()
        rows.append(
            PathCheckRow(
                source_doc_id=sid,
                file_name=file_name,
                resolved_path=str(pdf_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                exists=exists,
            )
        )
        if not exists:
            errors.append(
                f"PDF missing for {sid}: expected {pdf_path.as_posix()} "
                f"(from corpus_manifest file_name={file_name!r})"
            )
        else:
            resolved[sid] = pdf_path

    return rows, resolved, errors


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def ya_for_operation_date(d: date) -> str:
    """Sri Lanka YA containing date d: Apr 1 Y – Mar 31 Y+1 → Y_(Y+1)."""
    start_year = d.year if d.month >= 4 else d.year - 1
    return f"{start_year}_{str(start_year + 1)[-2:]}"


def parse_dotted_date(raw: str) -> date | None:
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw.strip())
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_month_name_date(text: str) -> date | None:
    m = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b",
        text,
        re.I,
    )
    if not m:
        return None
    month = MONTHS[m.group(1).lower()]
    day = int(m.group(2))
    year = int(m.group(3))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_pages_text(path: Path, max_pages: int) -> tuple[str, int]:
    """Scan early pages; extend a bit if short-title commencement not yet seen.

    Base Act (234 pages) places s.1 after the arrangement of sections (~page 13).
    """
    reader = PdfReader(str(path))
    total = len(reader.pages)
    target = min(max_pages, total)
    parts: list[str] = []
    for i in range(target):
        try:
            t = reader.pages[i].extract_text() or ""
        except Exception as exc:  # noqa: BLE001 — best-effort
            t = f"<!-- extract error: {exc} -->"
        parts.append(t)

    joined = "\n".join(parts)
    needs_more = not re.search(
        r"(?:comes|come|shall come)\s+into\s+operat",
        joined,
        re.I,
    ) and not re.search(r"column\s+iii", joined, re.I)
    # Arrangement-of-sections PDFs: keep reading until short-title page or hard cap.
    hard_cap = min(total, max(max_pages, 24))
    i = target
    while needs_more and i < hard_cap:
        try:
            t = reader.pages[i].extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            t = f"<!-- extract error: {exc} -->"
        parts.append(t)
        i += 1
        joined = "\n".join(parts)
        if re.search(r"(?:comes|come|shall come)\s+into\s+operat", joined, re.I):
            needs_more = False
        if re.search(r"column\s+iii", joined, re.I) and i >= max_pages:
            needs_more = False

    return "\n".join(parts), len(parts)


def find_column_iii_rows(text: str, source_doc_id: str, act_hint: str) -> list[CommencementRecord]:
    """Parse Column I/II/III style rows: section | amended | DD.MM.YYYY."""
    records: list[CommencementRecord] = []
    # Compact whitespace for row matching; keep original snippets via search.
    compact = normalize_ws(text)
    # Rows like: "3 37(1)( b) 01.04.2021" or "5 52 01.04.2025"
    pattern = re.compile(
        r"(?<!\d)(\d{1,3})\s+"
        r"([0-9A-Za-z().,\-\s]{1,40}?)\s+"
        r"(\d{1,2}\.\d{1,2}\.\d{4})(?!\d)"
    )
    if "column iii" not in compact.lower() and "date of operation" not in compact.lower():
        return records

    for m in pattern.finditer(compact):
        sec_of_act = m.group(1).strip()
        amended = normalize_ws(m.group(2))
        # Skip header-ish false positives
        if amended.lower() in {"of this act", "section of the principal"}:
            continue
        if "enactment" in amended.lower() and "amended" not in amended.lower():
            continue
        op = parse_dotted_date(m.group(3))
        if op is None:
            continue
        quote = m.group(0)[:220]
        ya = ya_for_operation_date(op)
        records.append(
            CommencementRecord(
                source_doc_id=source_doc_id,
                act_title_hint=act_hint,
                section_ref=f"s.{sec_of_act} amending {amended}",
                operation_date=op.isoformat(),
                derived_assessment_year=ya,
                quote=quote,
                parse_kind="column_iii_row",
            )
        )
    return records


def find_blanket_operation_dates(text: str, source_doc_id: str, act_hint: str) -> list[CommencementRecord]:
    """Whole-act / Table A/B blanket commencement clauses."""
    records: list[CommencementRecord] = []
    compact = normalize_ws(text)

    # PDF text often misspells "operation" as "operaton" (seen in IRA 2017 s.1).
    op_word = r"operat(?:ion|on)"
    date_tail = (
        r"(?:the )?(?:[A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?,? \d{4}|\d{1,2}\.\d{1,2}\.\d{4}|"
        r"1(?:st)?\s+of\s+[A-Za-z]+,?\s+\d{4})"
    )

    patterns: list[tuple[str, str, str]] = [
        (
            rf"(The provisions of this Act shall (?:come into {op_word}|be deemed to have come into {op_word}) on "
            rf"{date_tail})",
            "whole_act",
            "s.1 (whole Act)",
        ),
        (
            rf"(provisions of sections referred to in Table [\"“”'A-Za-z]+[^.]{{0,40}}shall be deemed to have come into "
            rf"{op_word} on {date_tail})",
            "table_blanket",
            "s.1 (table blanket)",
        ),
        (
            rf"(This Act[^.]{{0,120}}(?:shall come|comes) into {op_word} on {date_tail})",
            "short_title_clause",
            "s.1",
        ),
        (
            rf"((?:may be cited as|This Act may be cited as)[^.]{{0,160}}"
            rf"(?:shall come|comes) into {op_word} on {date_tail})",
            "short_title_clause",
            "s.1",
        ),
        (
            rf"(shall be deemed to have come into {op_word} on {date_tail})",
            "table_blanket",
            "s.1 (deemed operation)",
        ),
        (
            rf"((?:shall come|comes) into {op_word} on {date_tail})",
            "short_title_clause",
            "s.1",
        ),
    ]

    seen: set[tuple[str, str]] = set()
    for pat, kind, sec in patterns:
        for m in re.finditer(pat, compact, re.I):
            quote = normalize_ws(m.group(1))[:280]
            op = parse_month_name_date(quote) or parse_dotted_date(
                next(iter(re.findall(r"\d{1,2}\.\d{1,2}\.\d{4}", quote)), "")
            )
            if op is None:
                # "1st of April, 2018"
                m2 = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+of\s+([A-Za-z]+),?\s+(\d{4})", quote, re.I)
                if m2:
                    month = MONTHS.get(m2.group(2).lower())
                    if month:
                        try:
                            op = date(int(m2.group(3)), month, int(m2.group(1)))
                        except ValueError:
                            op = None
            if op is None:
                continue
            key = (op.isoformat(), kind)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                CommencementRecord(
                    source_doc_id=source_doc_id,
                    act_title_hint=act_hint,
                    section_ref=sec,
                    operation_date=op.isoformat(),
                    derived_assessment_year=ya_for_operation_date(op),
                    quote=quote,
                    parse_kind=kind,
                )
            )
    return records


def harvest_act(source_doc_id: str, pdf_path: Path, max_pages: int) -> ActHarvest:
    act_hint = pdf_path.stem
    text, n = extract_pages_text(pdf_path, max_pages=max_pages)
    harvest = ActHarvest(
        source_doc_id=source_doc_id,
        file_name=pdf_path.name,
        pages_scanned=n,
    )
    col = find_column_iii_rows(text, source_doc_id, act_hint)
    blanket = find_blanket_operation_dates(text, source_doc_id, act_hint)
    harvest.records.extend(col)
    harvest.records.extend(blanket)
    if not harvest.records:
        harvest.notes.append("No commencement / Column III dates recovered in scanned pages.")
    return harvest


def inclusive_ya_range(yas: set[str]) -> list[str]:
    if not yas:
        return []
    in_scope = sorted(y for y in yas if y <= MAX_IN_SCOPE_YA)
    if not in_scope:
        return []
    start = in_scope[0]
    end = in_scope[-1]
    # Expand contiguous YA keys from start..end using April-based years.
    start_y = int(start.split("_")[0])
    end_y = int(end.split("_")[0])
    out: list[str] = []
    for y in range(start_y, end_y + 1):
        key = f"{y}_{str(y + 1)[-2:]}"
        if key <= MAX_IN_SCOPE_YA:
            out.append(key)
    return out


def write_empty_skeletons(yas: list[str], dry_run: bool) -> list[str]:
    written: list[str] = []
    if dry_run:
        return written
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    RATES_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "proposed").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "extracted").mkdir(parents=True, exist_ok=True)

    for ya in yas:
        approved = {
            "spec_version": "1.0.0",
            "assessment_year": ya,
            "entries": [],
            "phase1_empty_skeleton": True,
            "notes": "Empty skeleton only. Live rows arrive via extract → verify → review promote.",
        }
        rates = {
            "spec_version": "1.0.0",
            "assessment_year": ya,
            "needs_manual_verification": True,
            "bands": [],
            "surcharges": [],
            "special_formulas": [],
            "phase1_empty_skeleton": True,
            "notes": "Empty skeleton only. No ontology/hand-typed seed.",
        }
        ap = APPROVED_DIR / f"{ya}.json"
        rp = RATES_DIR / f"{ya}.json"
        ap.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
        rp.write_text(json.dumps(rates, indent=2) + "\n", encoding="utf-8")
        written.append(str(ap.relative_to(REPO_ROOT)).replace("\\", "/"))
        written.append(str(rp.relative_to(REPO_ROOT)).replace("\\", "/"))
    return written


def render_report(
    path_rows: list[PathCheckRow],
    path_errors: list[str],
    harvests: list[ActHarvest],
    confirmed_yas: list[str],
    remapped: bool,
    skeleton_paths: list[str],
) -> str:
    lines: list[str] = [
        "# Relief Interview — Phase 1 YA mapping report",
        "",
        "**Generated by:** `scripts/relief_interview_phase1_commencement.py`",
        "**Path authority:** `models/adaptive-tax/corpus_manifest.json` (`source_doc_id` → `file_name`).",
        "",
        "## 1. PDF path check",
        "",
        "| source_doc_id | file_name (manifest) | path | exists |",
        "|---|---|---|---|",
    ]
    for r in path_rows:
        lines.append(
            f"| `{r.source_doc_id}` | `{r.file_name}` | `{r.resolved_path}` | "
            f"{'yes' if r.exists else '**NO**'} |"
        )
    lines.append("")
    if path_errors:
        lines.append("**Path check FAILED:**")
        for e in path_errors:
            lines.append(f"- {e}")
        lines.append("")
        lines.append("Harvest and skeletons were not written.")
        lines.append("")
        return "\n".join(lines) + "\n"

    lines.extend(["**Path check:** PASS", ""])
    lines.extend(
        [
            "## 2. Commencement / Column III harvest",
            "",
            "Dates below are recovered deterministically from early PDF pages "
            "(pypdf text). Quotes are lossy vs layout — use for YA mapping only.",
            "",
        ]
    )
    all_yas: set[str] = set()
    for h in harvests:
        lines.append(f"### `{h.source_doc_id}` (`{h.file_name}`, pages 1–{h.pages_scanned})")
        lines.append("")
        if h.notes:
            for n in h.notes:
                lines.append(f"- Note: {n}")
            lines.append("")
        if not h.records:
            lines.append("_No records._")
            lines.append("")
            continue
        lines.append("| section_ref | operation_date | derived YA | kind | quote (truncated) |")
        lines.append("|---|---|---|---|---|")
        for rec in h.records:
            all_yas.add(rec.derived_assessment_year)
            q = rec.quote.replace("|", "/")[:120]
            lines.append(
                f"| {rec.section_ref} | `{rec.operation_date}` | `{rec.derived_assessment_year}` | "
                f"`{rec.parse_kind}` | {q} |"
            )
        lines.append("")

    lines.extend(
        [
            "## 3. Derived assessment-year range",
            "",
            f"- **Hypothesis (plan):** `{', '.join(HYPOTHESIS_YAS)}`",
            f"- **Confirmed (harvest min→max, contiguous, capped at {MAX_IN_SCOPE_YA}):** "
            f"`{', '.join(confirmed_yas) if confirmed_yas else '(none)'}`",
            f"- **Raw YA keys seen on records:** "
            f"`{', '.join(sorted(all_yas)) if all_yas else '(none)'}`",
            f"- **Out of scope (seen but excluded):** any YA after `{MAX_IN_SCOPE_YA}` "
            f"(e.g. `2026_27` from Act 11/2026 Column III) is listed in raw keys only.",
            "",
        ]
    )

    if remapped:
        lines.extend(
            [
                "## 4. HARD STOP — YA mapping remapped",
                "",
                "Harvested range **differs** from the 2018/19–2025/26 hypothesis.",
                "**Do not start Phases 2–7** until a human accepts the confirmed mapping above.",
                "",
                f"- Only in hypothesis: "
                f"`{', '.join(y for y in HYPOTHESIS_YAS if y not in confirmed_yas) or '(none)'}`",
                f"- Only in harvest: "
                f"`{', '.join(y for y in confirmed_yas if y not in HYPOTHESIS_YAS) or '(none)'}`",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## 4. Gate — YA mapping matches hypothesis",
                "",
                "Confirmed range equals `2018_19` … `2025_26`. Phase 1 YA-mapping stop is **cleared** "
                "for proceeding to Phase 2 (subject to human review of this report).",
                "",
            ]
        )

    lines.extend(["## 5. Empty skeletons written", ""])
    if skeleton_paths:
        for p in skeleton_paths:
            lines.append(f"- `{p}`")
    else:
        lines.append("- _(none)_")
    lines.append("")
    lines.extend(
        [
            "## 6. Constraints respected",
            "",
            "- No numeric seed from ontology, fixtures, or hand-typing.",
            "- Consolidated / Guide / ontology PDFs were not opened for extraction.",
            "- `approved/{ya}.json` and `rates/{ya}.json` contain empty arrays only.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relief Interview Phase 1 commencement harvest")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=16,
        help="Initial early pages to scan per Act (default 16; may extend to 24)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Path-check + harvest + report to stdout only; write no skeletons",
    )
    args = parser.parse_args(argv)

    if not MANIFEST_PATH.is_file():
        print(f"ERROR: corpus_manifest.json not found at {MANIFEST_PATH}", file=sys.stderr)
        return 2

    manifest = load_manifest(MANIFEST_PATH)
    path_rows, resolved, path_errors = confirm_pdf_paths(manifest)

    print("=== Phase 1 path check ===")
    for r in path_rows:
        status = "OK" if r.exists else "MISSING"
        print(f"  [{status}] {r.source_doc_id} -> {r.file_name}")

    if path_errors:
        print("\nPATH CHECK FAILED — stopping before any PDF parse.")
        for e in path_errors:
            print(f"  - {e}", file=sys.stderr)
        report = render_report(path_rows, path_errors, [], [], True, [])
        if not args.dry_run:
            REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
            REPORT_PATH.write_text(report, encoding="utf-8")
            print(f"Wrote failure report: {REPORT_PATH}")
        else:
            print(report)
        return 1

    print("\n=== Phase 1 commencement harvest ===")
    harvests: list[ActHarvest] = []
    for sid in EXTRACT_SOURCE_DOC_IDS:
        h = harvest_act(sid, resolved[sid], max_pages=args.max_pages)
        harvests.append(h)
        print(f"  {sid}: {len(h.records)} record(s), pages={h.pages_scanned}")

    raw_yas: set[str] = set()
    for h in harvests:
        for rec in h.records:
            raw_yas.add(rec.derived_assessment_year)

    confirmed_yas = inclusive_ya_range(raw_yas)
    remapped = confirmed_yas != list(HYPOTHESIS_YAS)

    skeleton_paths: list[str] = []
    if not args.dry_run and confirmed_yas:
        HARVEST_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "spec_version": "1.0.0",
            "phase": 1,
            "extract_source_doc_ids": list(EXTRACT_SOURCE_DOC_IDS),
            "hypothesis_yas": list(HYPOTHESIS_YAS),
            "confirmed_yas": confirmed_yas,
            "remapped_vs_hypothesis": remapped,
            "path_check": [asdict(r) for r in path_rows],
            "acts": [
                {
                    "source_doc_id": h.source_doc_id,
                    "file_name": h.file_name,
                    "pages_scanned": h.pages_scanned,
                    "notes": h.notes,
                    "records": [asdict(r) for r in h.records],
                }
                for h in harvests
            ],
        }
        HARVEST_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        skeleton_paths = write_empty_skeletons(confirmed_yas, dry_run=False)

    report = render_report(path_rows, path_errors, harvests, confirmed_yas, remapped, skeleton_paths)
    if args.dry_run:
        print(report)
    else:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"\nWrote report: {REPORT_PATH}")
        print(f"Wrote harvest JSON: {HARVEST_JSON}")
        print(f"Wrote {len(skeleton_paths)} skeleton files under {OUT_ROOT}")

    if remapped:
        print(
            "\nHARD STOP: YA mapping remapped vs 2018_19…2025_26. "
            "Do not start Phases 2–7 until accepted.",
            file=sys.stderr,
        )
        return 3

    print("\nPhase 1 YA-mapping gate: CLEARED (matches hypothesis).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
