#!/usr/bin/env python3
"""Relief Interview Phase 6 — amendment watcher.

Future Acts propose catalog changes without rewriting the past.

Flow
----
1. ``ingest`` a PDF that is **not** already in ``corpus_manifest.json``
2. Extract + verify (same Pass 1 / Pass 2 / quote gate as Phase 4)
3. Write ``proposed/{source_doc_id}.json`` with ``proposed_for_assessment_year`` empty
4. Human ``set-year`` to a **new** YA that has no live catalog yet
5. ``promote`` creates only ``approved/{ya}.json`` + ``rates/{ya}.json`` for that YA
6. Every previously existing year-file hash is re-checked and must be unchanged

Act 04/2023 (``ird-amend-2023-04``) is already in the extract corpus — it is
refused here on purpose. The watcher demo uses a synthetic fixture PDF that is
not in the manifest.

Commands
--------
  status
  list
  show <source_doc_id>
  make-demo-pdf              write the synthetic watcher-demo PDF
  ingest --pdf PATH --source-doc-id ID [--title TITLE] [--force] [--dry-run]
  set-year --source-doc-id ID --ya YYYY_YY
  promote --source-doc-id ID [--dry-run]
  check-immutable            assert past year file hashes are intact
  refuse-corpus-docs         show which known Acts the watcher will reject

Usage:
  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase6_watcher.py status
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"
OUT_ROOT = REPO_ROOT / "models" / "adaptive-tax" / "relief-interview"
PROPOSED_DIR = OUT_ROOT / "proposed"
APPROVED_DIR = OUT_ROOT / "approved"
RATES_DIR = OUT_ROOT / "rates"
REVIEW_DIR = OUT_ROOT / "review"
HASH_BASELINE_PATH = REVIEW_DIR / "immutable_baseline.json"
DEMO_DIR = OUT_ROOT / "watcher-demo"
DEMO_PDF_PATH = DEMO_DIR / "IR_Act_No_Watcher_Demo_2026_E.pdf"
DEMO_SOURCE_DOC_ID = "ird-amend-watcher-demo-2026"
DEMO_TITLE = "Inland Revenue Amendment Act (Watcher Demo 2026) — SYNTHETIC FIXTURE"
EXTRACT_SCRIPT = REPO_ROOT / "scripts" / "relief_interview_phase4_extract.py"
PHASE5_SCRIPT = REPO_ROOT / "scripts" / "relief_interview_phase5_review.py"

SPEC_VERSION = "1.0.0"
YA_RE = re.compile(r"^\d{4}_\d{2}$")

# Explicitly called out in the plan: already in the Phase 4 extract corpus.
EXTRACT_CORPUS_IDS = frozenset(
    {
        "ird-ira-2017-base",
        "ird-amend-2021-10",
        "ird-amend-2022-45",
        "ird-amend-2023-04",
        "ird-amend-2023-14",
        "ird-amend-2025-02",
        "ird-amend-2026-11",
    }
)


# --------------------------------------------------------------------------
# Module loaders (standalone scripts; no package import cycle)
# --------------------------------------------------------------------------


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def p4() -> Any:
    return _load_module(EXTRACT_SCRIPT, "relief_interview_phase4_extract")


def p5() -> Any:
    return _load_module(PHASE5_SCRIPT, "relief_interview_phase5_review")


# --------------------------------------------------------------------------
# Manifest / path guards
# --------------------------------------------------------------------------


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def manifest_index(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    data = manifest or load_manifest()
    by_id = {d["source_doc_id"]: d for d in data["documents"]}
    by_name = {d["file_name"].lower(): d for d in data["documents"]}
    return {"by_id": by_id, "by_name": by_name, "pdf_root": data.get("pdf_root", "")}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def refuse_reasons(source_doc_id: str, pdf_path: Path) -> list[str]:
    """Why this PDF must not enter the watcher pipeline."""
    idx = manifest_index()
    reasons: list[str] = []
    if source_doc_id in idx["by_id"]:
        reasons.append(
            f"source_doc_id {source_doc_id!r} is already in corpus_manifest.json "
            f"({idx['by_id'][source_doc_id]['file_name']})"
        )
    if source_doc_id in EXTRACT_CORPUS_IDS:
        reasons.append(
            f"{source_doc_id!r} is already in the Phase 4 extract corpus "
            "(Act 04/2023 and the other six Acts are not watcher demos)"
        )
    name_hit = idx["by_name"].get(pdf_path.name.lower())
    if name_hit:
        reasons.append(
            f"file name {pdf_path.name!r} matches corpus_manifest entry "
            f"{name_hit['source_doc_id']!r} - watcher only accepts PDFs outside the manifest"
        )
    if not pdf_path.is_file():
        reasons.append(f"PDF does not exist: {pdf_path}")
    return reasons


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def proposed_path(source_doc_id: str) -> Path:
    return PROPOSED_DIR / f"{source_doc_id}.json"


def load_proposed(source_doc_id: str) -> dict[str, Any]:
    path = proposed_path(source_doc_id)
    if not path.is_file():
        raise FileNotFoundError(f"No proposal at {path.relative_to(REPO_ROOT).as_posix()}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_proposed(payload: dict[str, Any]) -> Path:
    PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    path = proposed_path(payload["source_doc_id"])
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def list_year_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for directory, label in ((APPROVED_DIR, "approved"), (RATES_DIR, "rates")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            files.append((f"{label}/{path.name}", path))
    return files


def snapshot_year_hashes() -> dict[str, str]:
    """content_sha256 (preferred) or whole-file sha256 for every live year file."""
    phase5 = p5()
    out: dict[str, str] = {}
    for key, path in list_year_files():
        payload = json.loads(path.read_text(encoding="utf-8"))
        recorded = payload.get("content_sha256")
        if recorded:
            # Prefer the sealed catalog hash so formatting churn does not false-alarm.
            recomputed = phase5.canonical_sha256(payload)
            if recorded != recomputed:
                raise SystemExit(
                    f"{key} was edited after sealing (content hash mismatch). "
                    "Restore from git or re-promote Phase 5 before running the watcher."
                )
            out[key] = recorded
        else:
            out[key] = file_sha256(path)
    return out


def write_immutable_baseline(hashes: dict[str, str], note: str) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "spec_version": SPEC_VERSION,
        "phase": 6,
        "captured_at": now_iso(),
        "note": note,
        "files": hashes,
    }
    HASH_BASELINE_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_immutable_baseline() -> dict[str, Any] | None:
    if not HASH_BASELINE_PATH.is_file():
        return None
    return json.loads(HASH_BASELINE_PATH.read_text(encoding="utf-8"))


def assert_past_years_unchanged(baseline: dict[str, str]) -> list[str]:
    """Return problems; empty list means every baseline file is byte-stable by hash."""
    current = snapshot_year_hashes()
    problems: list[str] = []
    for key, expected in baseline.items():
        actual = current.get(key)
        if actual is None:
            problems.append(f"{key} missing after watcher action")
        elif actual != expected:
            problems.append(f"{key} hash changed ({expected[:12]}... -> {actual[:12]}...)")
    return problems


def latest_approved_ya() -> str | None:
    years = sorted(
        p.stem
        for p in APPROVED_DIR.glob("*.json")
        if YA_RE.match(p.stem)
        and json.loads(p.read_text(encoding="utf-8")).get("entries")
    )
    return years[-1] if years else None


# --------------------------------------------------------------------------
# Diff against latest approved YA
# --------------------------------------------------------------------------


def _cap_key(entry: dict[str, Any]) -> str:
    return f"{entry.get('compare_group_id', '')}|{entry.get('cap_amount') or ''}|{entry.get('unit') or ''}"


def diff_against_approved(proposal_rows: list[dict[str, Any]], ya: str | None) -> dict[str, Any]:
    if not ya or not (APPROVED_DIR / f"{ya}.json").is_file():
        return {
            "baseline_assessment_year": ya,
            "reliefs": {"new": [], "changed": [], "unchanged": [], "note": "no baseline year"},
        }

    approved = json.loads((APPROVED_DIR / f"{ya}.json").read_text(encoding="utf-8"))
    by_group = {
        e["compare_group_id"]: e
        for e in approved.get("entries", [])
        if e.get("compare_group_id")
    }

    new_items: list[dict[str, Any]] = []
    changed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []

    for row in proposal_rows:
        if row.get("row_kind") != "relief" or not row.get("included"):
            continue
        group = row.get("compare_group_id") or ""
        # Normalise numeric group ids from a fresh extract into a reviewable slug.
        summary = {
            "compare_group_id": group,
            "display_name": row.get("display_name", ""),
            "cap_amount": row.get("cap_amount", ""),
            "unit": row.get("unit", ""),
            "effective_from": row.get("effective_from", ""),
            "section_ref": row.get("section_ref", ""),
            "quote": (row.get("quote") or "")[:160],
        }
        prior = by_group.get(group)
        if prior is None:
            # Also try matching by display_name when the model invents a fresh group id.
            prior = next(
                (
                    e
                    for e in by_group.values()
                    if e.get("display_name", "").lower() == str(row.get("display_name", "")).lower()
                ),
                None,
            )
        if prior is None:
            new_items.append(summary)
        elif str(prior.get("cap_amount") or "") != str(row.get("cap_amount") or ""):
            changed.append(
                {
                    **summary,
                    "baseline_cap_amount": prior.get("cap_amount"),
                    "baseline_compare_group_id": prior.get("compare_group_id"),
                }
            )
        else:
            unchanged.append(summary)

    return {
        "baseline_assessment_year": ya,
        "reliefs": {
            "new": new_items,
            "changed": changed,
            "unchanged": unchanged,
        },
    }


# --------------------------------------------------------------------------
# Extraction against an arbitrary (non-manifest) PDF
# --------------------------------------------------------------------------


def extract_proposal(
    *,
    source_doc_id: str,
    act_title: str,
    pdf_path: Path,
    model: str,
    max_calls: int,
    dry_run: bool,
    only_sections: list[str] | None,
) -> dict[str, Any]:
    extract = p4()
    act = extract.read_act_text(pdf_path)
    stream_norm = extract.normalize_for_match(act.stream)
    tables_norm = extract.normalize_for_match(act.tables_blob)

    client = None
    budget = extract.Budget(max_calls)
    if not dry_run:
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            env_path = REPO_ROOT / ".env"
            if env_path.is_file():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        if not api_key:
            raise SystemExit("ERROR: OPENAI_API_KEY not set")
        client = OpenAI(api_key=api_key)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    section_keys = [
        key
        for key in extract.SECTION_KEYS
        if not only_sections or any(key.lower() == want.lower() for want in only_sections)
    ]

    sections: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []

    for section_key in section_keys:
        focus_text = extract.build_focus_window(act, section_key, is_base_act=False)
        if not focus_text:
            sections.append(
                {
                    "section_key": section_key,
                    "status": "skipped_empty_focus",
                    "rows": [],
                }
            )
            continue

        if dry_run:
            sections.append(
                {
                    "section_key": section_key,
                    "status": "dry_run",
                    "focus_chars": len(focus_text),
                    "rows": [],
                }
            )
            continue

        focus_norm = extract.normalize_for_match(focus_text)
        payload, meta = extract.run_pass1(
            client,
            budget,
            model,
            act_title=act_title,
            source_doc_id=source_doc_id,
            section_key=section_key,
            focus_text=focus_text,
        )
        rows = extract.assemble_rows(payload, source_doc_id=source_doc_id, section_key=section_key)
        for row in rows:
            gate = extract.quote_gate(row.get("quote", ""), focus_norm, stream_norm, tables_norm)
            row.update(gate)
            row["provenance_complete"] = extract.provenance_complete(row)
            row["section_ref_on_target"] = extract.section_ref_on_target(
                row.get("section_ref", ""), section_key
            )
            try:
                window = extract.pass2_window(row.get("quote", ""), focus_text)
                check = extract.run_pass2(
                    client, budget, model, quote=row.get("quote", ""), focus_text=window
                )
                row["pass2_verbatim"] = check.verbatim
                row["pass2_note"] = check.note
                row["pass2_closest_quote"] = check.closest_quote
            except RuntimeError as exc:
                row["pass2_verbatim"] = False
                row["pass2_note"] = f"pass2_error: {exc}"
                row["pass2_closest_quote"] = ""

            row["quote_long_enough"] = (
                len(extract.normalize_for_match(row.get("quote", ""))) >= extract.MIN_QUOTE_CHARS
            )
            row["included"] = bool(
                row["quote_ok_full_doc"]
                and row["provenance_complete"]
                and row["quote_long_enough"]
            )
            row["pass2_disagrees"] = bool(row["included"] and not row["pass2_verbatim"])
            row["section_key"] = section_key
            row["source_doc_id"] = source_doc_id
            row["act_title"] = act_title
            row["extract_run_id"] = run_id

        kept = [r for r in rows if r["included"]]
        all_rows.extend(rows)
        sections.append(
            {
                "section_key": section_key,
                "status": "ok",
                "focus_chars": len(focus_text),
                "row_count": len(rows),
                "included_count": len(kept),
                "pass1_tokens": meta,
                "rows": rows,
            }
        )
        print(
            f"  - {section_key:<16} rows={len(rows):<3} included={len(kept):<3} "
            f"calls={budget.calls} ~${budget.usd:.2f}"
        )

    baseline_ya = latest_approved_ya()
    included = [r for r in all_rows if r.get("included")]
    return {
        "spec_version": SPEC_VERSION,
        "phase": 6,
        "run_id": run_id,
        "model": model,
        "temperature": 0,
        "source_doc_id": source_doc_id,
        "act_title": act_title,
        "pdf_path": pdf_path.resolve().relative_to(REPO_ROOT).as_posix()
        if pdf_path.resolve().is_relative_to(REPO_ROOT)
        else str(pdf_path.resolve()),
        "pdf_file_name": pdf_path.name,
        "pdf_sha256": file_sha256(pdf_path),
        "manifest_status": "not_in_corpus_manifest",
        "proposed_for_assessment_year": None,
        "proposed_year_set_at": None,
        "proposed_year_set_by": None,
        "extracted_at": now_iso(),
        "dry_run": dry_run,
        "usage": {
            "api_calls": budget.calls,
            "prompt_tokens": budget.prompt_tokens,
            "completion_tokens": budget.completion_tokens,
            "estimated_usd": round(budget.usd, 4),
        },
        "diff": diff_against_approved(included, baseline_ya),
        "sections": sections,
        "row_count": len(all_rows),
        "included_count": len(included),
        "rows": all_rows,
        "notes": (
            "Watcher proposal only — not live. A human must set "
            "proposed_for_assessment_year and run promote. Past approved/rates "
            "year files are never rewritten by this pipeline."
        ),
    }


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_status(_args: argparse.Namespace) -> int:
    proposals = sorted(PROPOSED_DIR.glob("*.json")) if PROPOSED_DIR.is_dir() else []
    print("=== Phase 6 amendment watcher ===")
    print(f"  proposals on disk     : {len(proposals)}")
    for path in proposals:
        data = json.loads(path.read_text(encoding="utf-8"))
        ya = data.get("proposed_for_assessment_year") or "(unset)"
        print(
            f"    - {data['source_doc_id']:<32} ya={ya:<10} "
            f"included={data.get('included_count', 0)}"
        )
    baseline = load_immutable_baseline()
    if baseline:
        print(f"  immutable baseline    : {len(baseline.get('files', {}))} files "
              f"(captured {baseline.get('captured_at', '')})")
    else:
        print("  immutable baseline    : (none yet - created on first ingest/promote)")
    years = sorted(p.stem for p in APPROVED_DIR.glob("*.json") if YA_RE.match(p.stem))
    print(f"  live approved years   : {', '.join(years) or '(none)'}")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    if not PROPOSED_DIR.is_dir():
        print("  (no proposed/ directory)")
        return 0
    for path in sorted(PROPOSED_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        print(
            f"  {data['source_doc_id']:<32} "
            f"ya={str(data.get('proposed_for_assessment_year') or '-'):<10} "
            f"included={data.get('included_count', 0):<3} "
            f"{data.get('act_title', '')[:48]}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    try:
        data = load_proposed(args.source_doc_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


def cmd_refuse_corpus_docs(_args: argparse.Namespace) -> int:
    idx = manifest_index()
    print("=== PDFs the watcher will refuse ===")
    print("\nIn corpus_manifest.json:")
    for sid, doc in sorted(idx["by_id"].items()):
        tag = " [extract corpus]" if sid in EXTRACT_CORPUS_IDS else ""
        print(f"  {sid:<28} {doc['file_name']}{tag}")
    print("\nExplicit extract-corpus note:")
    print("  ird-amend-2023-04 (Act 04/2023) - already extracted in Phase 4; not a watcher demo.")
    return 0


def cmd_make_demo_pdf(args: argparse.Namespace) -> int:
    """Write a clearly marked synthetic amendment PDF outside the corpus."""
    import fitz

    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    if DEMO_PDF_PATH.is_file() and not args.force:
        print(f"  exists: {DEMO_PDF_PATH.relative_to(REPO_ROOT).as_posix()} (use --force)")
        return 0

    text = """INLAND REVENUE (AMENDMENT) ACT — WATCHER DEMO 2026
