#!/usr/bin/env python3
"""Phase 1 audit of adaptive-tax corpus_v1.jsonl (read-only; does not overwrite corpus).

Writes:
  data/processed/adaptive-tax/audit/corpus_audit_chunks.jsonl
  data/processed/adaptive-tax/audit/corpus_audit_summary.json

Digit-aware section detection: ``subsection (5)`` alone is NOT Section 5.
``Section 5`` must not match ``Section 52``.

Example::

  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_audit_corpus.py
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_audit_corpus.py --archive
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent

REQUIRED_SECTION_KEYS: tuple[str, ...] = (
    "2",
    "5",
    "6",
    "7",
    "8",
    "11",
    "16",
    "52",
    "89",
    "first_schedule",
)

REQUIRED_UIDS = {
    "2": "ird-ira-2017-base::sec::section_2",
    "5": "ird-ira-2017-base::sec::section_5",
    "6": "ird-ira-2017-base::sec::section_6",
    "7": "ird-ira-2017-base::sec::section_7",
    "8": "ird-ira-2017-base::sec::section_8",
    "11": "ird-ira-2017-base::sec::section_11",
    "16": "ird-ira-2017-base::sec::section_16",
    "52": "ird-ira-2017-base::sec::section_52",
    "89": "ird-ira-2017-base::sec::section_89",
    "first_schedule": "ird-ira-2017-base::sec::first_schedule",
}

# Explicit "Section N" / "First Schedule" — not "subsection (N)".
_SECTION_HEADING = re.compile(
    r"(?i)\b(?:section|sec\.?)\s+(\d+[A-Za-z]?)\b(?!\s*\()"
)
_SECTION_HEADING_STRICT = re.compile(r"(?i)\bsection\s+(\d+[A-Za-z]?)\b")
_SUBSECTION_ONLY = re.compile(r"(?i)\bsub-?section\s*\(\s*(\d+[A-Za-z]?)\s*\)")
_FIRST_SCHEDULE = re.compile(r"(?i)\bfirst\s+schedule\b")
_SCHEDULE_GENERIC = re.compile(
    r"(?i)\b(?:second|third|fourth|fifth|sixth)\s+schedule\b|\bschedule\s+\d+\b"
)
_TOC_MARKERS = re.compile(
    r"\barrangement\s+of\s+sections\b|\btable\s+of\s+contents\b|"
    r"\bsection\s+title\s+page\b|\bcontents\b",
    re.I,
)
_HEADER_FOOTER = re.compile(
    r"^(?:inland\s+revenue\s+(?:\(amendment\)\s+)?act[^\n]{0,80})$|"
    r"\bprinted\s+on\s+the\s+order\s+of\s+government\b|"
    r"\bgazette\s+of\s+the\s+democratic\b|"
    r"\bcertified\s+on\b",
    re.I | re.M,
)
_CROSS_REF = re.compile(
    r"\bas\s+(?:referred|defined|provided)\s+in\s+section\b|"
    r"\bin\s+accordance\s+with\s+section\b|"
    r"\bsubject\s+to\s+(?:the\s+provisions\s+of\s+)?section\b|"
    r"\bunder\s+section\s+\d+",
    re.I,
)
_OPERATIVE_HINTS = re.compile(
    r"\b(?:shall|means|includes|deduct|chargeable|assessable|relief|"
    r"qualifying\s+payment|employment\s+income|taxable\s+income|"
    r"carry\s*(?:-|\s*)forward|rate\s+of\s+tax)\b",
    re.I,
)


def _normalize_section_ref_field(section_ref: Any) -> list[str]:
    if section_ref is None or section_ref == "":
        return []
    if isinstance(section_ref, list):
        return [str(x).strip() for x in section_ref if str(x).strip()]
    return [str(section_ref).strip()] if str(section_ref).strip() else []


def _digit_aware_section_nums_from_text(text: str) -> list[str]:
    """Primary section numbers from explicit Section N mentions (not subsection alone)."""
    found: list[str] = []
    seen: set[str] = set()
    for m in _SECTION_HEADING_STRICT.finditer(text or ""):
        num = m.group(1)
        # Skip if this match is inside "subsection (N)" context immediately before
        start = m.start()
        prefix = text[max(0, start - 12) : start].lower()
        if "subsection" in prefix or "sub-section" in prefix:
            continue
        key = num.upper() if num[-1:].isalpha() else num
        if key not in seen:
            seen.add(key)
            found.append(key)
    if _FIRST_SCHEDULE.search(text or ""):
        if "first_schedule" not in seen:
            found.append("first_schedule")
    return found


def _subsection_only_nums(text: str) -> list[str]:
    return [m.group(1) for m in _SUBSECTION_ONLY.finditer(text or "")]


def _section_keys_from_metadata(refs: list[str]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        low = ref.lower()
        if "first schedule" in low or "first_schedule" in low:
            if "first_schedule" not in seen:
                seen.add("first_schedule")
                keys.append("first_schedule")
            continue
        for m in re.finditer(r"(?i)(?:section|sec\.?)?\s*(\d+[a-z]?)\b", ref):
            num = m.group(1)
            # bare "Part II" etc. — skip non-section labels without digits in section context
            key = num.upper() if num[-1:].isalpha() else num
            if key not in seen:
                # Prefer when "section" appears in the ref string
                if "section" in low or re.fullmatch(r"\d+[A-Za-z]?", ref.strip()):
                    seen.add(key)
                    keys.append(key)
    return keys


def _looks_toc(text: str, section_ref: list[str]) -> bool:
    if _TOC_MARKERS.search(text or ""):
        return True
    # Arrangement-style: many "N. Title" short lines + page numbers
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) >= 8:
        dotted = sum(1 for ln in lines if re.match(r"^\d+[A-Za-z]?\.\s+\S+", ln))
        if dotted >= 5 and dotted / len(lines) >= 0.4:
            return True
    if section_ref and all(
        r.lower().startswith("part ") or r.lower() in ("part i", "part ii")
        for r in section_ref
    ):
        if "arrangement" in (text or "").lower() or "section title" in (text or "").lower():
            return True
    return False


def _looks_header_footer(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 40:
        return True
    if len(t) < 400 and _HEADER_FOOTER.search(t):
        return True
    # Mostly title/cover page
    if "parliament of the democratic" in t.lower() and len(t) < 900:
        return True
    return False


def _looks_cross_reference(text: str, detected_sections: list[str]) -> bool:
    if _CROSS_REF.search(text or ""):
        return True
    # Short chunk that only mentions a section in passing
    if detected_sections and len(text or "") < 280 and not _OPERATIVE_HINTS.search(text or ""):
        return True
    return False


def _looks_operative(text: str, *, is_toc: bool, is_header: bool) -> bool:
    if is_toc or is_header:
        return False
    if len(text or "") < 80:
        return False
    return bool(_OPERATIVE_HINTS.search(text or ""))


def audit_chunk(row: dict[str, Any]) -> dict[str, Any]:
    text = row.get("text") if isinstance(row.get("text"), str) else ""
    refs = _normalize_section_ref_field(row.get("section_ref"))
    detected = _digit_aware_section_nums_from_text(text)
    subsection_only = _subsection_only_nums(text)
    meta_keys = _section_keys_from_metadata(refs)
    is_toc = _looks_toc(text, refs)
    is_header = _looks_header_footer(text)
    is_xref = _looks_cross_reference(text, detected)
    looks_op = _looks_operative(text, is_toc=is_toc, is_header=is_header)

    applicable_yas = row.get("applicable_assessment_years") or row.get("applicable_yas")
    if isinstance(applicable_yas, str) and applicable_yas.strip():
        ya_list = [p for p in re.split(r"[|,]", applicable_yas) if p.strip()]
    elif isinstance(applicable_yas, list):
        ya_list = [str(x).strip() for x in applicable_yas if str(x).strip()]
    else:
        ya_list = []

    return {
        "chunk_id": row.get("chunk_id"),
        "source_doc_id": row.get("source_doc_id"),
        "page": row.get("page"),
        "current_section_ref": refs if refs else None,
        "has_section_ref": bool(refs),
        "assessment_year_metadata": ya_list or None,
        "publication_date": row.get("publication_date") or None,
        "effective_start_date": row.get("effective_start_date") or None,
        "effective_end_date": row.get("effective_end_date") or None,
        "document_type": row.get("instrument_type") or row.get("doc_type"),
        "instrument_type": row.get("instrument_type"),
        "doc_type": row.get("doc_type"),
        "text_length": len(text),
        "detected_section_refs": detected,
        "metadata_section_keys": meta_keys,
        "subsection_only_refs": subsection_only,
        "schedule_mentions": sorted(
            {m.group(0) for m in _SCHEDULE_GENERIC.finditer(text)}
            | ({"First Schedule"} if _FIRST_SCHEDULE.search(text) else set())
        ),
        "is_toc": is_toc,
        "is_header_footer": is_header,
        "is_cross_reference": is_xref and not looks_op,
        "looks_operative": looks_op,
        "pdf_outline_breadcrumb": row.get("pdf_outline_breadcrumb"),
    }


def _coverage_for_key(
    audits: list[dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    meta_hits = 0
    text_hits = 0
    either = 0
    operative = 0
    for a in audits:
        in_meta = key in (a.get("metadata_section_keys") or [])
        in_text = key in (a.get("detected_section_refs") or [])
        # also metadata current_section_ref digit-aware via metadata_section_keys
        if in_meta:
            meta_hits += 1
        if in_text:
            text_hits += 1
        if in_meta or in_text:
            either += 1
            if a.get("looks_operative"):
                operative += 1
    status = "missing"
    if either == 0:
        status = "missing"
    elif meta_hits == 0:
        status = "text_only"
    elif operative == 0:
        status = "weak"
    else:
        status = "ok"
    return {
        "section_key": key,
        "section_uid": REQUIRED_UIDS[key],
        "metadata_hits": meta_hits,
        "text_hits": text_hits,
        "either_hits": either,
        "operative_hits": operative,
        "status": status,
    }


def build_summary(
    audits: list[dict[str, Any]],
    *,
    corpus_path: Path,
    total_rows: int,
) -> dict[str, Any]:
    with_ref = sum(1 for a in audits if a.get("has_section_ref"))
    without_ref = total_rows - with_ref
    by_doc: Counter[str] = Counter()
    by_section: Counter[str] = Counter()
    by_ya: Counter[str] = Counter()
    toc_n = sum(1 for a in audits if a.get("is_toc"))
    header_n = sum(1 for a in audits if a.get("is_header_footer"))
    xref_n = sum(1 for a in audits if a.get("is_cross_reference"))
    op_n = sum(1 for a in audits if a.get("looks_operative"))

    for a in audits:
        by_doc[str(a.get("source_doc_id") or "(none)")] += 1
        for k in a.get("detected_section_refs") or []:
            by_section[str(k)] += 1
        for k in a.get("metadata_section_keys") or []:
            by_section[f"meta:{k}"] += 1
        yas = a.get("assessment_year_metadata") or []
        if not yas:
            by_ya["(none)"] += 1
        else:
            for y in yas:
                by_ya[str(y)] += 1

    required = [_coverage_for_key(audits, k) for k in REQUIRED_SECTION_KEYS]
    missing = [r for r in required if r["status"] == "missing"]
    weak = [r for r in required if r["status"] in ("weak", "text_only")]

    return {
        "corpus_path": str(corpus_path.as_posix()),
        "total_chunks": total_rows,
        "chunks_with_section_ref": with_ref,
        "chunks_without_section_ref": without_ref,
        "section_ref_coverage_pct": round(100.0 * with_ref / total_rows, 2) if total_rows else 0.0,
        "chunks_by_source_document": dict(by_doc.most_common()),
        "chunks_by_detected_section": {
            k: v for k, v in by_section.most_common(80) if not str(k).startswith("meta:")
        },
        "chunks_by_metadata_section": {
            str(k)[5:]: v for k, v in by_section.most_common() if str(k).startswith("meta:")
        },
        "chunks_by_assessment_year": dict(by_ya.most_common()),
        "flag_counts": {
            "is_toc": toc_n,
            "is_header_footer": header_n,
            "is_cross_reference": xref_n,
            "looks_operative": op_n,
        },
        "required_sections": required,
        "missing_required_sections": [r["section_uid"] for r in missing],
        "weak_required_sections": [
            {"section_uid": r["section_uid"], "status": r["status"]} for r in weak
        ],
        "notes": [
            "Digit-aware: subsection (N) alone does not assign Section N.",
            "Section 5 must not be confused with Section 52.",
            "Assessment-year metadata is usually empty on the pre-section-aware corpus.",
            "This audit does not modify corpus_v1.jsonl.",
        ],
    }


def run_audit(
    *,
    corpus_jsonl: Path,
    out_dir: Path,
    archive: bool,
) -> dict[str, Any]:
    if not corpus_jsonl.is_file():
        raise FileNotFoundError(f"corpus not found: {corpus_jsonl}")

    out_dir.mkdir(parents=True, exist_ok=True)
    chunks_out = out_dir / "corpus_audit_chunks.jsonl"
    summary_out = out_dir / "corpus_audit_summary.json"

    audits: list[dict[str, Any]] = []
    with corpus_jsonl.open(encoding="utf-8") as fin, chunks_out.open(
        "w", encoding="utf-8"
    ) as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            audited = audit_chunk(row)
            audits.append(audited)
            fout.write(json.dumps(audited, ensure_ascii=False) + "\n")

    summary = build_summary(audits, corpus_path=corpus_jsonl, total_rows=len(audits))
    summary_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    archive_path: Path | None = None
    if archive:
        archive_path = corpus_jsonl.with_name("corpus_v1.pre_section_aware.jsonl")
        if not archive_path.exists():
            shutil.copy2(corpus_jsonl, archive_path)
            summary["archived_to"] = str(archive_path.as_posix())
        else:
            summary["archived_to"] = str(archive_path.as_posix())
            summary["archive_note"] = "archive already existed; left unchanged"
        summary_out.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    summary["outputs"] = {
        "chunks": str(chunks_out.as_posix()),
        "summary": str(summary_out.as_posix()),
    }
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=_REPO / "data" / "processed" / "adaptive-tax" / "corpus_v1.jsonl",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_REPO / "data" / "processed" / "adaptive-tax" / "audit",
    )
    p.add_argument(
        "--archive",
        action="store_true",
        help="Copy corpus_v1.jsonl -> corpus_v1.pre_section_aware.jsonl if missing",
    )
    args = p.parse_args()

    summary = run_audit(
        corpus_jsonl=args.corpus_jsonl,
        out_dir=args.out_dir,
        archive=args.archive,
    )
    print(f"total_chunks={summary['total_chunks']}")
    print(
        f"with_section_ref={summary['chunks_with_section_ref']} "
        f"without={summary['chunks_without_section_ref']} "
        f"({summary['section_ref_coverage_pct']}%)"
    )
    print("required_sections:")
    for r in summary["required_sections"]:
        print(
            f"  {r['section_key']:15} status={r['status']:10} "
            f"meta={r['metadata_hits']} text={r['text_hits']} "
            f"operative={r['operative_hits']}"
        )
    print(f"wrote {summary['outputs']['chunks']}")
    print(f"wrote {summary['outputs']['summary']}")
    if summary.get("archived_to"):
        print(f"archived {summary['archived_to']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
