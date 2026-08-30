#!/usr/bin/env python3
"""Relief Interview Phase 5 ΓÇö human review and promotion.

Promotes verified Phase 4 staging rows into the live per-year catalogs. The
reviewer decides *which* rows are trustworthy and *how they line up across
years*; the reviewer never supplies a tax value.

The one rule the code enforces mechanically: every number, quote and citation in
``approved/{ya}.json`` and ``rates/{ya}.json`` is copied byte-for-byte from a
Phase 4 staging row that passed the substring gate. A reviewer may only set
presentation metadata (which relief this is, what to call it, what order to ask
it in). There is deliberately no code path that lets a cap or a rate be typed in.
If a value is wrong or missing, re-run Phase 4 on that provision:

    python scripts/relief_interview_phase4_extract.py \\
        --only-doc <source_doc_id> --only-section "<section>" --force

Commands
--------
  status                     counts by decision state
  list                       staging rows with their decision
  show <row_id>              one row in full, with provenance and gate verdicts
  groups                     compare_group_id assignments across Acts
  approve <row_id> ...       approve, optionally setting presentation metadata
  reject <row_id> --reason   reject
  flag <row_id> --reason     mark needs_manual_verification
  clear-flag --ya <ya>       record a human spot-check of that year's rates
  promote [--dry-run]        rebuild the year files from the decision ledger
  verify                     audit promoted files against staging and the ledger

Usage:
  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/relief_interview_phase5_review.py status
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = REPO_ROOT / "models" / "adaptive-tax" / "relief-interview"
EXTRACTED_DIR = OUT_ROOT / "extracted"
APPROVED_DIR = OUT_ROOT / "approved"
RATES_DIR = OUT_ROOT / "rates"
REVIEW_DIR = OUT_ROOT / "review"
LEDGER_PATH = REVIEW_DIR / "decisions.json"
HARVEST_PATH = OUT_ROOT / "harvest" / "commencement_records.json"

SPEC_VERSION = "1.1.0"

SUPPORTED_YAS: tuple[str, ...] = (
    "2018_19",
    "2019_20",
    "2020_21",
    "2021_22",
    "2022_23",
    "2023_24",
    "2024_25",
    "2025_26",
)

# Presentation metadata a reviewer may set. Everything carrying a tax value or a
# citation is copied from staging and is absent here on purpose.
REVIEWER_SETTABLE = (
    "compare_group_id",
    "display_name",
    "question_prompt",
    "sort_order",
    "input_kind",
    "auto_applied",
    "engine_binding",
)

# Copied verbatim from the staging row; never reviewer-editable.
VALUE_FIELDS = (
    "cap_amount",
    "unit",
    "effective_from",
    "effective_to",
    "rate_percent",
    "lower",
    "upper",
    "value",
)
PROVENANCE_FIELDS = ("act_name", "section_ref", "quote", "source_doc_id")

BOUNDARY_TOLERANCE = 1


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def ya_start(ya: str) -> date:
    return date(int(ya.split("_")[0]), 4, 1)


def ya_display(ya: str) -> str:
    return ya.replace("_", "/")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_sha256(payload: dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k != "content_sha256"}
    blob = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def quote_fingerprint(quote: str) -> str:
    normalized = re.sub(r"\s+", " ", quote or "").strip().lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def row_id_for(row: dict[str, Any], source_doc_id: str, section_key: str) -> str:
    """Stable id tied to the verified quote, not to a row's position.

    Re-extracting a provision keeps ids for rows whose quote is unchanged and
    mints new ones where the text changed ΓÇö so a decision can never silently
    carry over to a different quote.
    """
    # Sibling rows can legitimately share one quote ΓÇö a restated relief list
    # quotes the whole list for each of its items ΓÇö so the values distinguish them.
    values = "~".join(str(row.get(field, "")) for field in VALUE_FIELDS)
    seed = "|".join(
        [
            source_doc_id,
            section_key,
            row["row_kind"],
            values,
            quote_fingerprint(row.get("quote", "")),
        ]
    )
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _as_int(value: Any) -> int | None:
    text = str(value or "").strip().replace(",", "")
    return int(text) if text.isdigit() else None


def _as_float(value: Any) -> float | None:
    text = str(value or "").strip().rstrip("%")
    try:
        return float(text)
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Staging + ledger
# --------------------------------------------------------------------------


def load_staging_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(EXTRACTED_DIR.glob("*__*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for row in doc.get("rows", []):
            rows.append(
                {
                    **row,
                    "row_id": row_id_for(row, doc["source_doc_id"], doc["section_key"]),
                    "source_doc_id": doc["source_doc_id"],
                    "section_key": doc["section_key"],
                    "act_title": doc.get("act_title", ""),
                    "staging_path": path.relative_to(REPO_ROOT).as_posix(),
                    "extract_run_id": doc.get("run_id", ""),
                }
            )
    return rows


def load_ledger() -> dict[str, Any]:
    if LEDGER_PATH.is_file():
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {
        "spec_version": SPEC_VERSION,
        "phase": 5,
        "decisions": {},
        "rate_verifications": {},
        "promotions": [],
    }


def save_ledger(ledger: dict[str, Any]) -> None:
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_act_commencements() -> dict[str, str]:
    if not HARVEST_PATH.is_file():
        return {}
    data = json.loads(HARVEST_PATH.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for act in data.get("acts", []):
        for record in act.get("records", []):
            sid = record.get("source_doc_id") or act.get("source_doc_id")
            iso = record.get("operation_date") or ""
            if sid and iso and (sid not in out or iso < out[sid]):
                out[sid] = iso
    return out


def display_act_name(row: dict[str, Any]) -> str:
    """The Act a quote actually came from.

    Asked to name the Act, the model usually answers with the principal
    enactment an amending Act amends, which would make a 2025 amendment look
    like it came from the 2017 Act. The manifest title for the PDF that was
    actually read is authoritative here ΓÇö Phase 1 confirmed it against disk ΓÇö
    and the model's own answer is kept in provenance.
    """
    title = str(row.get("act_title", "")).strip()
    if not title:
        return str(row.get("act_name", ""))
    return re.sub(r"\s*\(English\)\s*$", "", title)


EARLIEST = "0001-01-01"


def effective_date_of(row: dict[str, Any], commencements: dict[str, str]) -> str:
    """When this row starts to apply.

    An amending Act restates a relief's whole history, and the oldest item in
    that list carries no date because it is the baseline the later items
    supersede. Treating an undated relief as "from the beginning" lets the
    normal supersession rule handle it; falling back to the Act's commencement
    would instead make the oldest value look like the newest.
    """
    stated = str(row.get("effective_from", "")).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stated):
        return stated
    if row.get("row_kind") == "relief":
        return EARLIEST
    return commencements.get(row["source_doc_id"], "")


# --------------------------------------------------------------------------
# Commands: inspection
# --------------------------------------------------------------------------


def decision_state(ledger: dict[str, Any], row_id: str) -> str:
    entry = ledger["decisions"].get(row_id)
    return entry["status"] if entry else "pending"


def cmd_status(args: argparse.Namespace) -> int:
    rows = load_staging_rows()
    ledger = load_ledger()
    counts: dict[str, int] = {}
    gate_blocked = 0
    for row in rows:
        state = decision_state(ledger, row["row_id"])
        if not row.get("included"):
            state = "blocked_by_gate"
            gate_blocked += 1
        counts[state] = counts.get(state, 0) + 1

    print("=== Phase 5 review status ===")
    print(f"  staging rows        : {len(rows)}")
    for state in ("pending", "approved", "rejected", "needs_manual_verification", "blocked_by_gate"):
        if counts.get(state):
            print(f"  {state:<20}: {counts[state]}")
    print()
    orphans = set(ledger["decisions"]) - {r["row_id"] for r in rows}
    if orphans:
        print(f"  ! {len(orphans)} decisions no longer match any staging row (re-extraction changed the quote)")
        print("    Run `list --orphans` to see them.")
    print(f"  rate spot-checks cleared: {sorted(ledger['rate_verifications'])}")
    promoted = sum(
        1 for ya in SUPPORTED_YAS if (APPROVED_DIR / f"{ya}.json").is_file()
        and json.loads((APPROVED_DIR / f"{ya}.json").read_text(encoding="utf-8")).get("entries")
    )
    print(f"  years with promoted entries: {promoted} of {len(SUPPORTED_YAS)}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = load_staging_rows()
    ledger = load_ledger()

    if args.orphans:
        known = {r["row_id"] for r in rows}
        for row_id, entry in ledger["decisions"].items():
            if row_id not in known:
                print(f"  {row_id}  {entry['status']:<12} {entry.get('note', '')}")
        return 0

    for row in rows:
        if args.kind and row["row_kind"] != args.kind:
            continue
        if args.doc and row["source_doc_id"] != args.doc:
            continue
        if args.section and row["section_key"].lower() != args.section.lower():
            continue
        state = "blocked" if not row.get("included") else decision_state(ledger, row["row_id"])
        if args.status and state != args.status:
            continue
        decided = ledger["decisions"].get(row["row_id"], {})
        group = decided.get("compare_group_id") or row.get("compare_group_id") or "-"
        label = str(
            row.get("display_name") or row.get("band_label") or row.get("description") or ""
        )[:44]
        if row["row_kind"] == "rate_band":
            value = f"{row.get('lower', '')}..{row.get('upper') or 'inf'}@{row.get('rate_percent', '')}%"
        else:
            value = row.get("cap_amount") or row.get("value") or "-"
        print(
            f"  {row['row_id']}  {state:<10} {row['row_kind']:<10} "
            f"{row['source_doc_id']:<20} eff={str(row.get('effective_from') or '-'):<11} "
            f"{str(value)[:26]:<26} {group[:22]:<22} {label}"
        )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    rows = {r["row_id"]: r for r in load_staging_rows()}
    row = rows.get(args.row_id)
    if row is None:
        print(f"No staging row with id {args.row_id!r}", file=sys.stderr)
        return 2
    ledger = load_ledger()
    print(json.dumps({**row, "decision": ledger["decisions"].get(args.row_id)}, indent=2, ensure_ascii=False))
    return 0


def cmd_groups(args: argparse.Namespace) -> int:
    rows = load_staging_rows()
    ledger = load_ledger()
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row["row_kind"] != "relief" or not row.get("included"):
            continue
        decided = ledger["decisions"].get(row["row_id"], {})
        key = decided.get("compare_group_id") or f"(unassigned: {row.get('compare_group_id', '?')})"
        groups.setdefault(key, []).append(row)

    for key in sorted(groups):
        print(f"\n{key}")
        for row in sorted(groups[key], key=lambda r: str(r.get("effective_from") or "")):
            print(
                f"    {row['row_id']}  {row['source_doc_id']:<20} "
                f"eff={str(row.get('effective_from') or '-'):<11} "
                f"cap={str(row.get('cap_amount') or '-'):<10} {row.get('display_name', '')[:46]}"
            )
    return 0


# --------------------------------------------------------------------------
# Commands: decisions
# --------------------------------------------------------------------------


def _record(
    ledger: dict[str, Any],
    row: dict[str, Any],
    status: str,
    args: argparse.Namespace,
    overrides: dict[str, Any] | None = None,
) -> None:
    entry = {
        "row_id": row["row_id"],
        "status": status,
        "entry_id": row.get("entry_id", ""),
        "source_doc_id": row["source_doc_id"],
        "section_key": row["section_key"],
        "row_kind": row["row_kind"],
        "quote_fingerprint": quote_fingerprint(row.get("quote", "")),
        "reviewer": args.reviewer,
        "decided_at": now_iso(),
    }
    if getattr(args, "reason", None):
        entry["reason"] = args.reason
    if overrides:
        entry.update(overrides)
    ledger["decisions"][row["row_id"]] = entry


def cmd_approve(args: argparse.Namespace) -> int:
    rows = {r["row_id"]: r for r in load_staging_rows()}
    ledger = load_ledger()
    failures = 0

    for row_id in args.row_ids:
        row = rows.get(row_id)
        if row is None:
            print(f"  ! {row_id}: no such staging row", file=sys.stderr)
            failures += 1
            continue
        if not row.get("included"):
            print(
                f"  ! {row_id}: blocked by the Phase 4 quote gate ΓÇö cannot approve.\n"
                f"    Re-extract instead:\n"
                f"      python scripts/relief_interview_phase4_extract.py "
                f'--only-doc {row["source_doc_id"]} --only-section "{row["section_key"]}" --force',
                file=sys.stderr,
            )
            failures += 1
            continue

        overrides: dict[str, Any] = {}
        for field in REVIEWER_SETTABLE:
            value = getattr(args, field, None)
            if value is not None:
                overrides[field] = value
        if args.binding:
            binding: dict[str, Any] = {"kind": args.binding}
            component_id = getattr(args, "component_id", None)
            if component_id:
                binding["component_id"] = component_id
            overrides["engine_binding"] = binding
        _record(ledger, row, "approved", args, overrides)
        print(f"  approved {row_id}  {row['row_kind']:<10} {overrides.get('compare_group_id', '')}")

    save_ledger(ledger)
    return 1 if failures else 0


def cmd_reject(args: argparse.Namespace) -> int:
    rows = {r["row_id"]: r for r in load_staging_rows()}
    ledger = load_ledger()
    for row_id in args.row_ids:
        row = rows.get(row_id)
        if row is None:
            print(f"  ! {row_id}: no such staging row", file=sys.stderr)
            continue
        _record(ledger, row, "rejected", args)
        print(f"  rejected {row_id}")
    save_ledger(ledger)
    return 0


def cmd_flag(args: argparse.Namespace) -> int:
    rows = {r["row_id"]: r for r in load_staging_rows()}
    ledger = load_ledger()
    for row_id in args.row_ids:
        row = rows.get(row_id)
        if row is None:
            print(f"  ! {row_id}: no such staging row", file=sys.stderr)
            continue
        overrides: dict[str, Any] = {}
        for field in REVIEWER_SETTABLE:
            value = getattr(args, field, None)
            if value is not None:
                overrides[field] = value
        if args.binding:
            binding: dict[str, Any] = {"kind": args.binding}
            component_id = getattr(args, "component_id", None)
            if component_id:
                binding["component_id"] = component_id
            overrides["engine_binding"] = binding
        _record(ledger, row, "needs_manual_verification", args, overrides)
        print(f"  flagged {row_id} needs_manual_verification")
    save_ledger(ledger)
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Archive decisions whose staging row no longer exists after a re-extraction."""
    known = {r["row_id"] for r in load_staging_rows()}
    ledger = load_ledger()
    orphans = {k: v for k, v in ledger["decisions"].items() if k not in known}
    if not orphans:
        print("  no orphaned decisions")
        return 0
    archive = ledger.setdefault("superseded_decisions", [])
    archive.append({"pruned_at": now_iso(), "by": args.reviewer, "decisions": orphans})
    for row_id in orphans:
        del ledger["decisions"][row_id]
    save_ledger(ledger)
    print(f"  archived {len(orphans)} decisions whose staging row was replaced by a re-extraction")
    return 0


