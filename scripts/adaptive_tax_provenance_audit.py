#!/usr/bin/env python3
"""System-wide provenance audit — READ-ONLY investigation.

Builds Stage A inventory, re-extracts from Act PDFs (openai harvest),
classifies findings, and writes audit artifacts + markdown report.

Does NOT modify rule_engine.py, provenance.py, param_store.py,
provenance_bootstrap_v1.json, or ontology param packs.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
_COMP = _REPO / "backend" / "comp-adaptive-tax"
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_COMP) not in sys.path:
    sys.path.insert(0, str(_COMP))

AUDIT_DIR = _REPO / "data" / "processed" / "adaptive-tax" / "audit"
HARVEST_DIR = AUDIT_DIR / "stage_b_harvest"
TEXT_DIR = _REPO / "data" / "processed" / "adaptive-tax" / "text"
RAW_DIR = _REPO / "data" / "raw" / "adaptive-tax"
ONTOLOGY = _REPO / "models" / "adaptive-tax" / "ontology"
FIXTURES = _REPO / "models" / "adaptive-tax" / "fixtures"
MANIFEST = _REPO / "models" / "adaptive-tax" / "corpus_manifest.json"
BOOTSTRAP = FIXTURES / "provenance_bootstrap_v1.json"
REPORT_PATH = _REPO / "docs" / "reports" / "provenance_audit_2026-08-18.md"

# Harvest matrix: section_key -> list of source_doc_ids
HARVEST_MATRIX: dict[str, list[str]] = {
    "5": ["ird-ira-2017-base"],
    "6": ["ird-ira-2017-base"],
    "7": ["ird-ira-2017-base"],
    "8": ["ird-ira-2017-base"],
    "11": ["ird-ira-2017-base"],
    "16": ["ird-ira-2017-base"],
    "89": ["ird-ira-2017-base"],
    "52": ["ird-ira-2017-base", "ird-amend-2025-02", "ird-amend-2026-11"],
    "first_schedule": ["ird-ira-2017-base", "ird-amend-2025-02", "ird-consolidated-2025"],
    "personal_relief": ["ird-ira-2017-base", "ird-amend-2025-02"],
    "donations": ["ird-ira-2017-base"],
    "fifth_schedule": ["ird-ira-2017-base", "ird-amend-2021-10"],
}

# Extra search patterns for sections not in section_targets_v1.json
SECTION_PATTERNS: dict[str, list[str]] = {
    "7": ["Section 7", "Investment income"],
    "8": ["Section 8", "other sources"],
    "11": ["Section 11"],
    "16": ["Section 16", "Capital allowances"],
    "89": ["Section 89"],
    "fifth_schedule": ["Fifth Schedule", "FIFTH SCHEDULE"],
}

HARDCODED_CONSTANTS: list[dict[str, Any]] = [
    {
        "row_id": "engine:rent_relief_pct",
        "concept_id": "rent_relief",
        "claimed_value": "25% (0.25 of included inv_rents)",
        "claimed_section": "Fifth Schedule 2(c)",
        "claimed_source_doc_id": "ird-ira-2017-base",
        "rule_source_id": "bootstrap:rent_relief",
        "source_files": ["backend/comp-adaptive-tax/adaptive_tax_app/services/rule_engine.py"],
        "assessment_years": ["2024_25", "2025_26"],
    },
    {
        "row_id": "engine:solar_cap",
        "concept_id": "solar_panel_relief",
        "claimed_value": "600000",
        "claimed_section": "Fifth Schedule 2(g)",
        "claimed_source_doc_id": "ird-amend-2021-10",
        "rule_source_id": "bootstrap:solar_panel_relief",
        "source_files": ["backend/comp-adaptive-tax/adaptive_tax_app/services/rule_engine.py"],
        "assessment_years": ["2024_25", "2025_26"],
    },
    {
        "row_id": "engine:qp_charitable",
        "concept_id": "qp_approved_charitable",
        "claimed_value": "min(claimed, 75000, floor(assessable/3))",
        "claimed_section": "Fifth Schedule 1(a)",
        "claimed_source_doc_id": "ird-ira-2017-base",
        "rule_source_id": "bootstrap:qp_approved_charitable",
        "source_files": ["backend/comp-adaptive-tax/adaptive_tax_app/services/qp_categories.py"],
        "assessment_years": ["2024_25", "2025_26"],
    },
    {
        "row_id": "engine:qp_film",
        "concept_id": "qp_film_production",
        "claimed_value": "5000000 (cost gate)",
        "claimed_section": "Fifth Schedule 1(f)(i)",
        "claimed_source_doc_id": "ird-amend-2021-10",
        "rule_source_id": "bootstrap:qp_film_production",
        "source_files": ["backend/comp-adaptive-tax/adaptive_tax_app/services/qp_categories.py"],
        "assessment_years": ["2024_25", "2025_26"],
    },
    {
        "row_id": "engine:qp_cinema_construction",
        "concept_id": "qp_cinema_construction",
        "claimed_value": "25000000",
        "claimed_section": "Fifth Schedule 1(f)(ii)",
        "claimed_source_doc_id": "ird-amend-2021-10",
        "rule_source_id": "bootstrap:qp_cinema_construction",
        "source_files": ["backend/comp-adaptive-tax/adaptive_tax_app/services/qp_categories.py"],
        "assessment_years": ["2024_25", "2025_26"],
    },
    {
        "row_id": "engine:qp_cinema_upgrading",
        "concept_id": "qp_cinema_upgrading",
        "claimed_value": "10000000 + one-third TI restriction",
        "claimed_section": "Fifth Schedule 1(f)(iii)",
        "claimed_source_doc_id": "ird-amend-2021-10",
        "rule_source_id": "bootstrap:qp_cinema_upgrading",
        "source_files": ["backend/comp-adaptive-tax/adaptive_tax_app/services/qp_categories.py"],
        "assessment_years": ["2024_25", "2025_26"],
    },
]

SEVERITY_ORDER = {5: 0, 3: 1, 4: 2, 2: 3, 6: 4, 1: 5}


@dataclass
class InventoryRow:
    row_id: str
    concept_id: str
    claimed_value: str
    claimed_section: str
    claimed_source_doc_id: str
    quote_text: str | None
    rule_source_id: str | None
    source_files: list[str]
    assessment_years: list[str]
    row_type: str  # param | bootstrap | ontology | engine
    executable: bool = True


@dataclass
class Classification:
    row_id: str
    category: int
    category_name: str
    confidence: str
    system_claim: str
    extraction_finding: str
    files_to_change: list[str]
    notes: str = ""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_by_id() -> dict[str, dict]:
    doc = _load_json(MANIFEST)
    return {d["source_doc_id"]: d for d in doc.get("documents", [])}


def _bootstrap_by_id() -> dict[str, dict]:
    doc = _load_json(BOOTSTRAP)
    return {r["id"]: r for r in doc.get("rules", [])}


def _quote_for(rule_source_id: str | None, bootstrap: dict[str, dict]) -> str | None:
    if not rule_source_id:
        return None
    row = bootstrap.get(rule_source_id)
    return row.get("source_quote") if row else None


def build_stage_a_inventory() -> list[InventoryRow]:
    bootstrap = _bootstrap_by_id()
    rows: list[InventoryRow] = []

    # Relief packs
    for fname in (
        "relief_caps_2024_25.json",
        "relief_caps_2025_26.json",
        "relief_caps_pre_amend_2025.json",
    ):
        path = ONTOLOGY / fname
        doc = _load_json(path)
        ya = str(doc.get("assessment_year", "")).replace("/", "_")
        for relief in doc.get("reliefs", []):
            cap = relief.get("cap_amount")
            cap_pct = relief.get("cap_pct_of_assessable")
            if cap is not None:
                val = str(cap)
            elif cap_pct is not None:
                val = f"{cap_pct * 100}%"
            elif relief.get("concept_id") == "rent_relief":
                val = "25% of included rents (engine constant)"
            else:
                continue
            rid = relief.get("rule_source_id")
            rows.append(
                InventoryRow(
                    row_id=f"param:{fname}:{relief.get('concept_id')}",
                    concept_id=str(relief.get("concept_id")),
                    claimed_value=val,
                    claimed_section=str(relief.get("section_ref", "")),
                    claimed_source_doc_id=str(relief.get("source_doc_id", "")),
                    quote_text=_quote_for(rid, bootstrap),
                    rule_source_id=rid,
                    source_files=[f"models/adaptive-tax/ontology/{fname}"],
                    assessment_years=[ya] if ya else [],
                    row_type="param",
                )
            )

    # Rate bands
    for fname, ya in (
        ("rate_bands_2024_25.json", "2024_25"),
        ("rate_bands_2025_26.json", "2025_26"),
    ):
        path = ONTOLOGY / fname
        doc = _load_json(path)
        bands_desc = "; ".join(
            f"{b['lower']}-{b.get('upper', 'inf')}@{b['rate']}" for b in doc.get("bands", [])
        )
        rid = doc["bands"][0]["rule_source_id"] if doc.get("bands") else None
        rows.append(
            InventoryRow(
                row_id=f"param:{fname}:first_schedule_rates",
                concept_id="first_schedule_rates",
                claimed_value=bands_desc,
                claimed_section="First Schedule",
                claimed_source_doc_id=str(doc.get("source_doc_id", "")),
                quote_text=_quote_for(rid, bootstrap),
                rule_source_id=rid,
                source_files=[f"models/adaptive-tax/ontology/{fname}"],
                assessment_years=[ya],
                row_type="param",
            )
        )

    # Bootstrap quotes (all rules)
    for rule in _load_json(BOOTSTRAP).get("rules", []):
        rows.append(
            InventoryRow(
                row_id=f"bootstrap:{rule['id']}",
                concept_id=str(rule.get("concept_id", "")),
                claimed_value="(quote-only)" if not rule.get("executable", True) else "see handler",
                claimed_section=str(rule.get("section", "")),
                claimed_source_doc_id=str(rule.get("source_doc_id", "")),
                quote_text=str(rule.get("source_quote", "")),
                rule_source_id=str(rule.get("id", "")),
                source_files=["models/adaptive-tax/fixtures/provenance_bootstrap_v1.json"],
                assessment_years=list(rule.get("assessment_years") or []),
                row_type="bootstrap",
                executable=bool(rule.get("executable", True)),
            )
        )

    # Ontology LIMITED_BY edges
    for fname in ("mvp_calc_edges_seed.jsonl", "calculation_edges_full.jsonl"):
        path = ONTOLOGY / fname
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            edge = json.loads(line)
            if edge.get("rel_type") != "LIMITED_BY":
                continue
            rid = edge.get("rule_source_id")
            rows.append(
                InventoryRow(
                    row_id=f"ontology:{fname}:{edge.get('from_id')}->{edge.get('to_id')}",
                    concept_id=f"{edge.get('from_id')} LIMITED_BY {edge.get('to_id')}",
                    claimed_value=str(edge.get("source_note", "")),
                    claimed_section="(ontology edge)",
                    claimed_source_doc_id="",
                    quote_text=_quote_for(rid, bootstrap),
                    rule_source_id=rid,
                    source_files=[f"models/adaptive-tax/ontology/{fname}"],
                    assessment_years=["2024_25", "2025_26"],
                    row_type="ontology",
                )
            )

    # Stale aggregate QP cap edges
    for fname in ("mvp_calc_edges_seed.jsonl", "calculation_edges_full.jsonl"):
        path = ONTOLOGY / fname
        for line in path.read_text(encoding="utf-8").splitlines():
            if "sec52_qualifying_payment_cap" in line:
                edge = json.loads(line)
                rows.append(
                    InventoryRow(
                        row_id=f"ontology:stale:{fname}:sec52_qualifying_payment_cap",
                        concept_id="sec52_qualifying_payment_cap (stale)",
                        claimed_value="aggregate QP cap edge (removed from engine)",
                        claimed_section="52",
                        claimed_source_doc_id="ird-ira-2017-base",
                        quote_text=None,
                        rule_source_id=edge.get("rule_source_id"),
                        source_files=[f"models/adaptive-tax/ontology/{fname}"],
                        assessment_years=["2024_25", "2025_26"],
                        row_type="ontology",
                        executable=False,
                    )
                )

    # Hardcoded engine constants
    for hc in HARDCODED_CONSTANTS:
        rows.append(
            InventoryRow(
                row_id=hc["row_id"],
                concept_id=hc["concept_id"],
                claimed_value=hc["claimed_value"],
                claimed_section=hc["claimed_section"],
                claimed_source_doc_id=hc["claimed_source_doc_id"],
                quote_text=_quote_for(hc["rule_source_id"], bootstrap),
                rule_source_id=hc["rule_source_id"],
                source_files=hc["source_files"],
                assessment_years=hc["assessment_years"],
                row_type="engine",
            )
        )

    # Runtime overlay if present
    override = _REPO / "data" / "processed" / "adaptive-tax" / "active_relief_caps.json"
    if override.is_file():
        doc = _load_json(override)
        for upd in doc.get("relief_updates", []):
            rows.append(
                InventoryRow(
                    row_id=f"override:relief:{upd.get('concept_id')}",
                    concept_id=str(upd.get("concept_id")),
                    claimed_value=str(upd.get("cap_amount", upd)),
                    claimed_section=str(upd.get("section_ref", "")),
                    claimed_source_doc_id=str(upd.get("source_doc_id", "")),
                    quote_text=None,
                    rule_source_id=doc.get("rule_source_id"),
                    source_files=["data/processed/adaptive-tax/active_relief_caps.json"],
                    assessment_years=[],
                    row_type="override",
                )
            )

    return rows


def sync_pdfs(source: Path) -> list[str]:
    cmd = [
        sys.executable,
        str(_REPO / "scripts" / "adaptive_tax_sync_ird_docs.py"),
        "--source",
        str(source),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)
    lines = (result.stdout + result.stderr).strip().splitlines()
    return lines


def build_corpus() -> list[str]:
    cmd = [sys.executable, str(_REPO / "scripts" / "adaptive_tax_build_corpus.py")]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_REPO)
    return (result.stdout + result.stderr).strip().splitlines()


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _resolve_text(source_doc_id: str) -> str:
    manifest = _manifest_by_id()
    doc = manifest.get(source_doc_id, {})
    fname = doc.get("file_name", "")
    candidates = [
        TEXT_DIR / f"{source_doc_id}.txt",
        TEXT_DIR / f"{fname.replace('.pdf', '.txt')}",
    ]
    for cand in sorted(TEXT_DIR.glob("*.txt")):
        stem = cand.stem.lower()
        if source_doc_id.replace("-", "_") in stem.replace("-", "_"):
            candidates.append(cand)
        if fname and fname.replace(".pdf", "").lower().replace(".", "_") in stem.replace(".", "_"):
            candidates.append(cand)
    seen: set[Path] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if cand.is_file():
            return cand.read_text(encoding="utf-8", errors="replace")
    raise FileNotFoundError(f"No text for {source_doc_id} under {TEXT_DIR}")


def _focus_text(full_text: str, section_key: str) -> str:
    from adaptive_tax_app.services.pdf_extract import focus_section_text

    patterns = SECTION_PATTERNS.get(section_key)
    focused = focus_section_text(
        full_text, section_key, search_patterns=patterns
    )
    return focused.focused_text


def run_quote_checks(rows: list[InventoryRow]) -> dict[str, Any]:
    from adaptive_tax_app.services.gpt_extract import _normalize_ws as norm

    results: list[dict] = []
    for row in rows:
        if not row.quote_text or row.row_type == "ontology":
            continue
        doc_id = row.claimed_source_doc_id
        if not doc_id:
            continue
        try:
            text = _resolve_text(doc_id)
            focused = _focus_text(text, _section_key_for_row(row))
            haystack = norm(focused)
            needle = norm(row.quote_text)
            found_in_focus = bool(needle and needle in haystack)
            found_in_full = bool(needle and needle in norm(text))
            results.append(
                {
                    "row_id": row.row_id,
                    "rule_source_id": row.rule_source_id,
                    "source_doc_id": doc_id,
                    "quote_substring_in_focus": found_in_focus,
                    "quote_substring_in_full_doc": found_in_full,
                    "quote_preview": (row.quote_text or "")[:120],
                }
            )
        except FileNotFoundError as exc:
            results.append(
                {
                    "row_id": row.row_id,
                    "rule_source_id": row.rule_source_id,
                    "source_doc_id": doc_id,
                    "error": str(exc),
                    "quote_substring_in_focus": False,
                    "quote_substring_in_full_doc": False,
                }
            )
    return {"checks": results}


def _section_key_for_row(row: InventoryRow) -> str:
    sec = (row.claimed_section or "").lower()
    if "first schedule" in sec:
        return "first_schedule"
    if "fifth" in sec:
        return "fifth_schedule"
    m = re.match(r"^(\d+)", sec)
    if m:
        return m.group(1)
    if row.concept_id in ("personal_relief",):
        return "personal_relief"
    if "donation" in row.concept_id or "qp_" in row.concept_id:
        return "donations" if "donation_cap" in row.concept_id else "fifth_schedule"
    return "52"


def run_harvest(skip_openai: bool = False) -> dict[str, Any]:
    from adaptive_tax_app.services.gpt_extract import extract_rules
    from adaptive_tax_app.services.pdf_extract import focus_section_text

    manifest = _manifest_by_id()
    outputs: list[dict] = []
    HARVEST_DIR.mkdir(parents=True, exist_ok=True)

    for section_key, doc_ids in HARVEST_MATRIX.items():
        for doc_id in doc_ids:
            out_path = HARVEST_DIR / f"{section_key}_{doc_id}.json"
            if out_path.is_file() and skip_openai:
                outputs.append(json.loads(out_path.read_text(encoding="utf-8")))
                continue
            try:
                text = _resolve_text(doc_id)
            except FileNotFoundError as exc:
                outputs.append(
                    {
                        "section_key": section_key,
                        "source_doc_id": doc_id,
                        "error": str(exc),
                    }
                )
                continue

            patterns = SECTION_PATTERNS.get(section_key)
            focused = focus_section_text(text, section_key, search_patterns=patterns)
            entry: dict[str, Any] = {
                "section_key": section_key,
                "source_doc_id": doc_id,
                "pdf_file": manifest.get(doc_id, {}).get("file_name"),
                "char_count_focused": focused.char_count_focused,
                "truncated": focused.truncated,
                "focused_text_preview": focused.focused_text[:3000],
                "focused_fallback": "fallback" in focused.focused_text.lower(),
            }

            if skip_openai:
                entry["skipped_openai"] = True
            else:
                result = extract_rules(
                    focused.focused_text,
                    amends_section_candidates=focused.amends_section_candidates,
                    harvest_mode="section",
                    section_key=section_key,
                )
                entry.update(
                    {
                        "mode": result.mode,
                        "model_name": result.model_name,
                        "warnings": result.warnings,
                        "rules": [r.model_dump(mode="json") for r in result.rules],
                    }
                )

            out_path.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
            outputs.append(entry)

    return {"harvest_runs": len(outputs), "outputs": outputs}


def _extract_numerics_from_harvest(harvest: dict[str, Any]) -> list[dict]:
    nums: list[dict] = []
    for entry in harvest.get("outputs", []):
        for rule in entry.get("rules") or []:
            nums.append(
                {
                    "section_key": entry.get("section_key"),
                    "source_doc_id": entry.get("source_doc_id"),
                    "concept_id": rule.get("concept_id"),
                    "threshold": rule.get("threshold"),
                    "maximum": rule.get("maximum"),
                    "formula": rule.get("formula"),
                    "source_quote": (rule.get("source_quote") or "")[:200],
                    "section": rule.get("section"),
                }
            )
    return nums


def _files_to_change(row: InventoryRow, category: int) -> list[str]:
    if category == 1:
        return []
    files = list(row.source_files)
    if row.rule_source_id and "provenance_bootstrap" not in " ".join(files):
        if category in (2, 4, 5):
            files.append("models/adaptive-tax/fixtures/provenance_bootstrap_v1.json")
    if row.row_type == "engine" and category in (3, 5):
        files.extend(row.source_files)
    if row.row_type == "param" and category == 3:
        files.extend(row.source_files)
    if "sec52_qualifying_payment_cap" in row.concept_id:
        files.extend(
            [
                "models/adaptive-tax/ontology/mvp_calc_edges_seed.jsonl",
                "models/adaptive-tax/ontology/calculation_edges_full.jsonl",
            ]
        )
    return sorted(set(files))


def classify_rows(
    rows: list[InventoryRow],
    quote_checks: dict[str, Any],
    harvest: dict[str, Any],
) -> list[Classification]:
    check_by_row = {c["row_id"]: c for c in quote_checks.get("checks", [])}
    numerics = _extract_numerics_from_harvest(harvest)
    classifications: list[Classification] = []

    for row in rows:
        cat, conf, finding, notes = _classify_one(row, check_by_row, numerics, harvest)
        classifications.append(
            Classification(
                row_id=row.row_id,
                category=cat,
                category_name=_cat_name(cat),
                confidence=conf,
                system_claim=_format_claim(row),
                extraction_finding=finding,
                files_to_change=_files_to_change(row, cat),
                notes=notes,
            )
        )
    classifications.sort(key=lambda c: (SEVERITY_ORDER.get(c.category, 9), c.row_id))
    return classifications


def _cat_name(cat: int) -> str:
    return {
        1: "MATCH",
        2: "QUOTE MISMATCH ONLY",
        3: "VALUE MISMATCH",
        4: "SECTION/ACT MISATTRIBUTION",
        5: "NO CORRESPONDING ACT TEXT FOUND",
        6: "UNABLE TO VERIFY",
    }.get(cat, "UNKNOWN")


def _format_claim(row: InventoryRow) -> str:
    parts = [
        f"value={row.claimed_value}",
        f"section={row.claimed_section}",
        f"source_doc_id={row.claimed_source_doc_id}",
    ]
    if row.quote_text:
        parts.append(f"quote={row.quote_text[:100]}...")
    return "; ".join(parts)


def _classify_one(
    row: InventoryRow,
    check_by_row: dict[str, dict],
    numerics: list[dict],
    harvest: dict[str, Any],
) -> tuple[int, str, str, str]:
    """Conservative single-category assignment."""
    notes = ""

    # Stale aggregate cap
    if "sec52_qualifying_payment_cap" in row.concept_id:
        return (
            5,
            "high",
            "Aggregate Sec 52 QP cap was removed from engine (Path B); ontology edge remains",
            "Stale COVERS_RELIEF edge references removed concept",
        )

    # Non-executable bootstrap
    if row.row_type == "bootstrap" and not row.executable:
        chk = check_by_row.get(row.row_id)
        if chk and chk.get("quote_substring_in_full_doc"):
            return 1, "high", "Non-executable quote found verbatim in full Act text", ""
        if chk and not chk.get("quote_substring_in_full_doc"):
            return 2, "medium", "Non-executable structural quote not verbatim in claimed PDF", ""
        return 6, "low", "Non-executable rule — quote check inconclusive", ""

    chk = check_by_row.get(row.row_id)
    quote_ok_focus = chk.get("quote_substring_in_focus") if chk else None
    quote_ok_full = chk.get("quote_substring_in_full_doc") if chk else None

    # Known high-risk: carry-forward attribution
    if row.rule_source_id == "bootstrap:sec52_carry_forward_2025_26":
        alt_docs = ["ird-amend-2025-02", "ird-amend-2026-11", "ird-ira-2017-base"]
        found_in: list[str] = []
        for doc_id in alt_docs:
            try:
                text = _resolve_text(doc_id)
                if _normalize_ws(row.quote_text or "") in _normalize_ws(text):
                    found_in.append(doc_id)
            except FileNotFoundError:
                pass
        if found_in and row.claimed_source_doc_id not in found_in:
            return (
                4,
                "high",
                f"Quote found in {found_in} but claimed source is {row.claimed_source_doc_id}",
                "Prior QP investigation flagged Act 11/2026 vs 02/2025 attribution",
            )
        if not found_in:
            return 5, "high", "Carry-forward quote not found in any checked Act PDF", ""

    # Quote-only bootstrap rows (no numeric)
    if row.row_type == "bootstrap" and row.claimed_value in ("(quote-only)", "see handler"):
        if quote_ok_full:
            return 1, "high", "Quote verbatim in claimed source PDF (full doc)", ""
        if quote_ok_focus:
            return 1, "medium", "Quote verbatim in focused section window", ""
        if quote_ok_full is False:
            # Check other official PDFs
            any_other = _quote_in_any_official_pdf(row.quote_text or "")
            if any_other:
                return 4, "medium", f"Quote found in {any_other} but not claimed {row.claimed_source_doc_id}", ""
            return 2, "medium", "Quote not verbatim substring of claimed PDF — likely paraphrase", ""
        return 6, "low", "Could not verify quote — text missing", ""

    # Numeric param / engine rows
    if row.row_type in ("param", "engine", "ontology", "override"):
        numeric_evidence = _find_numeric_evidence(row, numerics, harvest)
        value_match = numeric_evidence.get("value_match")
        value_mismatch = numeric_evidence.get("value_mismatch")
        act_text = numeric_evidence.get("act_text", "")

        if value_mismatch:
            return 3, numeric_evidence.get("confidence", "medium"), act_text, numeric_evidence.get("notes", "")

        if quote_ok_full is False and row.quote_text:
            if value_match:
                return 2, "high", f"Numeric value corroborated; quote not verbatim. Act: {act_text[:200]}", ""
            any_other = _quote_in_any_official_pdf(row.quote_text)
            if any_other and any_other != row.claimed_source_doc_id:
                return 4, "medium", f"Quote in {any_other}; numeric evidence: {act_text[:150]}", ""
            if not _numeric_in_focus(row, harvest):
                return 5, "medium", f"Claimed numeric not found in harvest; quote also non-verbatim. {act_text[:150]}", ""
            return 2, "medium", f"Quote paraphrase; numeric appears supported. {act_text[:150]}", ""

        if value_match and (quote_ok_full or quote_ok_focus or not row.quote_text):
            return 1, "high", act_text[:300], ""

        if not numeric_evidence.get("searched"):
            return 6, "low", "Harvest missing or inconclusive for this row", ""

        return 6, "medium", act_text[:300] or "Extraction inconclusive — manual review needed", notes

    return 6, "low", "Unclassified — default to unable to verify", ""


def _quote_in_any_official_pdf(quote: str) -> str | None:
    if not quote.strip():
        return None
    needle = _normalize_ws(quote)
    for doc_id in _manifest_by_id():
        if doc_id in ("ird-guide-ira", "ird-calc-ontology-v5"):
            continue
        try:
            text = _resolve_text(doc_id)
            if needle in _normalize_ws(text):
                return doc_id
        except FileNotFoundError:
            continue
    return None


def _numeric_in_focus(row: InventoryRow, harvest: dict[str, Any]) -> bool:
    targets = _numeric_targets(row)
    if not targets:
        return False
    for entry in harvest.get("outputs", []):
        if entry.get("source_doc_id") != row.claimed_source_doc_id:
            continue
        preview = _normalize_ws(entry.get("focused_text_preview", ""))
        for t in targets:
            if t in preview:
                return True
    return False


def _numeric_targets(row: InventoryRow) -> list[str]:
    val = row.claimed_value.lower()
    targets: list[str] = []
    for num in re.findall(r"\d{3,}", val.replace(",", "")):
        targets.append(num)
    if "25%" in val or "0.25" in val:
        targets.extend(["twenty five", "25 per", "25%"])
    if "one-third" in val or "one third" in val:
        targets.extend(["one-third", "one third", "1/3"])
    if "1,200,000" in row.claimed_value or row.claimed_value == "1200000":
        targets.extend(["1,200,000", "1200000", "one million two hundred"])
    if "1,800,000" in row.claimed_value or "1800000" in row.claimed_value:
        targets.extend(["1,800,000", "1800000", "one million eight hundred"])
    if "600000" in val or "600,000" in val:
        targets.extend(["600,000", "600000", "six hundred thousand"])
    if "75000" in val.replace(",", "") or "75,000" in val:
        targets.extend(["75,000", "75000", "seventy five thousand"])
    if "5000000" in val.replace(",", ""):
        targets.extend(["five million", "5,000,000"])
    if "25000000" in val.replace(",", ""):
        targets.extend(["twenty five million", "25,000,000"])
    if "10000000" in val.replace(",", ""):
        targets.extend(["ten million", "10,000,000"])
    # rate bands
    for rate in ("0.06", "0.12", "0.18", "0.24", "0.30", "0.36"):
        if rate.replace("0.", "") in val or rate in val:
            targets.append(rate.replace("0.", "") + " per")
    return targets


def _find_numeric_evidence(
    row: InventoryRow,
    numerics: list[dict],
    harvest: dict[str, Any],
) -> dict[str, Any]:
    targets = _numeric_targets(row)
    section_key = _section_key_for_row(row)
    relevant_harvest = [
        e
        for e in harvest.get("outputs", [])
        if e.get("source_doc_id") == row.claimed_source_doc_id
        and e.get("section_key") == section_key
    ]

    act_snippets: list[str] = []
    value_match = False
    value_mismatch = False
    notes = ""

    for entry in relevant_harvest:
        preview = entry.get("focused_text_preview", "")
        for t in targets:
            if t.lower() in _normalize_ws(preview):
                value_match = True
                act_snippets.append(preview[max(0, preview.lower().find(t.lower()) - 80) :][:250])

    for n in numerics:
        if n.get("source_doc_id") != row.claimed_source_doc_id:
            continue
        if section_key not in (n.get("section_key") or "") and n.get("section_key") != section_key:
            if row.concept_id not in (n.get("concept_id") or ""):
                continue
        for field in ("threshold", "maximum", "formula"):
            fv = str(n.get(field) or "")
            if fv and any(t in fv for t in targets if t.isdigit()):
                value_match = True
                act_snippets.append(f"Extracted {field}={fv}: {(n.get('source_quote') or '')[:120]}")

    # Personal relief cross-check
    if "personal_relief" in row.concept_id and "1800000" in row.claimed_value.replace(",", ""):
        for doc_id in ("ird-amend-2025-02", "ird-ira-2017-base"):
            try:
                text = _resolve_text(doc_id)
                if "1,800,000" in text or "1800000" in text.replace(",", ""):
                    value_match = True
                    act_snippets.append(f"Found 1.8M in {doc_id}")
                elif doc_id == "ird-ira-2017-base" and ("1,200,000" in text or "1200000" in text):
                    notes = "Base Act has 1.2M; 1.8M expected from amendment"
            except FileNotFoundError:
                pass

    # First schedule 2025/26 — 12% band removed
    if row.concept_id == "first_schedule_rates" and "2025_26" in row.assessment_years:
        try:
            text = _resolve_text("ird-amend-2025-02")
            if "12" in text and "first schedule" in text.lower():
                if "12% bracket removed" in row.claimed_value or "0.12" not in row.claimed_value:
                    value_match = True
                    act_snippets.append("2025/26 bands omit 12% — matches param pack")
        except FileNotFoundError:
            pass

    return {
        "searched": bool(relevant_harvest or numerics),
        "value_match": value_match,
        "value_mismatch": value_mismatch,
        "act_text": " | ".join(act_snippets[:3]) if act_snippets else "(no numeric snippet in harvest)",
        "confidence": "high" if value_match and act_snippets else "medium",
        "notes": notes,
    }


def write_report(
    rows: list[InventoryRow],
    classifications: list[Classification],
    quote_checks: dict[str, Any],
    harvest: dict[str, Any],
    sync_log: list[str],
    corpus_log: list[str],
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    by_cat: dict[int, int] = {}
    for c in classifications:
        by_cat[c.category] = by_cat.get(c.category, 0) + 1

    non_match = [c for c in classifications if c.category != 1]

    lines: list[str] = [
        "# System-wide Provenance Audit Report",
        "",
        f"**Date:** {date.today().isoformat()}  ",
        "**Mode:** READ-ONLY investigation — no fixture or engine changes made.",
        "",
        "## Executive summary",
        "",
        "| Category | Count |",
        "|----------|-------|",
    ]
    for cat in (5, 3, 4, 2, 6, 1):
        name = _cat_name(cat)
        lines.append(f"| {cat} — {name} | {by_cat.get(cat, 0)} |")
    lines.extend(
        [
            "",
            f"**Total inventory rows:** {len(rows)}  ",
            f"**Non-MATCH findings:** {len(non_match)}  ",
            "",
            "### Highest-severity items (categories 5, 3, 4)",
            "",
        ]
    )
    for c in non_match:
        if c.category in (5, 3, 4):
            lines.append(
                f"- **{c.row_id}** — Cat {c.category} ({c.category_name}), "
                f"confidence={c.confidence}: {c.extraction_finding[:200]}"
            )

    lines.extend(["", "## Findings table (non-MATCH)", ""])
    lines.append(
        "| Row | Concept | Category | Confidence | System claim | Extraction finding | Files to change |"
    )
    lines.append("|-----|---------|----------|------------|--------------|-------------------|-----------------|")
    for c in non_match:
        row = next((r for r in rows if r.row_id == c.row_id), None)
        concept = row.concept_id if row else ""
        claim = c.system_claim.replace("|", "/")[:80]
        finding = c.extraction_finding.replace("|", "/")[:100]
        files = ", ".join(c.files_to_change[:2])
        lines.append(
            f"| {c.row_id} | {concept} | {c.category} | {c.confidence} | {claim} | {finding} | {files} |"
        )

    lines.extend(["", "## MATCH appendix (category 1)", ""])
    match_rows = [c for c in classifications if c.category == 1]
    for c in match_rows[:30]:
        lines.append(f"- {c.row_id}: {c.extraction_finding[:100]}")
    if len(match_rows) > 30:
        lines.append(f"- … and {len(match_rows) - 30} more MATCH rows")

    lines.extend(
        [
            "",
            "## Stage A inventory (consolidated checklist)",
            "",
            "| concept_id | claimed_value | claimed_section | source_doc_id | rule_source_id | files |",
            "|------------|---------------|-----------------|---------------|----------------|-------|",
        ]
    )
    seen: set[str] = set()
    for row in rows:
        if row.row_type not in ("param", "engine") or row.row_id in seen:
            continue
        seen.add(row.row_id)
        val = str(row.claimed_value).replace("|", "/")[:60]
        lines.append(
            f"| {row.concept_id} | {val} | {row.claimed_section} | "
            f"{row.claimed_source_doc_id} | {row.rule_source_id} | {row.source_files[0]} |"
        )

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "### PDF sync",
            "```",
            *sync_log[:15],
            "```",
            "",
            "### Corpus build",
            "```",
            *corpus_log[-10:],
            "```",
            "",
            "### Extraction",
            "- `COMP_ADAPTIVE_TAX_EXTRACTION_MODE=openai`",
            "- Section harvest via `focus_section_text` + `extract_rules(harvest_mode=section)`",
            f"- {harvest.get('harvest_runs', 0)} harvest runs persisted under `data/processed/adaptive-tax/audit/stage_b_harvest/`",
            "",
            "### Limitations",
            "- Classification is conservative; category 6 used when OCR/harvest inconclusive.",
            "- Amendment upload path not used; section harvest used for base operative text.",
            "- Guide PDF excluded from primary SoT.",
            "",
            "## Stage E — Recurring-amendment process check",
            "",
            "### E1. End-to-end new Act pipeline",
            "",
            "**Partially supported.** `scripts/adaptive_tax_section_harvest.py` can re-extract",
            "section-by-section from a new PDF with OpenAI, but output goes to",
            "`harvest_pending/*.json` and is **not auto-applied** to param packs or bootstrap.",
            "`section_targets_v1.json` omits Fifth Schedule and Secs 7/8/11/16/89.",
            "",
            "The amendment API (`upload → extract → review → approve`) writes Postgres",
            "`rule_source` and optional `active_relief_caps.json` for personal relief, rate bands,",
            "and donation cap only. `write_sec52_override_from_rules` is deprecated (no-op).",
            "**`provenance.py` does not load approved Postgres rules** — calculate() quotes still",
            "come from `provenance_bootstrap_v1.json`.",
            "",
            "### E2. Bypass paths (root cause of QP-class bugs)",
            "",
            "| Bypass | Location | Risk |",
            "|--------|----------|------|",
            "| Bootstrap quotes | `provenance_bootstrap_v1.json` | Hand-typed quotes bypass review; drives strict provenance |",
            "| Param packs | `relief_caps_*.json`, `rate_bands_*.json` | Direct numeric edits with `manual_seed` / `act_verified` |",
            "| Engine constants | `qp_categories.py`, `rule_engine.py` | No JSON, no pipeline |",
            "| Ontology edges | `mvp_calc_edges_seed.jsonl`, `*_harvest_v1.json` | Manual seed → `calculation_edges_full.jsonl` |",
            "| Viva reset | `POST /admin/params/reset-to-pre-amend` | Override without extract/review |",
            "| LegalRuleEvidence | stub approve | Does not mutate engine |",
            "",
            "**Conclusion:** The reviewed amendment pipeline is **not** the sole path executable",
            "data enters the system. Bootstrap fixtures and engine constants remain authoritative",
            "for `calculate()`. Closing this gap requires a future policy decision.",
            "",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf-source",
        type=Path,
        default=Path(r"c:\Users\H P\Desktop\Research_Project\IRD_Docs"),
    )
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--skip-corpus", action="store_true")
    parser.add_argument("--skip-harvest", action="store_true", help="Reuse cached harvest JSON")
    parser.add_argument("--stage", choices=["all", "a", "b", "c", "report"], default="all")
    args = parser.parse_args(argv)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    sync_log: list[str] = []
    corpus_log: list[str] = []

    rows: list[InventoryRow] = []
    if args.stage in ("all", "a"):
        rows = build_stage_a_inventory()
        inv_path = AUDIT_DIR / "stage_a_inventory.json"
        inv_path.write_text(
            json.dumps([asdict(r) for r in rows], indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Stage A: {len(rows)} inventory rows -> {inv_path}")

    if args.stage in ("all", "b", "c", "report"):
        if not rows:
            inv_path = AUDIT_DIR / "stage_a_inventory.json"
            if inv_path.is_file():
                rows = [InventoryRow(**r) for r in _load_json(inv_path)]
            else:
                rows = build_stage_a_inventory()

        if not args.skip_sync:
            sync_log = sync_pdfs(args.pdf_source)
            print("\n".join(sync_log))

        if not args.skip_corpus:
            corpus_log = build_corpus()
            print("\n".join(corpus_log[-5:]))

        quote_checks = run_quote_checks(rows)
        (AUDIT_DIR / "stage_b_quote_checks.json").write_text(
            json.dumps(quote_checks, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Stage B quote checks: {len(quote_checks['checks'])} rules checked")

        harvest = run_harvest(skip_openai=args.skip_harvest)
        (AUDIT_DIR / "stage_b_harvest_summary.json").write_text(
            json.dumps(
                {
                    "harvest_runs": harvest["harvest_runs"],
                    "numerics": _extract_numerics_from_harvest(harvest),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Stage B harvest: {harvest['harvest_runs']} runs")

    if args.stage in ("all", "c", "report"):
        quote_checks = _load_json(AUDIT_DIR / "stage_b_quote_checks.json")
        harvest = {"outputs": [], "harvest_runs": 0}
        for p in sorted(HARVEST_DIR.glob("*.json")):
            harvest["outputs"].append(_load_json(p))
        harvest["harvest_runs"] = len(harvest["outputs"])

        classifications = classify_rows(rows, quote_checks, harvest)
        (AUDIT_DIR / "stage_c_classifications.json").write_text(
            json.dumps([asdict(c) for c in classifications], indent=2) + "\n",
            encoding="utf-8",
        )
        by_cat = {}
        for c in classifications:
            by_cat[c.category] = by_cat.get(c.category, 0) + 1
        print(f"Stage C classifications: {by_cat}")

        write_report(rows, classifications, quote_checks, harvest, sync_log, corpus_log)
        print(f"Report written: {REPORT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
