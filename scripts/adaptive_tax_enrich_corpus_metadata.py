#!/usr/bin/env python3
"""Optional GPT assist for corpus chunk metadata (Phase 5) — MANUAL ONLY.

NOT part of the main rebuild path. Required path first:

  PDF → deterministic chunking → deterministic metadata → Chroma → evaluation

Only after that, and only if ``needs_review`` chunks remain, a human may run this
script. It never feeds the Rule Engine. CI/offline does not require OPENAI_API_KEY.

Examples::

  # List needs_review candidates (no API call)
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_enrich_corpus_metadata.py --dry-run

  # Apply validated GPT metadata to a new JSONL (does not touch Chroma)
  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_enrich_corpus_metadata.py `
    --apply --out data/processed/adaptive-tax/corpus_v1.gpt_enriched.jsonl

  # After human accepts the enriched file, optionally re-index:
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_build_chroma.py `
    --corpus-jsonl data/processed/adaptive-tax/corpus_v1.gpt_enriched.jsonl --reset
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
for p in (_REPO, _REPO / "backend" / "comp-adaptive-tax", _SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

REQUIRED_SECTION_KEYS = frozenset(
    {"2", "5", "6", "7", "8", "11", "16", "52", "89", "first_schedule"}
)

_SYSTEM = """You assist with metadata tagging for Sri Lankan Inland Revenue Act PDF chunks.
Return JSON only. Do not invent tax rates, caps, or legal applicability.
If uncertain, set fields to null and needs_review=true.
primary_section must be one of the provided candidates or null.
effective_date only if explicitly stated in the chunk text.
Never invent sections not in candidates.
This is evidence metadata only — not executable tax rules.
"""


def chunk_needs_review(row: dict[str, Any]) -> bool:
    if row.get("needs_review") is True:
        return True
    if row.get("is_toc") or row.get("is_header_footer"):
        return False
    src = str(row.get("metadata_source") or "")
    if src == "gpt_assisted":
        return False
    ref = row.get("section_ref")
    if ref is None or ref == "" or ref == []:
        text = row.get("text") or ""
        if len(str(text)) >= 120:
            return True
    return False


def deterministic_section_candidates(row: dict[str, Any]) -> list[str]:
    """Allowed primary section labels for validation (reject inventions)."""
    found: list[str] = []
    for key in ("section_ref", "section_refs", "referenced_sections", "schedule_ref"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            found.append(val.strip())
        elif isinstance(val, list):
            found.extend(str(x).strip() for x in val if str(x).strip())
    text = str(row.get("text") or "")
    for m in re.finditer(r"(?i)\bsection\s+(\d+[a-z]?)\b", text):
        prefix = text[max(0, m.start() - 12) : m.start()].lower()
        if "subsection" in prefix or "sub-section" in prefix:
            continue
        found.append(f"Section {m.group(1)}")
    if re.search(r"(?i)\bfirst\s+schedule\b", text):
        found.append("First Schedule")
    # Always allow required calculator sections as candidates for review
    for key in sorted(REQUIRED_SECTION_KEYS):
        if key == "first_schedule":
            found.append("First Schedule")
        else:
            found.append(f"Section {key}")
    return list(dict.fromkeys(found))


def _normalize_section_label(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    text = str(value).strip()
    if re.fullmatch(r"(?i)first\s+schedule", text):
        return "First Schedule"
    m = re.fullmatch(r"(?i)(?:section\s+)?(\d+[a-z]?)", text)
    if m:
        return f"Section {m.group(1)}"
    return text


def validate_enrichment(
    proposal: dict[str, Any],
    *,
    candidates: list[str],
    chunk_text: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Accept only non-invented section/date fields. Returns (patch, rejects)."""
    rejects: list[str] = []
    allowed = {_normalize_section_label(c) for c in candidates}
    allowed.discard(None)

    primary = _normalize_section_label(proposal.get("primary_section"))
    if primary is not None and primary not in allowed:
        rejects.append(f"invented_primary_section:{primary}")
        primary = None

    referenced_out: list[str] = []
    for item in proposal.get("referenced_sections") or []:
        lab = _normalize_section_label(str(item))
        if lab is None:
            continue
        if lab not in allowed:
            rejects.append(f"invented_referenced_section:{lab}")
            continue
        referenced_out.append(lab)

    eff = proposal.get("effective_date")
    if eff is not None and str(eff).strip():
        eff_s = str(eff).strip()
        # Must appear in chunk text (loose) — never invent dates
        digits = re.sub(r"[^0-9]", "", eff_s)
        if len(digits) < 4 or digits[:4] not in (chunk_text or ""):
            # also allow ISO date year in text
            year_m = re.match(r"(\d{4})", eff_s)
            if not year_m or year_m.group(1) not in (chunk_text or ""):
                rejects.append(f"invented_effective_date:{eff_s}")
                eff = None
            else:
                eff = eff_s
        else:
            eff = eff_s
    else:
        eff = None

    if proposal.get("uncertain") is True or proposal.get("needs_review") is True:
        if primary is None and not referenced_out:
            return None, rejects + ["uncertain_no_fields"]

    if primary is None and not referenced_out and eff is None:
        return None, rejects + ["empty_after_validation"] if rejects else ["empty_proposal"]

    schedule = proposal.get("schedule")
    schedule_n = None
    if schedule and str(schedule).strip():
        schedule_n = _normalize_section_label(str(schedule))
        if schedule_n not in allowed and "schedule" not in str(schedule).lower():
            rejects.append(f"invented_schedule:{schedule}")
            schedule_n = None

    paragraph = proposal.get("paragraph")
    paragraph_n = None
    if paragraph and str(paragraph).strip():
        paragraph_n = str(paragraph).strip()
        # Must be grounded in text
        compact = paragraph_n.replace(" ", "")
        if compact.lower() not in (chunk_text or "").lower().replace(" ", ""):
            rejects.append(f"invented_paragraph:{paragraph_n}")
            paragraph_n = None

    patch: dict[str, Any] = {
        "metadata_source": "gpt_assisted",
        "needs_review": False,
    }
    if primary is not None:
        patch["section_ref"] = primary
    if referenced_out:
        existing = []
        if primary:
            existing.append(primary)
        existing.extend(referenced_out)
        patch["section_refs"] = list(dict.fromkeys(existing))
    if schedule_n:
        patch["schedule_ref"] = schedule_n
    if paragraph_n:
        patch["paragraph_ref"] = paragraph_n
    if eff:
        patch["effective_start_date"] = eff
    if proposal.get("provision_type"):
        # descriptive only — not executable
        patch["provision_type_hint"] = str(proposal.get("provision_type"))[:64]
    if proposal.get("operative_or_cross_reference") in {
        "operative",
        "cross_reference",
        "toc",
        "header_footer",
    }:
        kind = proposal["operative_or_cross_reference"]
        patch["is_operative_provision"] = kind == "operative"
        patch["is_cross_reference"] = kind == "cross_reference"
        patch["is_toc"] = kind == "toc"
        patch["is_header_footer"] = kind == "header_footer"

    return patch, rejects


