#!/usr/bin/env python3
"""Relief Interview Phase 4 accuracy gate — $0, no API calls.

Builds candidate individual rate ladders for the two engine-supported years
straight out of the Phase 4 staging rows, then diffs them against the Phase 5.2
ontology packs. A mismatch on YA 2024/25 or 2025/26 is the Phase 4 hard stop:
if the pipeline cannot reproduce the years we already know, its output for the
older years is not trustworthy either.

Ladder selection is entirely extractor-derived:

    included First Schedule rate_band rows for individuals
      -> grouped by the `effective_from` the model read off the Act
      -> kept only if they form a complete ladder (0 -> open-ended, contiguous)
      -> for each YA, the latest ladder effective on or before 1 April of that YA

The consolidated Act is used only as a read-only cross-check and never feeds a
catalog.

Usage:
  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase4_accuracy.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "models" / "adaptive-tax" / "relief-interview"
EXTRACTED_DIR = OUT_ROOT / "extracted"
RATES_DIR = OUT_ROOT / "rates"
HARVEST_PATH = OUT_ROOT / "harvest" / "commencement_records.json"
ONTOLOGY_DIR = REPO_ROOT / "models" / "adaptive-tax" / "ontology"
MANIFEST_PATH = REPO_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"
REPORT_PATH = REPO_ROOT / "docs" / "reports" / "relief_interview_phase4_accuracy.md"

# The two years the existing calculate() engine supports, hence the two years
# whose rates we can check against an independently reviewed pack.
GATE_YEARS: dict[str, date] = {
    "2024_25": date(2024, 4, 1),
    "2025_26": date(2025, 4, 1),
}

CONSOLIDATED_DOC_ID = "ird-consolidated-2025"
BOUNDARY_TOLERANCE = 1  # "500,000" vs "500,001" band-edge styles


def ya_display(ya: str) -> str:
    return ya.replace("_", "/")


def _as_int(value: Any) -> int | None:
    text = str(value or "").strip().replace(",", "")
    return int(text) if text.isdigit() else None


def _as_rate(value: Any) -> float | None:
    text = str(value or "").strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Load staging + fallback commencement dates
# --------------------------------------------------------------------------


def load_staging() -> list[dict[str, Any]]:
    # Only per-section staging files; "__" separates source_doc_id from section.
    files = sorted(f for f in EXTRACTED_DIR.glob("*__*.json"))
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def load_act_commencements() -> dict[str, str]:
    """Earliest Phase 1 commencement per Act, used when a table states no date."""
    if not HARVEST_PATH.is_file():
        return {}
    data = json.loads(HARVEST_PATH.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for act in data.get("acts", []):
        for record in act.get("records", []):
            sid = record.get("source_doc_id") or act.get("source_doc_id")
            iso = record.get("operation_date") or ""
            if not sid or not iso:
                continue
            if sid not in out or iso < out[sid]:
                out[sid] = iso
    return out


# --------------------------------------------------------------------------
# Ladder assembly
# --------------------------------------------------------------------------


def individual_band_rows(staging: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for doc in staging:
        if doc.get("section_key") != "First Schedule":
            continue
        for row in doc.get("rows", []):
            if row.get("row_kind") != "rate_band" or not row.get("included"):
                continue
            if not re.search(r"individual", str(row.get("applies_to", "")), re.IGNORECASE):
                continue
            lower = _as_int(row.get("lower"))
            rate = _as_rate(row.get("rate_percent"))
            if lower is None or rate is None:
                continue
            rows.append(
                {
                    "source_doc_id": doc["source_doc_id"],
                    "act_title": doc.get("act_title", ""),
                    "effective_from": str(row.get("effective_from", "")).strip(),
                    "lower": lower,
                    "upper": _as_int(row.get("upper")),
                    "rate": rate,
                    "band_label": row.get("band_label", ""),
                    "section_ref": row.get("section_ref", ""),
                    "quote": row.get("quote", ""),
                    "quote_source": row.get("quote_source", ""),
                }
            )
    return rows


def build_ladders(
    rows: list[dict[str, Any]], commencements: dict[str, str]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        effective = row["effective_from"] or commencements.get(row["source_doc_id"], "")
        row = {**row, "resolved_effective_from": effective}
        groups.setdefault((row["source_doc_id"], effective), []).append(row)

    ladders: list[dict[str, Any]] = []
    for (source_doc_id, effective), members in groups.items():
        bands = sorted(members, key=lambda r: r["lower"])
        problems: list[str] = []
        if bands[0]["lower"] > BOUNDARY_TOLERANCE:
            problems.append(f"does not start at 0 (starts at {bands[0]['lower']})")
        for prev, nxt in zip(bands, bands[1:]):
            if prev["upper"] is None:
                problems.append(f"open-ended band at {prev['lower']} is not the last band")
            elif abs(prev["upper"] - nxt["lower"]) > BOUNDARY_TOLERANCE:
                problems.append(f"gap between {prev['upper']} and {nxt['lower']}")
        if bands[-1]["upper"] is not None:
            problems.append(f"top band is capped at {bands[-1]['upper']}")

        ladders.append(
            {
                "source_doc_id": source_doc_id,
                "act_title": bands[0]["act_title"],
                "effective_from": effective,
                "effective_from_source": (
                    "extracted" if members[0]["effective_from"] else "phase1_commencement"
                ),
                "band_count": len(bands),
                "complete": not problems,
                "problems": problems,
                "bands": bands,
            }
        )
    return sorted(ladders, key=lambda ladder: (ladder["effective_from"], ladder["source_doc_id"]))


def select_ladder(ladders: list[dict[str, Any]], ya_start: date) -> dict[str, Any] | None:
    eligible = []
    for ladder in ladders:
        if not ladder["complete"] or not ladder["effective_from"]:
            continue
        try:
            effective = datetime.strptime(ladder["effective_from"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if effective <= ya_start:
            eligible.append((effective, ladder))
    if not eligible:
        return None
    eligible.sort(key=lambda pair: pair[0])
    return eligible[-1][1]


# --------------------------------------------------------------------------
# Diff vs ontology pack
# --------------------------------------------------------------------------


def load_ontology_pack(ya: str) -> dict[str, Any] | None:
    path = ONTOLOGY_DIR / f"rate_bands_{ya}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def diff_against_ontology(ladder: dict[str, Any], pack: dict[str, Any]) -> dict[str, Any]:
    expected = sorted(pack["bands"], key=lambda b: b["lower"])
    actual = ladder["bands"]
    diffs: list[str] = []

    if len(expected) != len(actual):
        diffs.append(f"band count: ontology {len(expected)} vs extracted {len(actual)}")

    for idx in range(max(len(expected), len(actual))):
        exp = expected[idx] if idx < len(expected) else None
        act = actual[idx] if idx < len(actual) else None
        if exp is None:
            diffs.append(f"band {idx + 1}: extra extracted band {act['lower']}..{act['upper']}")
            continue
        if act is None:
            diffs.append(f"band {idx + 1}: missing band {exp['lower']}..{exp['upper']}")
            continue
        if abs(int(exp["lower"]) - act["lower"]) > BOUNDARY_TOLERANCE:
            diffs.append(f"band {idx + 1} lower: ontology {exp['lower']} vs extracted {act['lower']}")
        exp_upper, act_upper = exp.get("upper"), act["upper"]
        if (exp_upper is None) != (act_upper is None):
            diffs.append(f"band {idx + 1} upper: ontology {exp_upper} vs extracted {act_upper}")
        elif exp_upper is not None and abs(int(exp_upper) - act_upper) > BOUNDARY_TOLERANCE:
            diffs.append(f"band {idx + 1} upper: ontology {exp_upper} vs extracted {act_upper}")
        exp_rate = round(float(exp["rate"]) * 100, 6)
        if abs(exp_rate - act["rate"]) > 1e-6:
            diffs.append(f"band {idx + 1} rate: ontology {exp_rate}% vs extracted {act['rate']}%")

    return {"match": not diffs, "diffs": diffs}


# --------------------------------------------------------------------------
# Consolidated cross-check (read-only, never written into a catalog)
# --------------------------------------------------------------------------


def consolidated_crosscheck(ladder: dict[str, Any]) -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    doc = next(
        (d for d in manifest["documents"] if d["source_doc_id"] == CONSOLIDATED_DOC_ID), None
    )
    if doc is None:
        return {"available": False, "note": "consolidated doc not in manifest"}
    path = REPO_ROOT / manifest["pdf_root"] / doc["file_name"]
    if not path.is_file():
        return {"available": False, "note": f"missing {path.name}"}

    import fitz

    pdf = fitz.open(str(path))
    try:
        text = "\n".join((page.get_text("text") or "") for page in pdf)
    finally:
        pdf.close()
    normalized = re.sub(r"\s+", " ", text)

    found: list[str] = []
    absent: list[str] = []
    for band in ladder["bands"]:
        needle = f"{band['lower']:,}"
        (found if needle in normalized else absent).append(needle)
    return {
        "available": True,
        "file_name": doc["file_name"],
        "boundaries_found": found,
        "boundaries_absent": absent,
        "note": "Read-only corroboration. Consolidated text never feeds a catalog.",
    }


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def candidate_pack(ya: str, ladder: dict[str, Any]) -> dict[str, Any]:
    return {
        "spec_version": "1.0.0",
        "phase": 4,
        "assessment_year": ya_display(ya),
        "currency": "LKR",
        "status": "candidate_pending_phase5_review",
        "note": (
            "Extractor-only candidate built from Phase 4 staging. Not promoted to "
            "rates/{ya}.json — that is Phase 5 human review."
        ),
        "source_doc_id": ladder["source_doc_id"],
        "act_title": ladder["act_title"],
        "effective_from": ladder["effective_from"],
        "effective_from_source": ladder["effective_from_source"],
        "bands": [
            {
                "band_index": idx + 1,
                "lower": band["lower"],
                "upper": band["upper"],
                "rate_percent": band["rate"],
                "band_label": band["band_label"],
                "act_name": ladder["act_title"],
                "section_ref": band["section_ref"],
                "quote": band["quote"],
                "quote_source": band["quote_source"],
                "source_doc_id": ladder["source_doc_id"],
            }
            for idx, band in enumerate(ladder["bands"])
        ],
    }


def render_report(results: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    verdict = "PASS" if results["gate_pass"] else "FAIL"
    add("# Relief Interview — Phase 4 accuracy report")
    add("")
    add(f"- Generated: {results['generated_at']}")
    add(f"- Gate verdict: **{verdict}**")
    add(f"- Staging files: {results['staging_files']}")
    add(f"- Rows included in staging: {results['rows_included']} of {results['rows_total']}")
    add("- API cost of this check: $0 (no model calls)")
    add("")
    add("## What this gate does")
    add("")
    add(
        "Phase 4 has to earn the right to be trusted on the older years. The only "
        "years with an independently reviewed rate pack are 2024/25 and 2025/26, so "
        "the pipeline is required to reproduce those two from the Acts alone. If it "
        "cannot, its 2018/19-2023/24 output is not trustworthy either and Phase 8 "
        "must not be written."
    )
    add("")

    for ya, entry in results["years"].items():
        add(f"## YA {ya_display(ya)}")
        add("")
        if entry.get("ladder") is None:
            add(f"- Result: **FAIL** — {entry['reason']}")
            add("")
            continue
        ladder = entry["ladder"]
        status = "MATCH" if entry["diff"]["match"] else "MISMATCH"
        add(f"- Result: **{status}**")
        add(f"- Selected ladder: `{ladder['source_doc_id']}` effective {ladder['effective_from']}")
        add(f"- Effective date came from: {ladder['effective_from_source']}")
        add(f"- Ontology pack: `models/adaptive-tax/ontology/rate_bands_{ya}.json`")
        add("")
        add("| # | Lower | Upper | Extracted | Ontology | Quote source |")
        add("|---|-------|-------|-----------|----------|--------------|")
        pack_bands = sorted(entry["pack"]["bands"], key=lambda b: b["lower"])
        for idx, band in enumerate(ladder["bands"]):
            exp = pack_bands[idx] if idx < len(pack_bands) else None
            exp_rate = f"{round(float(exp['rate']) * 100, 4)}%" if exp else "—"
            upper = f"{band['upper']:,}" if band["upper"] is not None else "no limit"
            add(
                f"| {idx + 1} | {band['lower']:,} | {upper} | {band['rate']}% | "
                f"{exp_rate} | {band['quote_source']} |"
            )
        add("")
        if entry["diff"]["diffs"]:
            add("Differences:")
            add("")
            for diff in entry["diff"]["diffs"]:
                add(f"- {diff}")
            add("")
        cross = entry.get("consolidated")
        if cross and cross.get("available"):
            found = len(cross["boundaries_found"])
            total = found + len(cross["boundaries_absent"])
            add(
                f"Consolidated cross-check (`{cross['file_name']}`, read-only): "
                f"{found}/{total} band boundaries corroborated."
            )
            add("")

    add("## Ladders discovered")
    add("")
    add("| Act | Effective from | Bands | Complete | Notes |")
    add("|-----|----------------|-------|----------|-------|")
    for ladder in results["ladders"]:
        note = "; ".join(ladder["problems"]) if ladder["problems"] else "contiguous 0 → open"
        effective = ladder["effective_from"] or "(not stated)"
        add(
            f"| `{ladder['source_doc_id']}` | {effective} | {ladder['band_count']} | "
            f"{'yes' if ladder['complete'] else 'no'} | {note} |"
        )
    add("")
    add("## Phase 8 gate")
    add("")
    if results["gate_pass"]:
        add(
            "Both engine-supported years reproduce their ontology pack exactly from "
            "Act text, so the extraction pipeline is cleared. Phase 5 human review is "
            "still required before any catalog is promoted."
        )
    else:
        add(
            "At least one engine-supported year does not reproduce its ontology pack. "
            "Per the plan this is a hard stop: **do not write Phase 8**. Re-extract the "
            "affected sections; do not hand-type the missing values."
        )
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 4 accuracy gate (no API calls)")
    parser.add_argument("--write-candidates", action="store_true", default=True)
    args = parser.parse_args(argv)

    staging = load_staging()
    if not staging:
        print("No staging files found — run relief_interview_phase4_extract.py first", file=sys.stderr)
        return 2

    rows_total = sum(doc.get("row_count", 0) for doc in staging)
    rows_included = sum(doc.get("included_count", 0) for doc in staging)
    commencements = load_act_commencements()
    ladders = build_ladders(individual_band_rows(staging), commencements)

    results: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "staging_files": len(staging),
        "rows_total": rows_total,
        "rows_included": rows_included,
        "ladders": ladders,
        "years": {},
        "gate_pass": True,
    }

    print("=== Phase 4 accuracy gate (no API calls) ===")
    print(f"  staging files : {len(staging)}")
    print(f"  rows included : {rows_included} of {rows_total}")
    print(f"  ladders found : {len(ladders)} ({sum(1 for l in ladders if l['complete'])} complete)")
    print()

    for ya, ya_start in GATE_YEARS.items():
        pack = load_ontology_pack(ya)
        if pack is None:
            results["years"][ya] = {"ladder": None, "reason": f"no ontology pack for {ya}"}
            results["gate_pass"] = False
            print(f"  {ya_display(ya)}: FAIL — no ontology pack")
            continue

        ladder = select_ladder(ladders, ya_start)
        if ladder is None:
            results["years"][ya] = {
                "ladder": None,
                "reason": "no complete individual rate ladder effective on or before "
                f"{ya_start.isoformat()}",
            }
            results["gate_pass"] = False
            print(f"  {ya_display(ya)}: FAIL — no complete ladder effective by {ya_start}")
            continue

        diff = diff_against_ontology(ladder, pack)
        entry = {
            "ladder": ladder,
            "pack": pack,
            "diff": diff,
            "consolidated": consolidated_crosscheck(ladder),
        }
        results["years"][ya] = entry
        if not diff["match"]:
            results["gate_pass"] = False

        status = "MATCH" if diff["match"] else "MISMATCH"
        print(
            f"  {ya_display(ya)}: {status} — {ladder['source_doc_id']} "
            f"effective {ladder['effective_from']} ({ladder['band_count']} bands)"
        )
        for line in diff["diffs"]:
            print(f"      - {line}")

        if args.write_candidates:
            out = EXTRACTED_DIR / f"candidate_rates_{ya}.json"
            out.write_text(
                json.dumps(candidate_pack(ya, ladder), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(results) + "\n", encoding="utf-8")

    json_path = EXTRACTED_DIR / "accuracy_result.json"
    json_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")

    # rates/{ya}.json stays whatever Phase 1 left; promotion is Phase 5's job.
    still_empty = [
        p.name for p in sorted(RATES_DIR.glob("*.json")) if not json.loads(p.read_text(encoding="utf-8")).get("bands")
    ]

    print()
    print(f"  report        : {REPORT_PATH.relative_to(REPO_ROOT).as_posix()}")
    print(f"  result json   : {json_path.relative_to(REPO_ROOT).as_posix()}")
    print(f"  rates/ still unpromoted (expected until Phase 5): {len(still_empty)} files")
    print()
    print(f"  GATE: {'PASS' if results['gate_pass'] else 'FAIL — do not write Phase 8'}")
    return 0 if results["gate_pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
