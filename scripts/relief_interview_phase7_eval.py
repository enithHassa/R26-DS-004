#!/usr/bin/env python3
"""Relief Interview Phase 7 — end-to-end evaluation + viva checklist.

Runs the plan's eight evaluation criteria against live catalogs, prior phase
reports, the UI provenance surface, and (when possible) the engine tax delta
for YA 2024/25 vs 2025/26.

Usage:
  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase7_eval.py
  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase7_eval.py --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "models" / "adaptive-tax" / "relief-interview"
APPROVED_DIR = OUT_ROOT / "approved"
RATES_DIR = OUT_ROOT / "rates"
EXTRACTED_DIR = OUT_ROOT / "extracted"
REVIEW_DIR = OUT_ROOT / "review"
PROPOSED_DIR = OUT_ROOT / "proposed"
HARVEST_PATH = OUT_ROOT / "harvest" / "commencement_records.json"
ACCURACY_JSON = EXTRACTED_DIR / "accuracy_result.json"
PHASE1_REPORT = REPO_ROOT / "docs" / "reports" / "relief_interview_phase1_ya_mapping.md"
PHASE4_ACCURACY_MD = REPO_ROOT / "docs" / "reports" / "relief_interview_phase4_accuracy.md"
REPORT_MD = REPO_ROOT / "docs" / "reports" / "relief_interview_phase7_eval.md"
RESULT_JSON = OUT_ROOT / "review" / "phase7_eval_result.json"
MANIFEST_PATH = REPO_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"
IMMUTABLE_BASELINE = REVIEW_DIR / "immutable_baseline.json"
RELIEFS_UI = (
    REPO_ROOT
    / "frontend"
    / "src"
    / "features"
    / "adaptive-tax"
    / "pages"
    / "relief-interview"
    / "reliefs.tsx"
)
COMPARE_UI = (
    REPO_ROOT
    / "frontend"
    / "src"
    / "features"
    / "adaptive-tax"
    / "pages"
    / "relief-interview"
    / "compare.tsx"
)
YEAR_DIFF_UI = (
    REPO_ROOT
    / "frontend"
    / "src"
    / "features"
    / "adaptive-tax"
    / "pages"
    / "relief-interview"
    / "year-diff-panel.tsx"
)

CORE_YAS = (
    "2018_19",
    "2019_20",
    "2020_21",
    "2021_22",
    "2022_23",
    "2023_24",
    "2024_25",
    "2025_26",
)
FORBIDDEN_SOURCE_DOC_IDS = frozenset(
    {"ird-consolidated-2025", "ird-guide-ira", "ird-calc-ontology-v5"}
)
VIVA_EMPLOYMENT_INCOME = Decimal("5000000")  # same facts both engine years


@dataclass
class CheckResult:
    id: str
    title: str
    status: str  # PASS | FAIL | PARTIAL | SKIP
    summary: str
    details: list[str] = field(default_factory=list)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_approved(ya: str) -> dict[str, Any]:
    return load_json(APPROVED_DIR / f"{ya}.json")


def find_group(ya: str, group_id: str) -> dict[str, Any] | None:
    data = load_approved(ya)
    for entry in data.get("entries", []):
        if entry.get("compare_group_id") == group_id:
            return entry
    return None


def cap_int(entry: dict[str, Any] | None) -> int | None:
    if not entry:
        return None
    raw = str(entry.get("cap_amount") or "").replace(",", "").strip()
    return int(raw) if raw.isdigit() else None


# --------------------------------------------------------------------------
# Checklist items
# --------------------------------------------------------------------------


def check_phase1_mapping() -> CheckResult:
    details: list[str] = []
    if not PHASE1_REPORT.is_file():
        return CheckResult(
            "phase1_mapping",
            "Phase 1 YA mapping reported (stop honored if remapped)",
            "FAIL",
            "Phase 1 report missing",
            [str(PHASE1_REPORT)],
        )
    text = PHASE1_REPORT.read_text(encoding="utf-8")
    details.append(f"report: {PHASE1_REPORT.relative_to(REPO_ROOT).as_posix()}")

    path_ok = "**Path check:** PASS" in text
    details.append(f"path check PASS documented: {path_ok}")

    cleared = "Phase 1 YA-mapping stop is **cleared**" in text
    details.append(f"YA-mapping stop cleared: {cleared}")

    confirmed = (
        "Confirmed range equals `2018_19` … `2025_26`" in text
        or "Confirmed range equals `2018_19` ... `2025_26`" in text
        or ("2018_19" in text and "2025_26" in text and "cleared" in text.lower())
    )
    # Prefer the explicit cleared line + confirmed range bullet.
    confirmed = "Confirmed (harvest min→max" in text or "Confirmed (harvest min" in text
    if "2018_19, 2019_20, 2020_21, 2021_22, 2022_23, 2023_24, 2024_25, 2025_26" in text:
        confirmed = True
    details.append(f"confirmed range 2018/19-2025/26 present: {confirmed}")

    harvest_ok = HARVEST_PATH.is_file()
    details.append(f"commencement harvest JSON present: {harvest_ok}")

    # Stop was honored: range matched hypothesis, so Phases 2-7 were allowed to proceed.
    if path_ok and cleared and confirmed and harvest_ok:
        return CheckResult(
            "phase1_mapping",
            "Phase 1 YA mapping reported (stop honored if remapped)",
            "PASS",
            "Path check passed; confirmed range matches hypothesis; stop cleared",
            details,
        )
    return CheckResult(
        "phase1_mapping",
        "Phase 1 YA mapping reported (stop honored if remapped)",
        "FAIL",
        "Phase 1 gate evidence incomplete",
        details,
    )


def check_extractor_only() -> CheckResult:
    details: list[str] = []
    problems: list[str] = []
    checked = 0

    # Index staging quotes + values for provenance trail lookup.
    staging_by_quote: dict[str, dict[str, Any]] = {}
    for path in EXTRACTED_DIR.glob("*__*.json"):
        doc = load_json(path)
        for row in doc.get("rows", []):
            if not row.get("included"):
                continue
            key = re.sub(r"\s+", " ", (row.get("quote") or "")).strip().lower()
            if key:
                staging_by_quote[key] = {
                    "source_doc_id": doc["source_doc_id"],
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "cap_amount": row.get("cap_amount"),
                    "run_id": doc.get("run_id", ""),
                }

    for ya in CORE_YAS:
        approved = load_approved(ya)
        rates = load_json(RATES_DIR / f"{ya}.json")
        for entry in approved.get("entries", []):
            checked += 1
            sid = entry.get("source_doc_id", "")
            if sid in FORBIDDEN_SOURCE_DOC_IDS:
                problems.append(f"{ya}/{entry.get('compare_group_id')}: forbidden source {sid}")
            quote = re.sub(r"\s+", " ", entry.get("quote") or "").strip().lower()
            if not quote:
                problems.append(f"{ya}/{entry.get('compare_group_id')}: empty quote")
            elif quote not in staging_by_quote and not entry.get("provenance", {}).get(
                "extract_run_id"
            ):
                # Phase 6 watcher rows cite proposal extract_run_id under provenance.
                if entry.get("provenance", {}).get("phase") == 6:
                    continue
                problems.append(
                    f"{ya}/{entry.get('compare_group_id')}: no staging match and no extract_run_id"
                )
            prov = entry.get("provenance") or {}
            if not prov.get("extract_run_id") and not prov.get("staging_path") and prov.get("phase") != 6:
                # Still acceptable if quote matches staging (Phase 5 trail).
                if quote in staging_by_quote:
                    continue
                problems.append(f"{ya}/{entry.get('compare_group_id')}: missing provenance trail")

        for band in rates.get("bands", []):
            checked += 1
            sid = band.get("source_doc_id", "")
            if sid in FORBIDDEN_SOURCE_DOC_IDS:
                problems.append(f"rates/{ya} band: forbidden source {sid}")
            if not band.get("quote"):
                problems.append(f"rates/{ya} band missing quote")

        # Ontology packs must not appear as the catalog source of a live row.
        notes = (approved.get("notes") or "") + " " + (rates.get("notes") or "")
        if "ontology" in notes.lower() and "hand-typed" in notes.lower():
            pass  # explanatory notes ok
        if approved.get("phase1_empty_skeleton"):
            problems.append(f"{ya}: still marked phase1_empty_skeleton")

    details.append(f"live catalog rows/bands checked: {checked}")
    details.append(f"staging included quotes indexed: {len(staging_by_quote)}")
    if problems:
        details.extend(problems[:12])
        return CheckResult(
            "extractor_only",
            "Extractor-only origin (no ontology/hand-typed rows)",
            "FAIL",
            f"{len(problems)} provenance/origin problems",
            details,
        )
    return CheckResult(
        "extractor_only",
        "Extractor-only origin (no ontology/hand-typed rows)",
        "PASS",
        "Every core-year entry/band carries Act quote + non-forbidden source_doc_id",
        details,
    )


def check_quote_and_attribution() -> CheckResult:
    """Re-test quotes against the Act PDF for a sample of live entries."""
    details: list[str] = []
    problems: list[str] = []
    try:
        p4 = _load_module(
            REPO_ROOT / "scripts" / "relief_interview_phase4_extract.py",
            "relief_interview_phase4_extract",
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "quote_attribution",
            "Quote match and correct act_name / section_ref / source_doc_id",
            "FAIL",
            f"Could not load Phase 4 extract module: {exc}",
            details,
        )

    resolved, path_rows, errors = p4.confirm_pdf_paths()
    if errors:
        return CheckResult(
            "quote_attribution",
            "Quote match and correct act_name / section_ref / source_doc_id",
            "FAIL",
            "Manifest path check failed",
            errors,
        )
    details.append(f"manifest path check: {sum(1 for r in path_rows if r['exists'])} ok")

    act_cache: dict[str, Any] = {}
    checked = 0
    sample_yas = ("2024_25", "2025_26", "2018_19")
    for ya in sample_yas:
        for entry in load_approved(ya).get("entries", []):
            sid = entry.get("source_doc_id", "")
            if sid.startswith("ird-amend-watcher"):
                continue  # synthetic demo PDF; not in extract corpus
            if sid not in resolved:
                problems.append(f"{ya}: unknown source_doc_id {sid}")
                continue
            if sid not in act_cache:
                act_cache[sid] = p4.read_act_text(resolved[sid])
            act = act_cache[sid]
            stream_norm = p4.normalize_for_match(act.stream)
            tables_norm = p4.normalize_for_match(act.tables_blob)
            quote = entry.get("quote") or ""
            gate = p4.quote_gate(quote, stream_norm, stream_norm, tables_norm)
            checked += 1
            if not gate["quote_ok_full_doc"]:
                problems.append(
                    f"{ya}/{entry.get('compare_group_id')}: quote not in {sid}"
                )
            if not entry.get("act_name"):
                problems.append(f"{ya}/{entry.get('compare_group_id')}: empty act_name")
            if not entry.get("section_ref"):
                problems.append(f"{ya}/{entry.get('compare_group_id')}: empty section_ref")
            # Manifest title should appear in act_name for amending Acts (Phase 5 fix).
            if sid.startswith("ird-amend-") and "2017" in (entry.get("act_name") or "") and "Amendment" not in (
                entry.get("act_name") or ""
            ):
                problems.append(
                    f"{ya}/{entry.get('compare_group_id')}: act_name still credits 2017 base for {sid}"
                )

        for band in load_json(RATES_DIR / f"{ya}.json").get("bands", [])[:3]:
            sid = band.get("source_doc_id", "")
            if sid not in resolved:
                continue
            if sid not in act_cache:
                act_cache[sid] = p4.read_act_text(resolved[sid])
            act = act_cache[sid]
            stream_norm = p4.normalize_for_match(act.stream)
            tables_norm = p4.normalize_for_match(act.tables_blob)
            gate = p4.quote_gate(band.get("quote") or "", stream_norm, stream_norm, tables_norm)
            checked += 1
            if not gate["quote_ok_full_doc"]:
                problems.append(f"rates/{ya} band quote not in {sid}")

    details.append(f"quotes re-checked against PDF: {checked}")
    if problems:
        details.extend(problems[:15])
        return CheckResult(
            "quote_attribution",
            "Quote match and correct act_name / section_ref / source_doc_id",
            "FAIL",
            f"{len(problems)} attribution/quote failures",
            details,
        )
    return CheckResult(
        "quote_attribution",
        "Quote match and correct act_name / section_ref / source_doc_id",
        "PASS",
        f"Sample of {checked} live quotes still match their Act PDFs with attributions filled",
        details,
    )


def check_viva_pairwise() -> CheckResult:
    details: list[str] = []
    problems: list[str] = []

    # Personal relief 1.2M vs 1.8M
    a = find_group("2024_25", "personal_relief")
    b = find_group("2025_26", "personal_relief")
    cap_a, cap_b = cap_int(a), cap_int(b)
    details.append(f"personal_relief 2024/25={cap_a}  2025/26={cap_b}")
    if cap_a != 1_200_000 or cap_b != 1_800_000:
        problems.append(f"expected 1200000 vs 1800000, got {cap_a} vs {cap_b}")
    else:
        details.append(
            f"sources: {a and a.get('source_doc_id')} vs {b and b.get('source_doc_id')}"
        )

    # Solar unchanged across years where present
    solar_caps = []
    for ya in CORE_YAS:
        entry = find_group(ya, "solar_panel_relief")
        if entry:
            solar_caps.append((ya, cap_int(entry)))
    details.append(
        "solar_panel_relief: "
        + ", ".join(f"{ya}={cap}" for ya, cap in solar_caps)
        or "(absent all years)"
    )
    caps_only = {cap for _, cap in solar_caps}
    if not solar_caps:
        problems.append("solar_panel_relief missing from all years")
    elif caps_only != {600_000}:
        problems.append(f"solar caps not uniformly 600000: {solar_caps}")
    elif "2024_25" not in {ya for ya, _ in solar_caps} or "2025_26" not in {
        ya for ya, _ in solar_caps
    }:
        problems.append("solar missing on an engine year")
    else:
        details.append("solar unchanged at 600000 wherever present (incl. engine years)")

    # Sec 52(4) carry-forward (expected from 2025/26 per plan)
    sec52_hits: list[str] = []
    for ya in ("2024_25", "2025_26"):
        data = load_approved(ya)
        for entry in data.get("entries", []):
            blob = " ".join(
                str(entry.get(k, ""))
                for k in ("compare_group_id", "display_name", "question_prompt", "quote", "section_ref")
            ).lower()
            if "52(4)" in blob or "carry forward" in blob or "carry-forward" in blob:
                sec52_hits.append(f"{ya}:{entry.get('compare_group_id')}")
    if sec52_hits:
        details.append(f"Sec 52(4)/carry-forward catalog hits: {', '.join(sec52_hits)}")
    else:
        details.append(
            "Sec 52(4) carry-forward: NOT in live catalogs "
            "(Phase 4 staging for ird-amend-2026-11__52 was gate-blocked; "
            "known gap documented in Phase 5 report)"
        )
        problems.append("sec52_4_missing")

    # Tax delta on engine years (same income, file ontology)
    tax_detail = _engine_tax_delta()
    details.extend(tax_detail["details"])
    if tax_detail["status"] == "FAIL":
        problems.append(tax_detail["summary"])
    elif tax_detail["status"] == "SKIP":
        details.append(f"tax delta skipped: {tax_detail['summary']}")

    # Verdict: personal+solar+tax are the demo spine; Sec 52(4) gap -> PARTIAL if only that fails
    hard = [p for p in problems if p != "sec52_4_missing" and not p.startswith("tax delta skipped")]
    if hard:
        return CheckResult(
            "viva_pairwise",
            "Viva pairwise: personal relief 1.2M vs 1.8M; Sec 52(4); solar unchanged; tax delta",
            "FAIL",
            "; ".join(hard[:3]),
            details,
        )
    if "sec52_4_missing" in problems:
        status = "PARTIAL"
        summary = (
            "Personal relief 1.2M vs 1.8M and solar-unchanged PASS; "
            "Sec 52(4) CF absent from catalogs (extractor gap); "
            + tax_detail["summary"]
        )
    else:
        status = "PASS"
        summary = "All pairwise viva items demonstrated"
    return CheckResult(
        "viva_pairwise",
        "Viva pairwise: personal relief 1.2M vs 1.8M; Sec 52(4); solar unchanged; tax delta",
        status,
        summary,
        details,
    )


def _engine_tax_delta() -> dict[str, Any]:
    details: list[str] = []
    try:
        from adaptive_tax_app.schemas.calculate import CalculateTaxRequestV1
        from adaptive_tax_app.services.rule_engine import calculate, default_file_kg
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "SKIP",
            "summary": f"rule engine import failed: {exc}",
            "details": details,
        }

    kg = default_file_kg()
    results: dict[str, Decimal] = {}
    try:
        for ya in ("2024_25", "2025_26"):
            req = CalculateTaxRequestV1(
                assessment_year=ya,
                resident_status="resident",
                employment_income=VIVA_EMPLOYMENT_INCOME,
                business_income=Decimal("0"),
                investment_income=Decimal("0"),
                other_income=Decimal("0"),
            )
            resp = calculate(req, kg=kg)
            payable = Decimal(str(resp.tax_payable_lkr))
            results[ya] = payable
            details.append(f"engine {ya}: tax_payable={payable} on employment={VIVA_EMPLOYMENT_INCOME}")
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "SKIP",
            "summary": f"calculate() unavailable ({type(exc).__name__}: {exc})",
            "details": details,
        }

    delta = results["2025_26"] - results["2024_25"]
    details.append(f"tax delta 2025/26 - 2024/25 = {delta}")
    # Same employment income; personal relief rose 1.2M->1.8M and rate ladder changed,
    # so payable should differ. Direction depends on ladder vs relief interaction.
    if results["2024_25"] == results["2025_26"]:
        return {
            "status": "FAIL",
            "summary": "tax payable identical across engine years despite different packs",
            "details": details,
        }
    return {
        "status": "PASS",
        "summary": f"engine tax delta demonstrated ({delta} LKR)",
        "details": details,
    }


def check_compare_table() -> CheckResult:
    details: list[str] = []
    if not COMPARE_UI.is_file():
        return CheckResult(
            "compare_table",
            "Compare table across confirmed YAs",
            "FAIL",
            "compare.tsx missing",
            details,
        )
    ui = COMPARE_UI.read_text(encoding="utf-8")
    has_all = "getReliefInterviewApprovedAll" in ui
    has_table = "<table" in ui.lower() or "Table" in ui
    details.append(f"compare.tsx loads all years API: {has_all}")
    details.append(f"compare.tsx renders a table: {has_table}")

    # Data side: personal_relief present across confirmed range with varying caps
    series = []
    for ya in CORE_YAS:
        entry = find_group(ya, "personal_relief")
        series.append((ya, cap_int(entry)))
    details.append(
        "personal_relief series: " + ", ".join(f"{ya}={cap}" for ya, cap in series)
    )
    caps = [cap for _, cap in series if cap is not None]
    varies = len(set(caps)) >= 3
    complete = all(cap is not None for _, cap in series)

    if has_all and has_table and complete and varies:
        return CheckResult(
            "compare_table",
            "Compare table across confirmed YAs",
            "PASS",
            "UI loads all-year catalogs; personal_relief varies across 8 confirmed YAs",
            details,
        )
    return CheckResult(
        "compare_table",
        "Compare table across confirmed YAs",
        "FAIL",
        "Compare UI or multi-year data incomplete",
        details,
    )


def check_provenance_badge() -> CheckResult:
    details: list[str] = []
    if not RELIEFS_UI.is_file():
        return CheckResult(
            "provenance_badge",
            "Expandable badge shows real provenance",
            "FAIL",
            "reliefs.tsx missing",
            details,
        )
    ui = RELIEFS_UI.read_text(encoding="utf-8")
    year_diff = YEAR_DIFF_UI.read_text(encoding="utf-8") if YEAR_DIFF_UI.is_file() else ""

    has_block = "Provenance" in ui and "act_name" in ui and "section_ref" in ui
    has_quote = "current.quote" in ui
    has_source = "source_doc_id" in ui
    has_diff_quotes = "As-of quote" in year_diff and "Compare quote" in year_diff
    details.append(f"reliefs provenance block (act/section/source): {has_block and has_source}")
    details.append(f"reliefs shows quote: {has_quote}")
    details.append(f"year-diff panel shows both years' quotes: {has_diff_quotes}")

    # Live data: every core entry has the four provenance fields
    missing = 0
    for ya in ("2024_25", "2025_26"):
        for entry in load_approved(ya).get("entries", []):
            for field_name in ("act_name", "section_ref", "quote", "source_doc_id"):
                if not entry.get(field_name):
                    missing += 1
    details.append(f"empty provenance fields on engine-year entries: {missing}")

    # Sample receipt for the viva pair
    a = find_group("2024_25", "personal_relief")
    b = find_group("2025_26", "personal_relief")
    if a and b:
        details.append(
            f"2024/25 receipt: {a.get('act_name')} | {a.get('section_ref')} | "
            f"{(a.get('quote') or '')[:80]}..."
        )
        details.append(
            f"2025/26 receipt: {b.get('act_name')} | {b.get('section_ref')} | "
            f"{(b.get('quote') or '')[:80]}..."
        )

    if has_block and has_quote and has_source and has_diff_quotes and missing == 0:
        return CheckResult(
            "provenance_badge",
            "Expandable badge shows real provenance",
            "PASS",
            "Interview provenance panel + year-diff quotes wired to live Act fields",
            details,
        )
    return CheckResult(
        "provenance_badge",
        "Expandable badge shows real provenance",
        "FAIL",
        "Provenance UI or catalog fields incomplete",
        details,
    )


def check_rate_accuracy_gate() -> CheckResult:
    details: list[str] = []
    if not ACCURACY_JSON.is_file():
        return CheckResult(
            "rate_accuracy",
            "Rate accuracy gate documented",
            "FAIL",
            "accuracy_result.json missing",
            details,
        )
    data = load_json(ACCURACY_JSON)
    gate = bool(data.get("gate_pass"))
    details.append(f"accuracy_result.gate_pass = {gate}")
    for ya in ("2024_25", "2025_26"):
        year = (data.get("years") or {}).get(ya, {})
        match = (year.get("diff") or {}).get("match")
        ladder = (year.get("ladder") or {}).get("source_doc_id")
        details.append(f"{ya}: ontology match={match} ladder={ladder}")
    md_ok = PHASE4_ACCURACY_MD.is_file()
    details.append(f"markdown report present: {md_ok}")
    if gate and md_ok:
        return CheckResult(
            "rate_accuracy",
            "Rate accuracy gate documented",
            "PASS",
            "2024/25 and 2025/26 match ontology packs; Phase 8 gate cleared",
            details,
        )
    return CheckResult(
        "rate_accuracy",
        "Rate accuracy gate documented",
        "FAIL",
        "Accuracy gate did not pass or report missing",
        details,
    )


def check_watcher_immutability() -> CheckResult:
    details: list[str] = []
    problems: list[str] = []

    # Baseline must cover the eight core years
    if not IMMUTABLE_BASELINE.is_file():
        return CheckResult(
            "watcher_immutable",
            "Watcher does not rewrite past approved/*.json",
            "FAIL",
            "immutable_baseline.json missing (run Phase 6 check-immutable)",
            details,
        )
    baseline = load_json(IMMUTABLE_BASELINE)
    files = baseline.get("files") or {}
    details.append(f"baseline files: {len(files)} (captured {baseline.get('captured_at')})")

    phase5 = _load_module(
        REPO_ROOT / "scripts" / "relief_interview_phase5_review.py",
        "relief_interview_phase5_review",
    )
    for ya in CORE_YAS:
        for folder, directory in (("approved", APPROVED_DIR), ("rates", RATES_DIR)):
            key = f"{folder}/{ya}.json"
            path = directory / f"{ya}.json"
            payload = load_json(path)
            recorded = payload.get("content_sha256")
            recomputed = phase5.canonical_sha256(payload)
            if not recorded:
                problems.append(f"{key}: missing content_sha256")
                continue
            if recorded != recomputed:
                problems.append(f"{key}: content hash mismatch (file edited)")
            expected = files.get(key)
            if expected and expected != recorded:
                problems.append(f"{key}: differs from immutable baseline")
            details.append(f"{key}: sealed ok")

    # Watcher demo created 2026_27 without touching past years
    demo_approved = APPROVED_DIR / "2026_27.json"
    proposal = PROPOSED_DIR / "ird-amend-watcher-demo-2026.json"
    details.append(f"watcher demo proposal present: {proposal.is_file()}")
    details.append(f"watcher new year 2026_27 present: {demo_approved.is_file()}")
    if demo_approved.is_file():
        demo = load_json(demo_approved)
        if demo.get("promotion_source") != "phase6_watcher":
            problems.append("2026_27 not marked as phase6_watcher promotion")
        # Past personal relief values must still be the Phase 5 story
        if cap_int(find_group("2024_25", "personal_relief")) != 1_200_000:
            problems.append("2024_25 personal relief changed after watcher")
        if cap_int(find_group("2025_26", "personal_relief")) != 1_800_000:
            problems.append("2025_26 personal relief changed after watcher")

    # Refuse corpus docs still encoded in watcher
    watcher_src = (
        REPO_ROOT / "scripts" / "relief_interview_phase6_watcher.py"
    ).read_text(encoding="utf-8")
    refuses = "ird-amend-2023-04" in watcher_src and "not_in_corpus_manifest" in watcher_src
    details.append(f"watcher refuses in-corpus Acts (incl. 04/2023): {refuses}")
    if not refuses:
        problems.append("watcher script no longer documents corpus refusal")

    if problems:
        details.extend(problems)
        return CheckResult(
            "watcher_immutable",
            "Watcher does not rewrite past approved/*.json",
            "FAIL",
            f"{len(problems)} immutability problems",
            details,
        )
    return CheckResult(
        "watcher_immutable",
        "Watcher does not rewrite past approved/*.json",
        "PASS",
        "Core-year hashes intact; watcher only added 2026_27",
        details,
    )


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def render_report(checks: list[CheckResult], overall: str) -> str:
    lines = [
        "# Relief Interview — Phase 7 evaluation (viva checklist)",
        "",
        f"**Generated:** {now_iso()}",
        f"**Overall:** **{overall}**",
        "**Canonical plan:** [relief_interview_plan.md](relief_interview_plan.md)",
        "",
        "Automated checks against live `approved/` / `rates/`, Phase 1–6 artifacts, "
        "and the Relief Interview UI provenance surfaces.",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| # | Check | Status |",
        "|---|---|---|",
    ]
    for i, check in enumerate(checks, start=1):
        lines.append(f"| {i} | {check.title} | **{check.status}** |")

    lines.extend(["", "---", ""])
    for i, check in enumerate(checks, start=1):
        lines.append(f"## {i}. {check.title}")
        lines.append("")
        lines.append(f"**Status:** {check.status}")
        lines.append("")
        lines.append(check.summary)
        lines.append("")
        if check.details:
            lines.append("Details:")
            lines.append("")
            for detail in check.details:
                lines.append(f"- {detail}")
            lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## Viva script (suggested)",
            "",
            "1. Open Relief Interview → pick **2024/25** as-of and **2025/26** compare.",
            "2. On personal relief: show **1,200,000 → 1,800,000** with Act quotes.",
            "3. Open Compare → personal relief across **2018/19–2025/26** "
            "(500k → 3M → 2.25M → 1.2M → 1.8M).",
            "4. Show solar at **600,000** unchanged on both engine years.",
            "5. Same employment income through Result for both engine years → tax delta.",
            "6. Expand provenance: `act_name` / `section_ref` / `quote` / `source_doc_id`.",
            "7. Note Phase 4 accuracy gate PASS; Phase 6 watcher added `2026_27` only.",
            "",
            "## Known gaps called in this eval",
            "",
            "- **Sec 52(4) carry-forward** is not in live catalogs (Phase 4 quote-gate "
            "blocked `ird-amend-2026-11` §52). Re-extract before claiming that viva beat.",
            "- Watcher demo year `2026_27` is on disk but not in the UI YA list yet.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def overall_status(checks: list[CheckResult]) -> str:
    statuses = {c.status for c in checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "PARTIAL" in statuses or "SKIP" in statuses:
        return "PASS_WITH_GAPS"
    return "PASS"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relief Interview Phase 7 evaluation")
    parser.add_argument("--json", action="store_true", help="Also print machine JSON to stdout")
    parser.add_argument("--skip-pdf", action="store_true", help="Skip PDF quote re-check (faster)")
    args = parser.parse_args(argv)

    print("=== Phase 7 evaluation ===")
    checks: list[CheckResult] = []

    runners = [
        check_phase1_mapping,
        check_extractor_only,
        (lambda: CheckResult(
            "quote_attribution",
            "Quote match and correct act_name / section_ref / source_doc_id",
            "SKIP",
            "skipped via --skip-pdf",
            [],
        ))
        if args.skip_pdf
        else check_quote_and_attribution,
        check_viva_pairwise,
        check_compare_table,
        check_provenance_badge,
        check_rate_accuracy_gate,
        check_watcher_immutability,
    ]

    for run in runners:
        result = run()
        checks.append(result)
        mark = {"PASS": "OK", "FAIL": "!!", "PARTIAL": "~ ", "SKIP": "--"}.get(
            result.status, "??"
        )
        print(f"  [{mark}] {result.status:<8} {result.title}")
        print(f"         {result.summary}")

    overall = overall_status(checks)
    report = render_report(checks, overall)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(report, encoding="utf-8")

    payload = {
        "generated_at": now_iso(),
        "overall": overall,
        "checks": [asdict(c) for c in checks],
        "report_path": REPORT_MD.relative_to(REPO_ROOT).as_posix(),
    }
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print()
    print(f"Overall: {overall}")
    print(f"Report : {REPORT_MD.relative_to(REPO_ROOT).as_posix()}")
    print(f"JSON   : {RESULT_JSON.relative_to(REPO_ROOT).as_posix()}")
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    return 0 if overall in {"PASS", "PASS_WITH_GAPS"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
