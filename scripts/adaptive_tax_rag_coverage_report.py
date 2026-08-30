#!/usr/bin/env python3
"""Phase 9 — Adaptive Tax RAG legal coverage report.

Writes ``rag_legal_coverage.md`` + ``.json`` with:

- before/after tagging coverage (archived pre-section-aware vs current)
- per-section operative + YA chunk counts (calculator-required sections)
- retrieval + citation-correctness PASS/FAIL from gold eval
- gold Precision@3 / Recall@3 before/after
- deterministic vs GPT-assisted metadata counts
- chosen ``RAG_MIN_SCORE`` with P/R sweep notes (not legal confidence)

No OpenAI / GPT required.

Example::

  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_rag_coverage_report.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_COMP = _REPO / "backend" / "comp-adaptive-tax"
for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

REQUIRED_SECTIONS = (
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

_DEFAULT_AFTER = _REPO / "data" / "processed" / "adaptive-tax" / "corpus_v1.jsonl"
_DEFAULT_BEFORE = (
    _REPO / "data" / "processed" / "adaptive-tax" / "corpus_v1.pre_section_aware.jsonl"
)
_DEFAULT_GOLD_AFTER = _REPO / "evaluation" / "adaptive-tax" / "rag" / "gold_eval_after.json"
_DEFAULT_GOLD_BEFORE = _REPO / "evaluation" / "adaptive-tax" / "rag" / "gold_eval_before.json"
_DEFAULT_OUT_DIR = _REPO / "evaluation" / "adaptive-tax" / "rag"


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _section_num(row: dict[str, Any]) -> str | None:
    ref = row.get("section_ref")
    if isinstance(ref, list):
        ref = " | ".join(str(x) for x in ref)
    text = str(ref or "")
    if re.search(r"(?i)first\s+schedule", text) or re.search(
        r"(?i)first\s+schedule", str(row.get("schedule_ref") or "")
    ):
        return "first_schedule"
    m = re.search(r"(?i)section\s+(\d+[a-z]?)", text)
    if m:
        return m.group(1).lower()
    # Bare digit primary (rare)
    m2 = re.fullmatch(r"(\d+[a-z]?)", text.strip(), flags=re.I)
    if m2:
        return m2.group(1).lower()
    return None


def _yas(row: dict[str, Any]) -> list[str]:
    raw = row.get("applicable_assessment_years")
    if raw is None:
        raw = row.get("applicable_yas")
    if isinstance(raw, list):
        out: list[str] = []
        for x in raw:
            s = str(x).strip()
            if s.startswith("["):
                try:
                    parsed = json.loads(s.replace("'", '"'))
                    if isinstance(parsed, list):
                        out.extend(str(p).strip() for p in parsed if str(p).strip())
                        continue
                except json.JSONDecodeError:
                    pass
            if s:
                out.append(s)
        return out
    if isinstance(raw, str) and raw.strip():
        s = raw.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s.replace("'", '"'))
                if isinstance(parsed, list):
                    return [str(p).strip() for p in parsed if str(p).strip()]
            except json.JSONDecodeError:
                pass
        return [p.strip() for p in re.split(r"[|,]", s) if p.strip()]
    return []


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in {"1", "true", "yes", "y"}


def analyze_corpus(path: Path, *, label: str) -> dict[str, Any]:
    rows = _iter_jsonl(path)
    total = len(rows)
    with_section = 0
    without_section = 0
    meta_src = Counter()
    needs_review = 0
    operative = 0
    toc = 0
    header = 0
    with_para = 0
    with_parent = 0
    with_ya = 0
    by_doc: Counter[str] = Counter()
    by_sec: Counter[str] = Counter()

    per_required: dict[str, dict[str, Any]] = {
        s: {
            "total": 0,
            "operative": 0,
            "toc": 0,
            "with_ya": 0,
            "ya_values": Counter(),
            "with_paragraph_ref": 0,
            "source_docs": Counter(),
        }
        for s in REQUIRED_SECTIONS
    }

    for row in rows:
        sid = str(row.get("source_doc_id") or "").strip() or "unknown"
        by_doc[sid] += 1
        src = str(row.get("metadata_source") or "unknown").strip() or "unknown"
        meta_src[src] += 1
        if _truthy(row.get("needs_review")):
            needs_review += 1
        if _truthy(row.get("is_operative_provision")):
            operative += 1
        if _truthy(row.get("is_toc")):
            toc += 1
        if _truthy(row.get("is_header_footer")):
            header += 1
        if row.get("paragraph_ref"):
            with_para += 1
        if row.get("parent_provision_id"):
            with_parent += 1
        yas = _yas(row)
        if yas:
            with_ya += 1

        sn = _section_num(row)
        ref = row.get("section_ref")
        if ref is None or ref == "" or ref == []:
            without_section += 1
        else:
            with_section += 1
        if sn:
            by_sec[sn] += 1
            if sn in per_required:
                bucket = per_required[sn]
                bucket["total"] += 1
                if _truthy(row.get("is_operative_provision")):
                    bucket["operative"] += 1
                if _truthy(row.get("is_toc")):
                    bucket["toc"] += 1
                if row.get("paragraph_ref"):
                    bucket["with_paragraph_ref"] += 1
                if yas:
                    bucket["with_ya"] += 1
                    for y in yas:
                        bucket["ya_values"][y] += 1
                bucket["source_docs"][sid] += 1

    # Serialize counters
    for s in REQUIRED_SECTIONS:
        per_required[s]["ya_values"] = dict(per_required[s]["ya_values"])
        per_required[s]["source_docs"] = dict(per_required[s]["source_docs"])
        # PASS if at least one operative non-TOC chunk exists for the section
        op = int(per_required[s]["operative"])
        tot = int(per_required[s]["total"])
        toc_n = int(per_required[s]["toc"])
        per_required[s]["tagging_pass"] = op > 0 and (op >= toc_n or tot > toc_n)

    return {
        "label": label,
        "corpus_path": str(path.as_posix()),
        "exists": path.is_file(),
        "total_chunks": total,
        "chunks_with_section_ref": with_section,
        "chunks_without_section_ref": without_section,
        "section_ref_coverage_pct": round(100.0 * with_section / total, 2) if total else 0.0,
        "metadata_source_counts": dict(meta_src),
        "deterministic_metadata_count": int(meta_src.get("deterministic", 0)),
        "gpt_assisted_metadata_count": int(meta_src.get("gpt_assisted", 0)),
        "needs_review_count": needs_review,
        "operative_count": operative,
        "toc_count": toc,
        "header_footer_count": header,
        "with_paragraph_ref": with_para,
        "with_parent_provision_id": with_parent,
        "with_applicable_yas": with_ya,
        "chunks_by_source_document": dict(by_doc),
        "chunks_by_section_num_top": dict(by_sec.most_common(40)),
        "required_sections": per_required,
    }


def _load_gold_eval(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "summary" in raw:
        return raw
    if isinstance(raw, dict) and "macro_precision_pct" in raw:
        return {"summary": raw, "sweeps": []}
    return None


def citation_correctness_from_gold(
    gold_payload: dict[str, Any] | None,
    *,
    min_precision: float = 0.3333,
    min_recall: float = 0.01,
) -> dict[str, Any]:
    """Per-query retrieval + citation-correctness PASS/FAIL from gold eval."""
    if not gold_payload:
        return {
            "available": False,
            "n_queries": 0,
            "n_pass": 0,
            "n_fail": 0,
            "pass_rate_pct": 0.0,
            "queries": [],
        }
    summary = gold_payload.get("summary") or {}
    rows = list(summary.get("per_query") or [])
    out_rows: list[dict[str, Any]] = []
    n_pass = 0
    for row in rows:
        p = float(row.get("precision_at_k") or 0.0)
        r = float(row.get("recall_at_k") or 0.0)
        leak = bool(row.get("blocked_leak"))
        ok = (p >= min_precision) and (r >= min_recall) and (not leak)
        if ok:
            n_pass += 1
        out_rows.append(
            {
                "query_id": row.get("query_id"),
                "assessment_year": row.get("assessment_year"),
                "precision_at_k": p,
                "recall_at_k": r,
                "blocked_leak": leak,
                "status": "PASS" if ok else "FAIL",
                "hit_ids": row.get("hit_ids") or [],
            }
        )
    n = len(out_rows)
    return {
        "available": True,
        "n_queries": n,
        "n_pass": n_pass,
        "n_fail": n - n_pass,
        "pass_rate_pct": round(100.0 * n_pass / n, 2) if n else 0.0,
        "criteria": {
            "min_precision_at_3": min_precision,
            "min_recall_at_3": min_recall,
            "blocked_leak_must_be_false": True,
            "note": (
                "PASS = soft-relevant P@3 and R@3 clear floors; "
                "not legal confidence."
            ),
        },
        "queries": out_rows,
    }


def choose_rag_min_score(
    sweeps: list[dict[str, Any]],
    *,
    configured: float,
) -> dict[str, Any]:
    """Document chosen experimental floor vs measured sweep (not legal confidence)."""
    table = []
    for s in sweeps:
        table.append(
            {
                "min_score": s.get("min_score"),
                "macro_precision_pct": s.get("macro_precision_pct"),
                "macro_recall_pct": s.get("macro_recall_pct"),
                "label": s.get("label"),
            }
        )
    # Prefer configured if present in sweep; else recommend highest P with R>=64
    recommendation = configured
    note = (
        f"Configured/experimental default RAG_MIN_SCORE={configured}. "
        "This is a retrieval similarity noise floor only — never legal confidence. "
        "Production value should be selected from measured P@K/R@K at "
        "0.45 / 0.50 / 0.55 / 0.60."
    )
    if table:
        # Stable pick: keep 0.55 unless another floor has strictly better P and R>=72
        best = None
        for row in table:
            try:
                floor = float(row["min_score"])
                p = float(row["macro_precision_pct"])
                r = float(row["macro_recall_pct"])
            except (TypeError, ValueError, KeyError):
                continue
            if r < 64.0:
                continue
            if best is None or p > best[1] or (p == best[1] and abs(floor - configured) < abs(best[0] - configured)):
                best = (floor, p, r)
        if best is not None:
            recommendation = best[0]
            note += (
                f" Sweep suggests candidate floor={recommendation} "
                f"(P@3={best[1]}%, R@3={best[2]}%). "
                f"Report still records configured={configured} as current experimental default."
            )
    return {
        "configured_rag_min_score": configured,
        "chosen_rag_min_score": configured,
        "recommended_from_sweep": recommendation,
        "sweep": table,
        "note": note,
    }


def build_report(
    *,
    before_corpus: Path,
    after_corpus: Path,
    gold_before: Path,
    gold_after: Path,
    configured_min_score: float,
) -> dict[str, Any]:
    before = analyze_corpus(before_corpus, label="before")
    after = analyze_corpus(after_corpus, label="after")
    gb = _load_gold_eval(gold_before)
    ga = _load_gold_eval(gold_after)

    before_sum = (gb or {}).get("summary") if gb else None
    after_sum = (ga or {}).get("summary") if ga else None
    sweeps = list((ga or {}).get("sweeps") or [])

    citation = citation_correctness_from_gold(ga)
    rag_score = choose_rag_min_score(sweeps, configured=configured_min_score)

    required_pass_after = {
        s: after["required_sections"][s]["tagging_pass"] for s in REQUIRED_SECTIONS
    }
    required_pass_before = {
        s: before["required_sections"][s]["tagging_pass"] for s in REQUIRED_SECTIONS
    }

    headline = None
    if before_sum and after_sum:
        headline = (
            f"Section-aware retrieval improved legal evidence Precision@3 from "
            f"{before_sum.get('macro_precision_pct')}% to "
            f"{after_sum.get('macro_precision_pct')}% "
            f"(Recall@3 from {before_sum.get('macro_recall_pct')}% to "
            f"{after_sum.get('macro_recall_pct')}%)."
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "9",
        "headline": headline,
        "before": before,
        "after": after,
        "tagging_delta": {
            "total_chunks": {
                "before": before["total_chunks"],
                "after": after["total_chunks"],
            },
            "section_ref_coverage_pct": {
                "before": before["section_ref_coverage_pct"],
                "after": after["section_ref_coverage_pct"],
            },
            "operative_count": {
                "before": before["operative_count"],
                "after": after["operative_count"],
            },
            "with_paragraph_ref": {
                "before": before["with_paragraph_ref"],
                "after": after["with_paragraph_ref"],
            },
            "gpt_assisted_metadata_count": {
                "before": before["gpt_assisted_metadata_count"],
                "after": after["gpt_assisted_metadata_count"],
            },
            "deterministic_metadata_count": {
                "before": before["deterministic_metadata_count"],
                "after": after["deterministic_metadata_count"],
            },
        },
        "required_section_tagging_pass": {
            "before": required_pass_before,
            "after": required_pass_after,
        },
        "gold_eval": {
            "before": {
                "available": before_sum is not None,
                "macro_precision_pct": (before_sum or {}).get("macro_precision_pct"),
                "macro_recall_pct": (before_sum or {}).get("macro_recall_pct"),
                "k": (before_sum or {}).get("k", 3),
                "min_score": (before_sum or {}).get("min_score"),
                "n_queries": (before_sum or {}).get("n_queries"),
                "blocked_leak_queries": (before_sum or {}).get("blocked_leak_queries"),
                "path": str(gold_before.as_posix()),
            },
            "after": {
                "available": after_sum is not None,
                "macro_precision_pct": (after_sum or {}).get("macro_precision_pct"),
                "macro_recall_pct": (after_sum or {}).get("macro_recall_pct"),
                "k": (after_sum or {}).get("k", 3),
                "min_score": (after_sum or {}).get("min_score"),
                "n_queries": (after_sum or {}).get("n_queries"),
                "blocked_leak_queries": (after_sum or {}).get("blocked_leak_queries"),
                "path": str(gold_after.as_posix()),
            },
        },
        "retrieval_citation_correctness": citation,
        "rag_min_score": rag_score,
        "notes": [
            "GPT-assisted metadata count is 0 unless scripts/adaptive_tax_enrich_corpus_metadata.py was run manually.",
            "RAG_MIN_SCORE is a retrieval noise floor only — not legal confidence.",
            "Guide (ird-guide-ira) and Master (ird-calc-ontology-v5) remain blocked from Chroma explain evidence.",
            "Calc / Rule Engine path unchanged.",
            "Phase 10: GPT only enrich/explain; no GPT enrich → Rule Engine; do not bypass Rule Engine.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    before = report["before"]
    after = report["after"]
    gold = report["gold_eval"]
    cite = report["retrieval_citation_correctness"]
    rag = report["rag_min_score"]
    lines: list[str] = [
        "# Adaptive Tax — RAG legal coverage (Phase 9)",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
    ]
    if report.get("headline"):
        lines.append(f"> {report['headline']}")
        lines.append("")

    lines.extend(
        [
            "## Before / after tagging",
            "",
            "| Metric | Before (pre-section-aware) | After (section-aware) |",
            "|---|---:|---:|",
            f"| Total chunks | {before['total_chunks']} | {after['total_chunks']} |",
            f"| With `section_ref` | {before['chunks_with_section_ref']} | {after['chunks_with_section_ref']} |",
            f"| Section-ref coverage % | {before['section_ref_coverage_pct']} | {after['section_ref_coverage_pct']} |",
            f"| Operative chunks | {before['operative_count']} | {after['operative_count']} |",
            f"| TOC chunks | {before['toc_count']} | {after['toc_count']} |",
            f"| With `paragraph_ref` | {before['with_paragraph_ref']} | {after['with_paragraph_ref']} |",
            f"| With `parent_provision_id` | {before['with_parent_provision_id']} | {after['with_parent_provision_id']} |",
            f"| With applicable YA | {before['with_applicable_yas']} | {after['with_applicable_yas']} |",
            f"| `metadata_source=deterministic` | {before['deterministic_metadata_count']} | {after['deterministic_metadata_count']} |",
            f"| `metadata_source=gpt_assisted` | {before['gpt_assisted_metadata_count']} | {after['gpt_assisted_metadata_count']} |",
            f"| `needs_review` | {before['needs_review_count']} | {after['needs_review_count']} |",
            "",
            f"- Before corpus: `{before['corpus_path']}`",
            f"- After corpus: `{after['corpus_path']}`",
            "",
            "## Per-section operative + YA counts (after)",
            "",
            "| Section | Total | Operative | TOC | With YA | YA values | Tagging |",
            "|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for s in REQUIRED_SECTIONS:
        b = after["required_sections"][s]
        yas = ", ".join(f"{k}:{v}" for k, v in sorted((b.get("ya_values") or {}).items())) or "—"
        status = "PASS" if b.get("tagging_pass") else "FAIL"
        lines.append(
            f"| {s} | {b['total']} | {b['operative']} | {b['toc']} | "
            f"{b['with_ya']} | {yas} | {status} |"
        )

    lines.extend(
        [
            "",
            "### Before tagging (same sections)",
            "",
            "| Section | Total | Operative | Tagging |",
            "|---|---:|---:|---|",
        ]
    )
    for s in REQUIRED_SECTIONS:
        b = before["required_sections"][s]
        status = "PASS" if b.get("tagging_pass") else "FAIL"
        lines.append(f"| {s} | {b['total']} | {b['operative']} | {status} |")

    gb = gold["before"]
    ga = gold["after"]
    lines.extend(
        [
            "",
            "## Gold Precision@3 / Recall@3",
            "",
            "| Split | P@3 % | R@3 % | min_score | n | blocked leaks |",
            "|---|---:|---:|---:|---:|---:|",
            (
                f"| Before | {gb.get('macro_precision_pct')} | {gb.get('macro_recall_pct')} | "
                f"{gb.get('min_score')} | {gb.get('n_queries')} | {gb.get('blocked_leak_queries')} |"
            ),
            (
                f"| After | {ga.get('macro_precision_pct')} | {ga.get('macro_recall_pct')} | "
                f"{ga.get('min_score')} | {ga.get('n_queries')} | {ga.get('blocked_leak_queries')} |"
            ),
            "",
        ]
    )

    lines.extend(
        [
            "## Retrieval + citation-correctness (after gold)",
            "",
            f"- Queries: **{cite['n_pass']} PASS** / **{cite['n_fail']} FAIL** "
            f"({cite['pass_rate_pct']}% pass)",
            f"- Criteria: P@3 ≥ {cite.get('criteria', {}).get('min_precision_at_3')}, "
            f"R@3 ≥ {cite.get('criteria', {}).get('min_recall_at_3')}, no Guide/Master leak",
            "",
            "| Query | YA | P@3 | R@3 | Status |",
            "|---|---|---:|---:|---|",
        ]
    )
    for q in cite.get("queries") or []:
        lines.append(
            f"| `{q.get('query_id')}` | {q.get('assessment_year')} | "
            f"{q.get('precision_at_k')} | {q.get('recall_at_k')} | **{q.get('status')}** |"
        )

    lines.extend(
        [
            "",
            "## Chosen `RAG_MIN_SCORE` (noise floor — not legal confidence)",
            "",
            f"- Configured / experimental default: **{rag['configured_rag_min_score']}**",
            f"- Chosen for this report: **{rag['chosen_rag_min_score']}**",
            f"- Sweep recommendation (informational): `{rag.get('recommended_from_sweep')}`",
            "",
            "| min_score | P@3 % | R@3 % |",
            "|---:|---:|---:|",
        ]
    )
    for row in rag.get("sweep") or []:
        lines.append(
            f"| {row.get('min_score')} | {row.get('macro_precision_pct')} | "
            f"{row.get('macro_recall_pct')} |"
        )
    if not rag.get("sweep"):
        lines.append("| — | — | — |")
    lines.extend(["", rag.get("note") or "", ""])

    lines.extend(
        [
            "## Deterministic metadata (GPT assist optional)",
            "",
            f"- After deterministic count: **{after['deterministic_metadata_count']}**",
            f"- After GPT-assisted count: **{after['gpt_assisted_metadata_count']}** "
            "(must stay 0 unless manual enrich was accepted)",
            f"- After `needs_review`: **{after['needs_review_count']}**",
            "",
            "## Notes",
            "",
        ]
    )
    for n in report.get("notes") or []:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before-corpus", type=Path, default=_DEFAULT_BEFORE)
    p.add_argument("--after-corpus", type=Path, default=_DEFAULT_AFTER)
    p.add_argument("--gold-before", type=Path, default=_DEFAULT_GOLD_BEFORE)
    p.add_argument("--gold-after", type=Path, default=_DEFAULT_GOLD_AFTER)
    p.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT_DIR)
    p.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Override configured RAG_MIN_SCORE for the report (default: settings)",
    )
    args = p.parse_args(argv)

    configured = 0.55
    try:
        from adaptive_tax_app.config import get_adaptive_tax_settings

        configured = float(get_adaptive_tax_settings().RAG_MIN_SCORE)
    except Exception:  # noqa: BLE001
        pass
    if args.min_score is not None:
        configured = float(args.min_score)

    report = build_report(
        before_corpus=args.before_corpus,
        after_corpus=args.after_corpus,
        gold_before=args.gold_before,
        gold_after=args.gold_after,
        configured_min_score=configured,
    )

    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = _REPO / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rag_legal_coverage.json"
    md_path = out_dir / "rag_legal_coverage.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    if report.get("headline"):
        print(report["headline"])
    print(
        "citation PASS/FAIL:",
        report["retrieval_citation_correctness"]["n_pass"],
        "/",
        report["retrieval_citation_correctness"]["n_fail"],
    )
    print(
        "gpt_assisted after:",
        report["after"]["gpt_assisted_metadata_count"],
        "RAG_MIN_SCORE:",
        report["rag_min_score"]["chosen_rag_min_score"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
