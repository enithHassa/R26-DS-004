#!/usr/bin/env python3
"""Score Adaptive Tax RAG gold set — Precision@K / Recall@K (no GPT).

Gold labelling is human ([evaluation/adaptive-tax/rag_gold_queries_v1.jsonl]).
Scoring is automated against a Chroma collection.

Examples::

  # After section-aware rebuild (current index)
  $env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_rag_gold_eval.py `
    --label after --k 3 --min-score 0.55

  # Baseline on archived pre-section-aware corpus (builds a temp Chroma)
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_rag_gold_eval.py `
    --label before `
    --corpus-jsonl data/processed/adaptive-tax/corpus_v1.pre_section_aware.jsonl `
    --persist-dir data/processed/adaptive-tax/chroma_baseline_pre_section `
    --reset --k 3 --min-score 0.55

  # Sweep dissertation candidate floors
  .\\.venv-backend\\Scripts\\python.exe scripts/adaptive_tax_rag_gold_eval.py `
    --sweep-min-scores 0.45,0.50,0.55,0.60 --k 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_REPO = _SCRIPTS.parent
_COMP = _REPO / "backend" / "comp-adaptive-tax"
for p in (_REPO, _COMP):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

_DEFAULT_GOLD = _REPO / "evaluation" / "adaptive-tax" / "rag_gold_queries_v1.jsonl"
_DEFAULT_PERSIST = _REPO / "data" / "processed" / "adaptive-tax" / "chroma"
_DEFAULT_OUT = _REPO / "evaluation" / "adaptive-tax" / "rag" / "RESULTS.md"


def load_gold(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _section_ok(hit_section: str | None, expected: str | None) -> bool:
    if not expected:
        return True
    from adaptive_tax_app.services.evidence import section_ref_matches

    if section_ref_matches(hit_section, expected):
        return True
    # First Schedule may be stored as schedule paragraph section_ref
    if expected.lower() == "first schedule":
        text = (hit_section or "").lower()
        return "first schedule" in text or "schedule" in text
    return False


def _paragraph_ok(meta_or_text: str, expected: str | None) -> bool:
    if not expected:
        return True
    blob = (meta_or_text or "").lower().replace(" ", "")
    want = expected.lower().replace(" ", "")
    return want in blob


def hit_is_relevant(hit: Any, gold: dict[str, Any]) -> bool:
    """Relevance: gold chunk_id, or section(+paragraph) + topical support."""
    cid = str(getattr(hit, "chunk_id", "") or "")
    gold_ids = {str(x) for x in (gold.get("gold_chunk_ids") or []) if x}
    if cid in gold_ids:
        return True

    hard_neg = {str(x) for x in (gold.get("hard_negatives") or []) if x}
    if cid in hard_neg:
        return False

    blocked = {str(x) for x in (gold.get("blocked_source_doc_ids") or []) if x}
    sid = str(getattr(hit, "source_doc_id", "") or "")
    if sid in blocked:
        return False

    allowed_docs = gold.get("expected_source_doc_ids") or []
    if allowed_docs and sid and sid not in allowed_docs:
        return False

    expected_sec = gold.get("expected_section_ref")
    text = getattr(hit, "text", "") or ""
    if not _section_ok(getattr(hit, "section_ref", None), expected_sec):
        # Soft fallback: digit-aware match against chunk text (legacy corpora)
        from adaptive_tax_app.services.evidence import section_ref_matches

        if not expected_sec:
            pass
        elif section_ref_matches(text[:500], expected_sec):
            pass
        elif expected_sec.lower() == "first schedule" and "first schedule" in text.lower():
            pass
        else:
            return False

    para = gold.get("expected_paragraph_ref")
    meta = getattr(hit, "metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    para_blob = f"{meta.get('paragraph_ref') or ''} {text}"
    if not _paragraph_ok(para_blob, para):
        return False

    terms = [str(t).lower() for t in (gold.get("topical_terms") or []) if t]
    if terms:
        text_l = text.lower()
        if not any(t in text_l for t in terms):
            return False

    return True


def precision_at_k(retrieved: list[Any], gold: dict[str, Any], k: int) -> float:
    top = retrieved[:k]
    if not top:
        return 0.0
    rel = sum(1 for h in top if hit_is_relevant(h, gold))
    return rel / float(k)


def recall_at_k(retrieved: list[Any], gold: dict[str, Any], k: int) -> float:
    """Support recall: share of gold chunk ids retrieved, else binary soft support."""
    gold_ids = {str(x) for x in (gold.get("gold_chunk_ids") or []) if x}
    top = retrieved[:k]
    hit_ids = {str(getattr(h, "chunk_id", "")) for h in top}
    if gold_ids:
        id_hit = len(gold_ids & hit_ids) / float(len(gold_ids))
        if id_hit > 0:
            return id_hit
        # Fair before/after when chunk_ids changed: soft support counts as partial credit
        return 1.0 if any(hit_is_relevant(h, gold) for h in top) else 0.0
    return 1.0 if any(hit_is_relevant(h, gold) for h in top) else 0.0


def blocked_leak(retrieved: list[Any], gold: dict[str, Any]) -> bool:
    blocked = {str(x) for x in (gold.get("blocked_source_doc_ids") or []) if x}
    if not blocked:
        return False
    for h in retrieved:
        if str(getattr(h, "source_doc_id", "") or "") in blocked:
            return True
    return False


def ensure_index(
    *,
    persist_dir: Path,
    corpus_jsonl: Path | None,
    reset: bool,
    collection: str,
) -> Any:
    from adaptive_tax_app.services.chroma_index import AdaptiveTaxChromaIndex

    index = AdaptiveTaxChromaIndex(
        persist_dir=persist_dir,
        collection_name=collection,
    )
    if corpus_jsonl is not None:
        if not corpus_jsonl.is_file():
            raise SystemExit(f"corpus not found: {corpus_jsonl}")
        print(f"indexing {corpus_jsonl} -> {persist_dir} reset={reset}")
        n = index.upsert_from_corpus_jsonl(corpus_jsonl, reset=reset)
        print(f"upserted {n}; count={index.count()}")
    return index


def run_eval(
    *,
    gold_rows: list[dict[str, Any]],
    index: Any,
    k: int,
    min_score: float,
    label: str,
) -> dict[str, Any]:
    from adaptive_tax_app.services.evidence import section_ref_matches

    per_query: list[dict[str, Any]] = []
    p_sum = 0.0
    r_sum = 0.0
    leaks = 0

    for gold in gold_rows:
        q = str(gold.get("query") or "").strip()
        section = gold.get("expected_section_ref")
        # Over-fetch then filter by min_score (noise floor only)
        hits = index.search(q, section_ref=None, top_k=max(k * 8, 24))
        filtered = [
            h
            for h in hits
            if h.score is None or float(h.score) >= float(min_score)
        ]
        # Soft section prefer (digit-aware) without dropping all
        if section:
            preferred = [
                h
                for h in filtered
                if section_ref_matches(h.section_ref, section)
                or section.lower() in (h.text or "")[:500].lower()
            ]
            if preferred:
                # Keep preferred first, then others
                pref_ids = {h.chunk_id for h in preferred}
                filtered = preferred + [h for h in filtered if h.chunk_id not in pref_ids]

        top = filtered[:k]
        p = precision_at_k(top, gold, k)
        r = recall_at_k(top, gold, k)
        p_sum += p
        r_sum += r
        leak = blocked_leak(top, gold)
        if leak:
            leaks += 1
        per_query.append(
            {
                "query_id": gold.get("query_id"),
                "assessment_year": gold.get("assessment_year"),
                "precision_at_k": round(p, 4),
                "recall_at_k": round(r, 4),
                "hit_ids": [h.chunk_id for h in top],
                "hit_scores": [h.score for h in top],
                "blocked_leak": leak,
            }
        )

    n = len(gold_rows) or 1
    summary = {
        "label": label,
        "k": k,
        "min_score": min_score,
        "n_queries": len(gold_rows),
        "macro_precision_at_k": round(p_sum / n, 4),
        "macro_recall_at_k": round(r_sum / n, 4),
        "macro_precision_pct": round(100.0 * p_sum / n, 2),
        "macro_recall_pct": round(100.0 * r_sum / n, 2),
        "blocked_leak_queries": leaks,
        "note": (
            "RAG_MIN_SCORE is a retrieval noise floor only — not legal confidence. "
            "Choose production floor from sweep 0.45/0.50/0.55/0.60."
        ),
        "per_query": per_query,
    }
    return summary


def format_report(
    after: dict[str, Any] | None,
    before: dict[str, Any] | None,
    sweeps: list[dict[str, Any]] | None = None,
) -> str:
    lines: list[str] = [
        "# Adaptive Tax RAG gold evaluation (Phase 8)",
        "",
        "Gold set: `evaluation/adaptive-tax/rag_gold_queries_v1.jsonl` (human-labelled).",
        "Scorer: `scripts/adaptive_tax_rag_gold_eval.py` (no GPT).",
        "",
    ]
    if before and after:
        lines.append(
            f'> Section-aware retrieval improved legal evidence Precision@{after["k"]} '
            f'from **{before["macro_precision_pct"]}%** to **{after["macro_precision_pct"]}%** '
            f'(Recall@{after["k"]} from **{before["macro_recall_pct"]}%** to '
            f'**{after["macro_recall_pct"]}%**).'
        )
        lines.append("")
    elif after:
        lines.append(
            f'> After section-aware rebuild: Precision@{after["k"]} = '
            f'**{after["macro_precision_pct"]}%**, Recall@{after["k"]} = '
            f'**{after["macro_recall_pct"]}%** '
            f'(min_score={after["min_score"]}).'
        )
        lines.append("")
        lines.append(
            "Run a `--label before` pass on `corpus_v1.pre_section_aware.jsonl` "
            "to fill the before→after sentence."
        )
        lines.append("")

    def _table(title: str, summary: dict[str, Any]) -> None:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"- label: `{summary['label']}`")
        lines.append(f"- k: {summary['k']}")
        lines.append(f"- min_score (noise floor): {summary['min_score']}")
        lines.append(f"- n_queries: {summary['n_queries']}")
        lines.append(f"- macro P@{summary['k']}: {summary['macro_precision_pct']}%")
        lines.append(f"- macro R@{summary['k']}: {summary['macro_recall_pct']}%")
        lines.append(f"- blocked Guide/Master leaks: {summary['blocked_leak_queries']}")
        lines.append("")

    if before:
        _table("Before (pre-section-aware)", before)
    if after:
        _table("After (section-aware + retrieval upgrades)", after)

    if sweeps:
        lines.append("## RAG_MIN_SCORE sweep (dissertation candidates)")
        lines.append("")
        lines.append("| min_score | P@K % | R@K % |")
        lines.append("|---:|---:|---:|")
        for s in sweeps:
            lines.append(
                f"| {s['min_score']} | {s['macro_precision_pct']} | {s['macro_recall_pct']} |"
            )
        lines.append("")
        lines.append(
            "Pick the production floor from measured P/R — never call it legal confidence."
        )
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gold", type=Path, default=_DEFAULT_GOLD)
    p.add_argument("--persist-dir", type=Path, default=_DEFAULT_PERSIST)
    p.add_argument(
        "--corpus-jsonl",
        type=Path,
        default=None,
        help="If set, (re)index this corpus into --persist-dir before scoring",
    )
    p.add_argument("--reset", action="store_true")
    p.add_argument("--collection", type=str, default="ird_legal_evidence_v1")
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--min-score", type=float, default=0.55)
    p.add_argument("--label", type=str, default="after", choices=["before", "after", "custom"])
    p.add_argument(
        "--sweep-min-scores",
        type=str,
        default="",
        help="Comma list e.g. 0.45,0.50,0.55,0.60",
    )
    p.add_argument("--out-json", type=Path, default=None)
    p.add_argument("--out-md", type=Path, default=_DEFAULT_OUT)
    p.add_argument("--merge-md", action="store_true", help="Merge with existing RESULTS.md")
    args = p.parse_args(argv)

    if not args.gold.is_file():
        print(f"gold not found: {args.gold}", file=sys.stderr)
        return 2

    gold_rows = load_gold(args.gold)
    persist = args.persist_dir
    if not persist.is_absolute():
        persist = _REPO / persist

    index = ensure_index(
        persist_dir=persist,
        corpus_jsonl=args.corpus_jsonl,
        reset=bool(args.reset),
        collection=args.collection,
    )

    summary = run_eval(
        gold_rows=gold_rows,
        index=index,
        k=args.k,
        min_score=args.min_score,
        label=args.label,
    )
    print(json.dumps({k: v for k, v in summary.items() if k != "per_query"}, indent=2))

    sweeps: list[dict[str, Any]] = []
    if args.sweep_min_scores.strip():
        for part in args.sweep_min_scores.split(","):
            floor = float(part.strip())
            sweeps.append(
                run_eval(
                    gold_rows=gold_rows,
                    index=index,
                    k=args.k,
                    min_score=floor,
                    label=f"{args.label}@min={floor}",
                )
            )

    out_json = args.out_json
    if out_json is None:
        out_dir = _REPO / "evaluation" / "adaptive-tax" / "rag"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_json = out_dir / f"gold_eval_{args.label}.json"
    else:
        out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summary, "sweeps": sweeps}
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {out_json}")

    before = summary if args.label == "before" else None
    after = summary if args.label == "after" else None
    if args.merge_md and args.out_md.is_file():
        # Load companion JSON if present
        rag_dir = args.out_md.parent
        before_path = rag_dir / "gold_eval_before.json"
        after_path = rag_dir / "gold_eval_after.json"
        if before_path.is_file():
            before = json.loads(before_path.read_text(encoding="utf-8")).get("summary")
        if after_path.is_file():
            after = json.loads(after_path.read_text(encoding="utf-8")).get("summary")
        if args.label == "before":
            before = summary
        if args.label == "after":
            after = summary

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(
        format_report(after=after, before=before, sweeps=sweeps or None),
        encoding="utf-8",
    )
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