def build_user_prompt(row: dict[str, Any], candidates: list[str]) -> str:
    return json.dumps(
        {
            "chunk_id": row.get("chunk_id"),
            "source_doc_id": row.get("source_doc_id"),
            "page": row.get("page"),
            "deterministic_candidates": candidates,
            "current_section_ref": row.get("section_ref"),
            "text": (row.get("text") or "")[:4000],
            "return_schema": {
                "primary_section": "string|null — must be in deterministic_candidates",
                "referenced_sections": "string[]",
                "schedule": "string|null",
                "paragraph": "string|null e.g. 52(4)",
                "provision_type": "string|null",
                "operative_or_cross_reference": "operative|cross_reference|toc|header_footer|null",
                "effective_date": "YYYY-MM-DD|null — only if explicit in text",
                "assessment_year": "null — do not invent",
                "uncertain": "boolean",
                "needs_review": "boolean",
            },
        },
        ensure_ascii=False,
    )


def call_openai_metadata(
    row: dict[str, Any],
    candidates: list[str],
    *,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": build_user_prompt(row, candidates)},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = completion.choices[0].message.content or "{}"
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("OpenAI metadata response must be a JSON object")
    return data


def select_candidates(
    rows: list[dict[str, Any]],
    *,
    limit: int | None,
    required_only: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not chunk_needs_review(row):
            continue
        if required_only:
            # Prefer chunks that mention required sections in text or candidates
            cands = deterministic_section_candidates(row)
            if not any(
                (k == "first_schedule" and "First Schedule" in cands)
                or f"Section {k}" in cands
                for k in REQUIRED_SECTION_KEYS
                if k != "first_schedule"
            ) and "First Schedule" not in cands:
                # still include if text mentions required section numbers
                text = str(row.get("text") or "")
                if not re.search(
                    r"(?i)\b(?:section\s+)?(?:2|5|6|7|8|11|16|52|89)\b|first\s+schedule",
                    text,
                ):
                    continue
        out.append(row)
        if limit is not None and len(out) >= limit:
            break
    return out


def enrich_corpus(
    *,
    corpus_jsonl: Path,
    out_jsonl: Path | None,
    dry_run: bool,
    apply: bool,
    limit: int | None,
    required_only: bool,
    model: str,
    api_key: str | None,
) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in corpus_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidates_rows = select_candidates(rows, limit=limit, required_only=required_only)

    summary: dict[str, Any] = {
        "corpus": str(corpus_jsonl.as_posix()),
        "total_chunks": len(rows),
        "needs_review_selected": len(candidates_rows),
        "dry_run": dry_run,
        "apply": apply,
        "accepted": 0,
        "rejected": 0,
        "skipped_no_api": 0,
        "details": [],
        "note": (
            "Manual GPT metadata assist only. Does not modify Rule Engine. "
            "Does not rebuild Chroma unless you run adaptive_tax_build_chroma.py separately."
        ),
    }

    if dry_run or not apply:
        for row in candidates_rows[:50]:
            summary["details"].append(
                {
                    "chunk_id": row.get("chunk_id"),
                    "source_doc_id": row.get("source_doc_id"),
                    "page": row.get("page"),
                    "candidates": deterministic_section_candidates(row)[:12],
                }
            )
        if not apply:
            summary["message"] = (
                "Dry listing only. Pass --apply (and OPENAI_API_KEY) to write enrichments."
            )
        return summary

    if not api_key:
        summary["skipped_no_api"] = len(candidates_rows)
        summary["message"] = (
            "OPENAI_API_KEY not set — refusing to call OpenAI. "
            "Corpus build never requires this key."
        )
        return summary

    by_id = {str(r.get("chunk_id")): r for r in rows}
    for row in candidates_rows:
        cid = str(row.get("chunk_id"))
        cands = deterministic_section_candidates(row)
        try:
            proposal = call_openai_metadata(row, cands, api_key=api_key, model=model)
        except Exception as exc:  # noqa: BLE001
            summary["rejected"] += 1
            summary["details"].append({"chunk_id": cid, "error": str(exc)})
            continue
        patch, rejects = validate_enrichment(
            proposal, candidates=cands, chunk_text=str(row.get("text") or "")
        )
        if patch is None:
            summary["rejected"] += 1
            summary["details"].append({"chunk_id": cid, "rejects": rejects, "proposal": proposal})
            continue
        target = by_id.get(cid)
        if target is None:
            continue
        target.update(patch)
        summary["accepted"] += 1
        summary["details"].append({"chunk_id": cid, "patch": patch, "rejects": rejects})

    dest = out_jsonl or corpus_jsonl.with_suffix(".gpt_enriched.jsonl")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary["wrote"] = str(dest.as_posix())
    summary["message"] = (
        f"Wrote enriched corpus to {dest}. "
        "Review, then re-index Chroma manually if accepted "
        "(scripts/adaptive_tax_build_chroma.py --reset)."
    )
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=_REPO / "data" / "processed" / "adaptive-tax" / "corpus_v1.jsonl",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSONL (default: corpus_v1.gpt_enriched.jsonl beside input)",
    )
    p.add_argument("--dry-run", action="store_true", help="List needs_review only (default)")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Call OpenAI and write validated metadata to --out (never default rebuild)",
    )
    p.add_argument("--limit", type=int, default=None)
    p.add_argument(
        "--required-only",
        action="store_true",
        default=True,
        help="Prefer chunks related to calculator-required sections (default)",
    )
    p.add_argument("--all-needs-review", action="store_true")
    p.add_argument("--model", type=str, default=None)
    args = p.parse_args()

    api_key = None
    model = args.model or "gpt-4o-mini"
    try:
        from adaptive_tax_app.config import get_adaptive_tax_settings

        settings = get_adaptive_tax_settings()
        api_key = settings.OPENAI_API_KEY
        if not args.model:
            model = settings.COMP_ADAPTIVE_TAX_OPENAI_MODEL
    except Exception:  # noqa: BLE001
        import os

        api_key = os.environ.get("OPENAI_API_KEY")

    if not args.corpus_jsonl.is_file():
        print(f"corpus not found: {args.corpus_jsonl}", file=sys.stderr)
        return 2

    summary = enrich_corpus(
        corpus_jsonl=args.corpus_jsonl,
        out_jsonl=args.out,
        dry_run=bool(args.dry_run) or not bool(args.apply),
        apply=bool(args.apply),
        limit=args.limit,
        required_only=not bool(args.all_needs_review),
        model=model,
        api_key=api_key,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