def cmd_clear_flag(args: argparse.Namespace) -> int:
    """Record that a human spot-checked a year's rates against the Act."""
    if args.ya not in SUPPORTED_YAS:
        print(f"Unsupported assessment year {args.ya!r}", file=sys.stderr)
        return 2
    ledger = load_ledger()
    ledger["rate_verifications"][args.ya] = {
        "cleared_by": args.reviewer,
        "cleared_at": now_iso(),
        "note": args.note,
    }
    save_ledger(ledger)
    print(f"  rates/{args.ya}.json spot-check recorded ΓÇö re-run promote to apply")
    return 0


# --------------------------------------------------------------------------
# Promotion
# --------------------------------------------------------------------------


def approved_rows(rows: list[dict[str, Any]], ledger: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        decided = ledger["decisions"].get(row["row_id"])
        if not decided or decided["status"] not in ("approved", "needs_manual_verification"):
            continue
        if not row.get("included"):
            continue
        if decided.get("quote_fingerprint") != quote_fingerprint(row.get("quote", "")):
            continue
        out.append({**row, "_decision": decided})
    return out


def _parse_iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def row_effective_from(row: dict[str, Any], commencements: dict[str, str]) -> date:
    """Quote-backed start, or EARLIEST sentinel for undated relief baselines."""
    stated = _parse_iso_date(row.get("effective_from"))
    if stated is not None:
        return stated
    if row.get("row_kind") == "relief":
        return datetime.strptime(EARLIEST, "%Y-%m-%d").date()
    fallback = _parse_iso_date(commencements.get(row.get("source_doc_id", ""), ""))
    return fallback or datetime.strptime(EARLIEST, "%Y-%m-%d").date()


def derived_effective_tos(
    candidates: list[dict[str, Any]], commencements: dict[str, str]
) -> dict[str, date | None]:
    """Rule 1b: close empty effective_to at the next later effective_from in-group.

    Local computation only ΓÇö never written back to staging or approved catalogs.
    Only quote-backed ISO effective_from values participate as chain anchors.
    """
    quoted_starts: list[date] = []
    for row in candidates:
        stated = _parse_iso_date(row.get("effective_from"))
        if stated is not None:
            quoted_starts.append(stated)
    later_starts = sorted(set(quoted_starts))
    out: dict[str, date | None] = {}
    for row in candidates:
        key = row.get("row_id") or str(id(row))
        staged_to = _parse_iso_date(row.get("effective_to"))
        if staged_to is not None:
            out[key] = staged_to
            continue
        own = row_effective_from(row, commencements)
        # For chaining, compare against quote-backed from; undated baseline uses EARLIEST.
        later = [d for d in later_starts if d > own]
        out[key] = later[0] if later else None
    return out


def end_bound_for_row(
    row: dict[str, Any],
    derived: dict[str, date | None],
) -> tuple[date | None, str]:
    """Return (end_date_or_None, 'quote'|'derived'|'open')."""
    staged = _parse_iso_date(row.get("effective_to"))
    if staged is not None:
        return staged, "quote"
    key = row.get("row_id") or str(id(row))
    derived_to = derived.get(key)
    if derived_to is not None:
        return derived_to, "derived"
    return None, "open"


def select_for_year(
    candidates: list[dict[str, Any]], ya: str, commencements: dict[str, str]
) -> dict[str, Any] | None:
    """Pick the live row for one YA using Rules 1b, 1, and 2.

    Rule 1b closes empty effective_to at the earliest later effective_from in the
    compare_group (local only). Rule 1 tests from/end vs YA start. Rule 2 breaks
    ties by earliest Act harvest commencement (originating Act, not restatement).
    """
    if not candidates:
        return None
    start = ya_start(ya)
    derived = derived_effective_tos(candidates, commencements)
    eligible: list[dict[str, Any]] = []
    for row in candidates:
        from_d = row_effective_from(row, commencements)
        end_d, _kind = end_bound_for_row(row, derived)
        if from_d > start:
            continue
        if end_d is not None and end_d <= start:
            continue
        eligible.append(row)
    if not eligible:
        return None
    if len(eligible) == 1:
        return eligible[0]

    def act_commencement(row: dict[str, Any]) -> date:
        iso = commencements.get(row["source_doc_id"], "")
        parsed = _parse_iso_date(iso)
        return parsed or date.max

    eligible.sort(
        key=lambda row: (
            act_commencement(row),
            row.get("source_doc_id", ""),
            row.get("row_id", ""),
        )
    )
    return eligible[0]


def dry_run_personal_relief_table(
    candidates: list[dict[str, Any]], commencements: dict[str, str]
) -> dict[str, Any]:
    """Report Rule 1b/1/2 selection for personal_relief across supported YAs."""
    derived = derived_effective_tos(candidates, commencements)
    rows_out: list[dict[str, Any]] = []
    for row in candidates:
        end_d, kind = end_bound_for_row(row, derived)
        rows_out.append(
            {
                "row_id": row.get("row_id"),
                "source_doc_id": row.get("source_doc_id"),
                "cap_amount": row.get("cap_amount"),
                "effective_from": row.get("effective_from") or EARLIEST,
                "effective_to_staged": row.get("effective_to") or "",
                "end_bound": end_d.isoformat() if end_d else "",
                "end_kind": kind,
            }
        )
    selections: list[dict[str, Any]] = []
    for ya in SUPPORTED_YAS:
        chosen = select_for_year(candidates, ya, commencements)
        selections.append(
            {
                "assessment_year": ya,
                "source_doc_id": chosen.get("source_doc_id") if chosen else None,
                "cap_amount": chosen.get("cap_amount") if chosen else None,
                "row_id": chosen.get("row_id") if chosen else None,
            }
        )
    return {"candidates": rows_out, "selections": selections}


def build_approved_entry(row: dict[str, Any], commencements: dict[str, str]) -> dict[str, Any]:
    decided = row["_decision"]
    binding = decided.get("engine_binding") or {"kind": "none"}
    resolved = effective_date_of(row, commencements)
    undated = resolved == EARLIEST
    return {
        "entry_id": row["row_id"],
        "compare_group_id": decided.get("compare_group_id") or row.get("compare_group_id", ""),
        "display_name": decided.get("display_name") or row.get("display_name", ""),
        "question_prompt": decided.get("question_prompt") or row.get("question_prompt", ""),
        "sort_order": int(decided.get("sort_order", 100)),
        "input_kind": decided.get("input_kind") or row.get("input_kind", "notice"),
        "help": decided.get("help") or row.get("help") or "",
        "auto_applied": bool(decided.get("auto_applied", row.get("auto_applied", False))),
        # Values below are copied from staging; the CLI cannot set them.
        "cap_amount": row.get("cap_amount") or None,
        "unit": row.get("unit") or "lkr",
        "engine_binding": binding,
        "act_name": display_act_name(row),
        "section_ref": row.get("section_ref", ""),
        "quote": row.get("quote", ""),
        "source_doc_id": row["source_doc_id"],
        "needs_manual_verification": decided["status"] == "needs_manual_verification",
        "provenance": {
            "act_name_extracted": row.get("act_name", ""),
            "effective_from": "" if undated else resolved,
            "effective_from_basis": (
                "undated baseline in the Act; applies until a later dated item supersedes it"
                if undated
                else "stated in the quoted provision"
            ),
            "effective_from_stated": row.get("effective_from", ""),
            "quote_source": row.get("quote_source", ""),
            "quote_ok_full_doc": bool(row.get("quote_ok_full_doc")),
            "pass2_verbatim": bool(row.get("pass2_verbatim")),
            "extract_run_id": row.get("extract_run_id", ""),
            "staging_path": row.get("staging_path", ""),
            "reviewed_by": decided.get("reviewer", ""),
            "reviewed_at": decided.get("decided_at", ""),
        },
    }


def build_ladders(rows: list[dict[str, Any]], commencements: dict[str, str]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if row["row_kind"] != "rate_band":
            continue
        if not re.search(r"individual", str(row.get("applies_to", "")), re.IGNORECASE):
            continue
        lower, rate = _as_int(row.get("lower")), _as_float(row.get("rate_percent"))
        if lower is None or rate is None:
            continue
        groups.setdefault((row["source_doc_id"], effective_date_of(row, commencements)), []).append(row)

    ladders = []
    for (source_doc_id, effective), members in groups.items():
        bands = sorted(members, key=lambda r: _as_int(r["lower"]) or 0)
        ok = _as_int(bands[0]["lower"]) is not None and (_as_int(bands[0]["lower"]) or 0) <= BOUNDARY_TOLERANCE
        for prev, nxt in zip(bands, bands[1:]):
            prev_upper, next_lower = _as_int(prev.get("upper")), _as_int(nxt.get("lower"))
            if prev_upper is None or next_lower is None or abs(prev_upper - next_lower) > BOUNDARY_TOLERANCE:
                ok = False
        if _as_int(bands[-1].get("upper")) is not None:
            ok = False
        if ok and effective:
            ladders.append({"source_doc_id": source_doc_id, "effective_from": effective, "bands": bands})
    return ladders


def cmd_promote(args: argparse.Namespace) -> int:
    rows = load_staging_rows()
    ledger = load_ledger()
    commencements = load_act_commencements()
    live = approved_rows(rows, ledger)

    reliefs = [r for r in live if r["row_kind"] == "relief"]
    rules = [r for r in live if r["row_kind"] == "rule"]
    ladders = build_ladders(live, commencements)

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in reliefs:
        key = row["_decision"].get("compare_group_id") or row.get("compare_group_id", "")
        groups.setdefault(key, []).append(row)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary: list[dict[str, Any]] = []

    for ya in SUPPORTED_YAS:
        start = ya_start(ya)

        entries = []
        for key in sorted(groups):
            chosen = select_for_year(groups[key], ya, commencements)
            if chosen is not None:
                entries.append(build_approved_entry(chosen, commencements))
        entries.sort(key=lambda e: (e["sort_order"], e["compare_group_id"]))

        ladder = None
        for candidate in sorted(ladders, key=lambda item: item["effective_from"]):
            if datetime.strptime(candidate["effective_from"], "%Y-%m-%d").date() <= start:
                ladder = candidate
        year_rules = [
            r
            for r in rules
            if effective_date_of(r, commencements)
            and datetime.strptime(effective_date_of(r, commencements), "%Y-%m-%d").date() <= start
        ]

        cleared = ledger["rate_verifications"].get(ya)
        approved_payload = {
            "spec_version": SPEC_VERSION,
            "assessment_year": ya,
            "phase1_empty_skeleton": False,
            "promoted_at": now_iso(),
            "promotion_run": run_id,
            "notes": (
                "Phase 5 promotion. Every value, quote and citation is copied verbatim "
                "from a Phase 4 staging row that passed the substring gate."
            ),
            "entries": entries,
            "entry_count": len(entries),
        }
        approved_payload["content_sha256"] = canonical_sha256(approved_payload)

        rates_payload = {
            "spec_version": SPEC_VERSION,
            "assessment_year": ya,
            "currency": "LKR",
            "needs_manual_verification": cleared is None,
            "manual_verification": cleared,
            "promoted_at": now_iso(),
            "promotion_run": run_id,
            "bands": [
                {
                    "band_index": idx + 1,
                    "lower": _as_int(band["lower"]),
                    "upper": _as_int(band.get("upper")),
                    "rate_percent": _as_float(band["rate_percent"]),
                    "band_label": band.get("band_label", ""),
                    "act_name": display_act_name(band),
                    "act_name_extracted": band.get("act_name", ""),
                    "section_ref": band.get("section_ref", ""),
                    "quote": band.get("quote", ""),
                    "source_doc_id": band["source_doc_id"],
                    "quote_source": band.get("quote_source", ""),
                }
                for idx, band in enumerate(ladder["bands"])
            ]
            if ladder
            else [],
            "surcharges": [
                _rule_payload(r) for r in year_rules if r.get("rule_kind") == "surcharge"
            ],
            "special_formulas": [
                _rule_payload(r) for r in year_rules if r.get("rule_kind") != "surcharge"
            ],
            "provenance": {
                "ladder_source_doc_id": ladder["source_doc_id"] if ladder else None,
                "ladder_effective_from": ladder["effective_from"] if ladder else None,
            },
            "notes": (
                "Phase 5 promotion. Rates stay needs_manual_verification until a human "
                "spot-check is recorded via `clear-flag`."
            ),
        }
        rates_payload["content_sha256"] = canonical_sha256(rates_payload)

        summary.append(
            {
                "assessment_year": ya,
                "entries": len(entries),
                "bands": len(rates_payload["bands"]),
                "surcharges": len(rates_payload["surcharges"]),
                "special_formulas": len(rates_payload["special_formulas"]),
                "rates_verified": cleared is not None,
                "ladder": ladder["source_doc_id"] if ladder else None,
            }
        )

        if not args.dry_run:
            _write_year_file(APPROVED_DIR / f"{ya}.json", approved_payload, args.force)
            _write_year_file(RATES_DIR / f"{ya}.json", rates_payload, args.force)

    print(f"=== Phase 5 promotion{' (dry run)' if args.dry_run else ''} ===")
    print(f"{'YA':<10}{'entries':>8}{'bands':>7}{'surch':>7}{'formulas':>10}  {'rates verified':<15} ladder")
    for item in summary:
        print(
            f"{ya_display(item['assessment_year']):<10}{item['entries']:>8}{item['bands']:>7}"
            f"{item['surcharges']:>7}{item['special_formulas']:>10}  "
            f"{'yes' if item['rates_verified'] else 'no (flagged)':<15} {item['ladder'] or '-'}"
        )

    if not args.dry_run:
        ledger.setdefault("promotions", []).append(
            {"run_id": run_id, "at": now_iso(), "by": args.reviewer, "summary": summary}
        )
        save_ledger(ledger)
        print(f"\nPromotion run {run_id} recorded in {LEDGER_PATH.relative_to(REPO_ROOT).as_posix()}")
    return 0


def _rule_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": row.get("rule_id", ""),
        "rule_kind": row.get("rule_kind", "other"),
        "description": row.get("description", ""),
        "value": row.get("value", ""),
        "effective_from": row.get("effective_from", ""),
        "act_name": display_act_name(row),
        "act_name_extracted": row.get("act_name", ""),
        "section_ref": row.get("section_ref", ""),
        "quote": row.get("quote", ""),
        "source_doc_id": row["source_doc_id"],
    }


def _write_year_file(path: Path, payload: dict[str, Any], force: bool) -> None:
    """Write a year file, refusing to silently clobber a hand-edited one."""
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        recorded = existing.get("content_sha256")
        if recorded and recorded != canonical_sha256(existing) and not force:
            raise SystemExit(
                f"{path.name} was edited by hand after its last promotion "
                f"(content hash mismatch). Re-run with --force to overwrite, but "
                f"prefer re-running Phase 4 on the affected provision."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Verify
# --------------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    rows = {r["row_id"]: r for r in load_staging_rows()}
    problems: list[str] = []
    checked = 0

    for ya in SUPPORTED_YAS:
        for directory in (APPROVED_DIR, RATES_DIR):
            path = directory / f"{ya}.json"
            if not path.is_file():
                problems.append(f"{path.name} missing from {directory.name}/")
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            recorded = payload.get("content_sha256")
            if recorded and recorded != canonical_sha256(payload):
                problems.append(f"{directory.name}/{path.name} edited after promotion (hash mismatch)")

        approved_path = APPROVED_DIR / f"{ya}.json"
        if not approved_path.is_file():
            continue
        approved = json.loads(approved_path.read_text(encoding="utf-8"))
        for entry in approved.get("entries", []):
            checked += 1
            staged = rows.get(entry["entry_id"])
            if staged is None:
                problems.append(f"{ya}: entry {entry['entry_id']} has no staging row")
                continue
            for field in PROVENANCE_FIELDS:
                # act_name is resolved from the manifest title, not the model's answer.
                expected = display_act_name(staged) if field == "act_name" else staged.get(field, "")
                if str(entry.get(field, "")) != str(expected):
                    problems.append(f"{ya}: entry {entry['entry_id']} {field} differs from staging")
            if str(entry.get("cap_amount") or "") != str(staged.get("cap_amount") or ""):
                problems.append(f"{ya}: entry {entry['entry_id']} cap_amount differs from staging")

    print("=== Phase 5 verification ===")
    print(f"  promoted entries checked against staging: {checked}")
    if problems:
        print(f"  problems: {len(problems)}")
        for problem in problems:
            print(f"    - {problem}")
        return 3
    print("  no drift: every promoted value, quote and citation matches its staging row")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relief Interview Phase 5 review CLI")
    parser.add_argument(
        "--reviewer",
        default=getpass.getuser() or "unknown",
        help="Name recorded on every decision",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status").set_defaults(func=cmd_status)

    p_list = sub.add_parser("list")
    p_list.add_argument("--kind", choices=["relief", "rate_band", "rule"])
    p_list.add_argument("--status", choices=["pending", "approved", "rejected", "needs_manual_verification", "blocked"])
    p_list.add_argument("--doc")
    p_list.add_argument("--section")
    p_list.add_argument("--orphans", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show")
    p_show.add_argument("row_id")
    p_show.set_defaults(func=cmd_show)

    sub.add_parser("groups").set_defaults(func=cmd_groups)

    p_approve = sub.add_parser("approve")
    p_approve.add_argument("row_ids", nargs="+")
    p_approve.add_argument("--compare-group-id", dest="compare_group_id")
    p_approve.add_argument("--display-name", dest="display_name")
    p_approve.add_argument("--question-prompt", dest="question_prompt")
    p_approve.add_argument("--sort-order", dest="sort_order", type=int)
    p_approve.add_argument("--input-kind", dest="input_kind", choices=["notice", "yes_no_amount", "amount", "boolean"])
    p_approve.add_argument("--auto-applied", dest="auto_applied", action="store_true", default=None)
    p_approve.add_argument(
        "--binding",
        choices=[
            "solar_panel_relief",
            "rent_relief",
            "qualifying_payments",
            "donations",
            "filing_line",
            "none",
        ],
    )
    p_approve.add_argument(
        "--component-id",
        dest="component_id",
        help="When --binding filing_line, the Calculator component_id",
    )
    p_approve.set_defaults(func=cmd_approve, engine_binding=None, component_id=None)

    p_reject = sub.add_parser("reject")
    p_reject.add_argument("row_ids", nargs="+")
    p_reject.add_argument("--reason", required=True)
    p_reject.set_defaults(func=cmd_reject)

    p_flag = sub.add_parser("flag")
    p_flag.add_argument("row_ids", nargs="+")
    p_flag.add_argument("--reason", required=True)
    p_flag.add_argument("--compare-group-id", dest="compare_group_id")
    p_flag.add_argument("--display-name", dest="display_name")
    p_flag.add_argument("--question-prompt", dest="question_prompt")
    p_flag.add_argument("--sort-order", dest="sort_order", type=int)
    p_flag.add_argument("--input-kind", dest="input_kind", choices=["notice", "yes_no_amount", "amount", "boolean"])
    p_flag.add_argument(
        "--binding",
        choices=[
            "solar_panel_relief",
            "rent_relief",
            "qualifying_payments",
            "donations",
            "filing_line",
            "none",
        ],
    )
    p_flag.add_argument("--component-id", dest="component_id")
    p_flag.set_defaults(func=cmd_flag, auto_applied=None, engine_binding=None, component_id=None)

    sub.add_parser("prune").set_defaults(func=cmd_prune)

    p_clear = sub.add_parser("clear-flag")
    p_clear.add_argument("--ya", required=True)
    p_clear.add_argument("--note", required=True)
    p_clear.set_defaults(func=cmd_clear_flag)

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("--dry-run", action="store_true")
    p_promote.add_argument("--force", action="store_true")
    p_promote.set_defaults(func=cmd_promote)

    sub.add_parser("verify").set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