SYNTHETIC FIXTURE — NOT A REAL STATUTE — RESEARCH DEMO ONLY

An Act to amend the Inland Revenue Act, No. 24 of 2017.
[Certified on 1st January, 2026 for watcher-demo purposes only.]

Amendment of the Fifth Schedule to the principal enactment

5. The Fifth Schedule to the principal enactment is hereby amended in
paragraph 2, in subparagraph (a), by the addition immediately after item (v)
of that subparagraph, of the following new item:-

"(vi) Rs. 2,000,000, for each year of assessment commencing on or after
April 1, 2026,".

Amendment of the First Schedule to the principal enactment

6. The First Schedule to the principal enactment is hereby amended by the
substitution for the rate bands applicable to a resident or non-resident
individual, of the following, with effect from April 1, 2026:-

Taxable income for a year of assessment | Tax payable
Not exceeding Rs. 1,000,000 | 6%
Exceeding Rs. 1,000,000 but not exceeding Rs. 1,500,000 | 18%
Exceeding Rs. 1,500,000 but not exceeding Rs. 2,000,000 | 24%
Exceeding Rs. 2,000,000 but not exceeding Rs. 2,500,000 | 30%
Exceeding Rs. 2,500,000 | 36%

End of synthetic watcher-demo fixture.
"""
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)
        # insert_text keeps each glyph in the text layer so quote_gate can match.
        y = 48.0
        for line in text.splitlines():
            page.insert_text((48, y), line, fontsize=10, fontname="helv")
            y += 13
            if y > 800:
                page = doc.new_page(width=595, height=842)
                y = 48.0
        doc.save(str(DEMO_PDF_PATH))
    finally:
        doc.close()

    print(f"  wrote {DEMO_PDF_PATH.relative_to(REPO_ROOT).as_posix()}")
    print(f"  source_doc_id suggestion: {DEMO_SOURCE_DOC_ID}")
    print("  This file is intentionally NOT in corpus_manifest.json.")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    pdf_path = Path(args.pdf).expanduser()
    if not pdf_path.is_absolute():
        pdf_path = (REPO_ROOT / pdf_path).resolve()
    else:
        pdf_path = pdf_path.resolve()

    reasons = refuse_reasons(args.source_doc_id, pdf_path)
    if reasons:
        print("INGEST REFUSED - watcher only accepts PDFs outside the corpus.", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 2

    out = proposed_path(args.source_doc_id)
    if out.is_file() and not args.force and not args.dry_run:
        print(f"Proposal already exists at {out.relative_to(REPO_ROOT).as_posix()} (use --force)")
        return 1

    # Freeze past-year hashes before any work so a later promote can prove immutability.
    baseline_hashes = snapshot_year_hashes()
    write_immutable_baseline(
        baseline_hashes,
        note="Captured at Phase 6 ingest; past years must still match after promote.",
    )

    title = args.title or args.source_doc_id
    only_sections = args.only_section
    print(f"=== Phase 6 ingest ({args.source_doc_id}) ===")
    print(f"  pdf   : {pdf_path}")
    print(f"  title : {title}")
    print(f"  sha256: {file_sha256(pdf_path)}")
    print(f"  baseline years frozen: {len(baseline_hashes)}")

    proposal = extract_proposal(
        source_doc_id=args.source_doc_id,
        act_title=title,
        pdf_path=pdf_path,
        model=args.model,
        max_calls=args.max_calls,
        dry_run=args.dry_run,
        only_sections=only_sections,
    )

    if args.dry_run:
        print("\n  dry-run only - proposal not written")
        for section in proposal["sections"]:
            print(f"    {section['section_key']:<16} {section['status']}")
        return 0

    path = save_proposed(proposal)
    diff = proposal["diff"]["reliefs"]
    print(f"\n  wrote {path.relative_to(REPO_ROOT).as_posix()}")
    print(f"  included rows : {proposal['included_count']}")
    print(f"  diff vs {proposal['diff'].get('baseline_assessment_year')}: "
          f"new={len(diff['new'])} changed={len(diff['changed'])} "
          f"unchanged={len(diff['unchanged'])}")
    print("  proposed_for_assessment_year is empty - run set-year next")
    return 0


def cmd_set_year(args: argparse.Namespace) -> int:
    if not YA_RE.match(args.ya):
        print(f"Invalid assessment year {args.ya!r} (expected YYYY_YY)", file=sys.stderr)
        return 2

    try:
        proposal = load_proposed(args.source_doc_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    approved_path = APPROVED_DIR / f"{args.ya}.json"
    if approved_path.is_file():
        existing = json.loads(approved_path.read_text(encoding="utf-8"))
        if existing.get("entries"):
            print(
                f"REFUSED: approved/{args.ya}.json already has live entries. "
                "The watcher may only create a NEW year file, never rewrite one.",
                file=sys.stderr,
            )
            return 2

    proposal["proposed_for_assessment_year"] = args.ya
    proposal["proposed_year_set_at"] = now_iso()
    proposal["proposed_year_set_by"] = args.reviewer
    path = save_proposed(proposal)
    print(f"  set {args.source_doc_id} -> proposed_for_assessment_year={args.ya}")
    print(f"  updated {path.relative_to(REPO_ROOT).as_posix()}")
    return 0


def _map_compare_group(row: dict[str, Any], baseline_entries: list[dict[str, Any]]) -> str:
    """Prefer an explicit group; otherwise match baseline by display name."""
    group = str(row.get("compare_group_id") or "").strip()
    if group and not group.isdigit() and not group.startswith("relief_"):
        return group
    name = str(row.get("display_name") or "").strip().lower()
    for entry in baseline_entries:
        if entry.get("display_name", "").strip().lower() == name:
            return entry["compare_group_id"]
    # Heuristic for the demo personal-relief amendment wording.
    if "2,000,000" in str(row.get("quote", "")) or "2000000" == str(row.get("cap_amount") or ""):
        return "personal_relief"
    if "personal relief" in name or "assessment relief" in name:
        return "personal_relief"
    return group or f"proposed_{row.get('section_key', 'row')}"


def cmd_promote(args: argparse.Namespace) -> int:
    phase5 = p5()
    try:
        proposal = load_proposed(args.source_doc_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    ya = proposal.get("proposed_for_assessment_year")
    if not ya:
        print(
            "proposed_for_assessment_year is empty - run set-year first",
            file=sys.stderr,
        )
        return 2

    approved_path = APPROVED_DIR / f"{ya}.json"
    rates_path = RATES_DIR / f"{ya}.json"
    if approved_path.is_file() and json.loads(approved_path.read_text(encoding="utf-8")).get("entries"):
        print(
            f"REFUSED: approved/{ya}.json already exists with entries. "
            "Watcher promote creates a new year only.",
            file=sys.stderr,
        )
        return 2

    baseline = load_immutable_baseline()
    if baseline is None:
        hashes = snapshot_year_hashes()
        write_immutable_baseline(hashes, note="Auto-captured immediately before watcher promote")
        baseline_files = hashes
    else:
        baseline_files = dict(baseline["files"])
        # Drop the target YA from the baseline if a skeleton somehow exists.
        baseline_files.pop(f"approved/{ya}.json", None)
        baseline_files.pop(f"rates/{ya}.json", None)

    pre_problems = assert_past_years_unchanged(baseline_files)
    if pre_problems:
        print("IMMUTABILITY PRE-CHECK FAILED", file=sys.stderr)
        for problem in pre_problems:
            print(f"  - {problem}", file=sys.stderr)
        return 3

    baseline_ya = latest_approved_ya()
    if not baseline_ya:
        print("No existing approved year to carry forward from", file=sys.stderr)
        return 2

    base_approved = json.loads((APPROVED_DIR / f"{baseline_ya}.json").read_text(encoding="utf-8"))
    base_rates = json.loads((RATES_DIR / f"{baseline_ya}.json").read_text(encoding="utf-8"))

    included = [r for r in proposal.get("rows", []) if r.get("included")]
    reliefs = [r for r in included if r.get("row_kind") == "relief"]

    # Start from the latest live year, then supersede groups present in the proposal.
    entries_by_group = {
        e["compare_group_id"]: dict(e) for e in base_approved.get("entries", [])
    }
    overlays: list[dict[str, Any]] = []
    for row in reliefs:
        group = _map_compare_group(row, list(entries_by_group.values()))
        prior = entries_by_group.get(group)
        entry = {
            "entry_id": hashlib.sha1(
                f"{proposal['source_doc_id']}|{group}|{row.get('quote', '')}".encode()
            ).hexdigest()[:12],
            "compare_group_id": group,
            "display_name": (prior or {}).get("display_name") or row.get("display_name", ""),
            "question_prompt": (prior or {}).get("question_prompt")
            or row.get("question_prompt", ""),
            "sort_order": int((prior or {}).get("sort_order", 100)),
            "input_kind": (prior or {}).get("input_kind") or row.get("input_kind", "notice"),
            "auto_applied": bool((prior or {}).get("auto_applied", row.get("auto_applied", False))),
            "cap_amount": row.get("cap_amount") or None,
            "unit": row.get("unit") or "lkr",
            "engine_binding": (prior or {}).get("engine_binding") or {"kind": "none"},
            "act_name": proposal.get("act_title") or row.get("act_name", ""),
            "section_ref": row.get("section_ref", ""),
            "quote": row.get("quote", ""),
            "source_doc_id": proposal["source_doc_id"],
            "needs_manual_verification": True,
            "provenance": {
                "phase": 6,
                "watcher_proposal": proposal["source_doc_id"],
                "carried_forward_from": baseline_ya if prior else None,
                "effective_from": row.get("effective_from", ""),
                "quote_source": row.get("quote_source", ""),
                "quote_ok_full_doc": bool(row.get("quote_ok_full_doc")),
                "pass2_verbatim": bool(row.get("pass2_verbatim")),
                "extract_run_id": row.get("extract_run_id", proposal.get("run_id", "")),
                "pdf_sha256": proposal.get("pdf_sha256", ""),
                "reviewed_by": args.reviewer,
                "reviewed_at": now_iso(),
            },
        }
        entries_by_group[group] = entry
        overlays.append({"compare_group_id": group, "cap_amount": entry["cap_amount"]})

    entries = sorted(entries_by_group.values(), key=lambda e: (e["sort_order"], e["compare_group_id"]))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    approved_payload = {
        "spec_version": "1.1.0",
        "assessment_year": ya,
        "phase1_empty_skeleton": False,
        "promoted_at": now_iso(),
        "promotion_run": run_id,
        "promotion_source": "phase6_watcher",
        "watcher_source_doc_id": proposal["source_doc_id"],
        "carried_forward_from": baseline_ya,
        "notes": (
            "Phase 6 watcher promotion. New year only. Overlay values copied from the "
            "watcher proposal's quote-gated rows; other reliefs carried forward from "
            f"{baseline_ya}. Past year files were not opened for write."
        ),
        "entries": entries,
        "entry_count": len(entries),
    }
    approved_payload["content_sha256"] = phase5.canonical_sha256(approved_payload)

    # Rates: carry forward the latest ladder unless the proposal itself produced
    # a complete individual ladder (Phase 5 contiguity rules). Demo fixture keeps
    # the same 2025/26 bands and flags the year for manual verification.
    rates_payload = {
        "spec_version": "1.1.0",
        "assessment_year": ya,
        "currency": "LKR",
        "needs_manual_verification": True,
        "manual_verification": None,
        "promoted_at": now_iso(),
        "promotion_run": run_id,
        "promotion_source": "phase6_watcher",
        "watcher_source_doc_id": proposal["source_doc_id"],
        "carried_forward_from": baseline_ya,
        "bands": base_rates.get("bands", []),
        "surcharges": base_rates.get("surcharges", []),
        "special_formulas": base_rates.get("special_formulas", []),
        "provenance": {
            **(base_rates.get("provenance") or {}),
            "phase6_note": (
                "Bands carried forward from the previous live year; watcher proposal "
                "did not replace them unless a future extract adds a complete ladder."
            ),
        },
        "notes": (
            "Phase 6 watcher promotion. Rates stay needs_manual_verification until a "
            "human spot-check clears the flag. Past year rate files were not rewritten."
        ),
    }
    rates_payload["content_sha256"] = phase5.canonical_sha256(rates_payload)

    print(f"=== Phase 6 promote -> {ya}{' (dry run)' if args.dry_run else ''} ===")
    print(f"  baseline year     : {baseline_ya}")
    print(f"  overlay reliefs   : {len(overlays)}")
    for item in overlays:
        print(f"    - {item['compare_group_id']}: cap={item['cap_amount']}")
    print(f"  entries in new YA : {len(entries)}")
    print(f"  bands carried     : {len(rates_payload['bands'])}")

    if args.dry_run:
        print("  dry-run - no files written")
        return 0

    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    RATES_DIR.mkdir(parents=True, exist_ok=True)
    # Never use Phase 5's overwrite path on past years — write only the new YA.
    approved_path.write_text(
        json.dumps(approved_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    rates_path.write_text(
        json.dumps(rates_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    post_problems = assert_past_years_unchanged(baseline_files)
    if post_problems:
        # Roll back the new year files so a failed immutability check leaves no partial state.
        approved_path.unlink(missing_ok=True)
        rates_path.unlink(missing_ok=True)
        print("IMMUTABILITY POST-CHECK FAILED - new year files rolled back", file=sys.stderr)
        for problem in post_problems:
            print(f"  - {problem}", file=sys.stderr)
        return 3

    proposal["promoted_at"] = now_iso()
    proposal["promoted_by"] = args.reviewer
    proposal["promoted_assessment_year"] = ya
    proposal["promotion_run"] = run_id
    save_proposed(proposal)

    # Extend baseline so a later watcher run also protects this new year.
    updated = snapshot_year_hashes()
    write_immutable_baseline(
        updated,
        note=f"Updated after promoting {ya} from {proposal['source_doc_id']}",
    )

    print(f"  wrote approved/{ya}.json")
    print(f"  wrote rates/{ya}.json")
    print(f"  past year hashes unchanged ({len(baseline_files)} files checked)")
    return 0


def cmd_check_immutable(args: argparse.Namespace) -> int:
    baseline = load_immutable_baseline()
    if baseline is None:
        hashes = snapshot_year_hashes()
        write_immutable_baseline(hashes, note="Initial Phase 6 immutable baseline")
        print(f"  created baseline with {len(hashes)} files at "
              f"{HASH_BASELINE_PATH.relative_to(REPO_ROOT).as_posix()}")
        return 0

    # Optionally ignore years created by the watcher when checking "past" only.
    files = dict(baseline["files"])
    if args.past_only:
        for key in list(files):
            stem = Path(key).stem
            if stem not in {
                "2018_19",
                "2019_20",
                "2020_21",
                "2021_22",
                "2022_23",
                "2023_24",
                "2024_25",
                "2025_26",
            }:
                files.pop(key)

    problems = assert_past_years_unchanged(files)
    print("=== Phase 6 immutability check ===")
    print(f"  baseline captured : {baseline.get('captured_at')}")
    print(f"  files checked     : {len(files)}")
    if problems:
        print(f"  FAIL ({len(problems)})")
        for problem in problems:
            print(f"    - {problem}")
        return 3
    print("  PASS - every checked year file hash is unchanged")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relief Interview Phase 6 amendment watcher")
    parser.add_argument("--reviewer", default=getpass.getuser() or "unknown")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("list").set_defaults(func=cmd_list)

    p_show = sub.add_parser("show")
    p_show.add_argument("source_doc_id")
    p_show.set_defaults(func=cmd_show)

    sub.add_parser("refuse-corpus-docs").set_defaults(func=cmd_refuse_corpus_docs)

    p_demo = sub.add_parser("make-demo-pdf")
    p_demo.add_argument("--force", action="store_true")
    p_demo.set_defaults(func=cmd_make_demo_pdf)

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--pdf", required=True)
    p_ingest.add_argument("--source-doc-id", required=True)
    p_ingest.add_argument("--title", default=None)
    p_ingest.add_argument("--model", default="gpt-4o")
    p_ingest.add_argument("--max-calls", type=int, default=80)
    p_ingest.add_argument("--only-section", action="append", default=None)
    p_ingest.add_argument("--force", action="store_true")
    p_ingest.add_argument("--dry-run", action="store_true")
    p_ingest.set_defaults(func=cmd_ingest)

    p_year = sub.add_parser("set-year")
    p_year.add_argument("--source-doc-id", required=True)
    p_year.add_argument("--ya", required=True)
    p_year.set_defaults(func=cmd_set_year)

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("--source-doc-id", required=True)
    p_promote.add_argument("--dry-run", action="store_true")
    p_promote.set_defaults(func=cmd_promote)

    p_check = sub.add_parser("check-immutable")
    p_check.add_argument(
        "--past-only",
        action="store_true",
        help="Only check 2018/19–2025/26 (ignore later watcher-created years)",
    )
    p_check.set_defaults(func=cmd_check_immutable)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
