#!/usr/bin/env python3
"""Phase 5.0 — section-scoped harvest from official IRD Act text.

Reads pre-extracted text under data/processed/adaptive-tax/text/ (or a PDF),
focuses on one section/schedule, runs GPT/fixture extract, and optionally
persists an amendment job + pending rule_source rows for admin review.

Never sends the whole Act to GPT.

Examples:

  # Dry-run focus window for Section 52 from processed text
  py -3 scripts/adaptive_tax_section_harvest.py --section 52 --dry-run

  # Extract (fixture or openai per COMP_ADAPTIVE_TAX_EXTRACTION_MODE) and print JSON
  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_section_harvest.py `
    --section 52 --source-doc-id ird-amend-2025-02

  # Persist pending rules into Postgres (requires DB)
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_section_harvest.py `
    --section 52 --persist
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
_COMP = _REPO / "backend" / "comp-adaptive-tax"
if str(_COMP) not in sys.path:
    sys.path.insert(0, str(_COMP))


def _load_targets(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_text(
    *,
    source_doc_id: str,
    pdf: Path | None,
    text_dir: Path,
) -> tuple[str, Path | None]:
    if pdf is not None:
        from adaptive_tax_app.services.pdf_extract import extract_pdf_text

        return extract_pdf_text(pdf), pdf

    # Prefer processed .txt named by source_doc_id or original PDF stem.
    candidates = [
        text_dir / f"{source_doc_id}.txt",
        text_dir / f"{source_doc_id}_E.txt",
    ]
    for cand in sorted(text_dir.glob("*.txt")):
        if source_doc_id.replace("-", "_") in cand.stem.replace("-", "_"):
            candidates.append(cand)
        # Common IRD filenames mapped in corpus_manifest
        if "24_2017" in source_doc_id or source_doc_id.endswith("2017-base"):
            if "24_2017" in cand.name or "24_2017" in cand.stem:
                candidates.append(cand)
        if "02-2025" in source_doc_id or source_doc_id.endswith("2025-02"):
            if "02-2025" in cand.name or "02_2025" in cand.name:
                candidates.append(cand)

    for cand in candidates:
        if cand.is_file():
            return cand.read_text(encoding="utf-8", errors="replace"), cand

    # Last resort: any txt in text_dir matching loosely
    for cand in sorted(text_dir.glob("*.txt")):
        return cand.read_text(encoding="utf-8", errors="replace"), cand

    raise FileNotFoundError(
        f"No processed text for source_doc_id={source_doc_id!r} under {text_dir}. "
        "Run scripts/adaptive_tax_build_corpus.py first, or pass --pdf."
    )


def _persist_pending_export(
    *,
    focused_text: str,
    rules: list,
    source_doc_id: str,
    section_key: str,
    source_path: Path | None,
    mode: str,
    model_name: str,
    prompt_version: str,
) -> Path:
    """Write a pending harvest JSON for admin review (no auto-approve)."""
    out_dir = _REPO / "data" / "processed" / "adaptive-tax" / "harvest_pending"
    out_dir.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4()
    path = out_dir / f"{job_id}.json"
    payload = {
        "id": str(job_id),
        "status": "pending_review",
        "harvest_mode": "section",
        "section_key": section_key,
        "source_doc_id": source_doc_id,
        "source_path": str(source_path) if source_path else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "extraction": {
            "mode": mode,
            "model_name": model_name,
            "prompt_version": prompt_version,
            "rules": [r.model_dump(mode="json") for r in rules],
        },
        "focused_text": focused_text,
        "note": (
            "Phase 5.0 harvest export — not auto-applied. "
            "Approve via admin amendment UI after formal PDF upload, "
            "or import into rule_source in a later milestone."
        ),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", required=True, help="Section key, e.g. 52 or first_schedule")
    parser.add_argument(
        "--source-doc-id",
        default="ird-ira-2017-base",
        help="Corpus source_doc_id (default: base Act)",
    )
    parser.add_argument("--pdf", type=Path, default=None, help="Optional PDF path")
    parser.add_argument(
        "--text-dir",
        type=Path,
        default=_REPO / "data" / "processed" / "adaptive-tax" / "text",
    )
    parser.add_argument(
        "--targets",
        type=Path,
        default=_REPO / "models" / "adaptive-tax" / "harvest" / "section_targets_v1.json",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print focus window only")
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Write pending harvest JSON under data/processed/adaptive-tax/harvest_pending/",
    )
    parser.add_argument("--max-chars", type=int, default=32_000)
    args = parser.parse_args(argv)

    patterns: list[str] | None = None
    if args.targets.is_file():
        doc = _load_targets(args.targets)
        for t in doc.get("targets") or []:
            if str(t.get("section_key")) == args.section:
                patterns = list(t.get("search_patterns") or [])
                break

    text, source_path = _resolve_text(
        source_doc_id=args.source_doc_id,
        pdf=args.pdf,
        text_dir=args.text_dir,
    )

    from adaptive_tax_app.services.pdf_extract import focus_section_text
    from adaptive_tax_app.services.gpt_extract import extract_rules

    focused = focus_section_text(
        text,
        args.section,
        max_chars=args.max_chars,
        search_patterns=patterns,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "section_key": args.section,
                    "source_doc_id": args.source_doc_id,
                    "source_path": str(source_path) if source_path else None,
                    "char_count_focused": focused.char_count_focused,
                    "truncated": focused.truncated,
                    "candidates": focused.amends_section_candidates,
                    "focused_text_preview": focused.focused_text[:2000],
                },
                indent=2,
            )
        )
        return 0

    result = extract_rules(
        focused.focused_text,
        amends_section_candidates=focused.amends_section_candidates,
        harvest_mode="section",
        section_key=args.section,
    )

    out = {
        "section_key": args.section,
        "source_doc_id": args.source_doc_id,
        "mode": result.mode,
        "model_name": result.model_name,
        "prompt_version": result.prompt_version,
        "warnings": result.warnings,
        "metrics": result.metrics,
        "rules": [r.model_dump(mode="json") for r in result.rules],
    }

    if args.persist:
        path = _persist_pending_export(
            focused_text=focused.focused_text,
            rules=result.rules,
            source_doc_id=args.source_doc_id,
            section_key=args.section,
            source_path=source_path,
            mode=result.mode,
            model_name=result.model_name,
            prompt_version=result.prompt_version,
        )
        out["pending_export_path"] = str(path)
        print(f"Wrote pending harvest export: {path}", file=sys.stderr)

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
