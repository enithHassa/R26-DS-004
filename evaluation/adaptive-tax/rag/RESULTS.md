# Adaptive Tax RAG gold evaluation (Phase 8)

Gold set: `evaluation/adaptive-tax/rag_gold_queries_v1.jsonl` (human-labelled).
Scorer: `scripts/adaptive_tax_rag_gold_eval.py` (no GPT).

> Section-aware retrieval improved legal evidence Precision@3 from **13.33%** to **52.0%** (Recall@3 from **36.0%** to **72.0%**).

## Before (pre-section-aware)

- label: `before`
- k: 3
- min_score (noise floor): 0.55
- n_queries: 25
- macro P@3: 13.33%
- macro R@3: 36.0%
- blocked Guide/Master leaks: 0

## After (section-aware + retrieval upgrades)

- label: `after`
- k: 3
- min_score (noise floor): 0.55
- n_queries: 25
- macro P@3: 52.0%
- macro R@3: 72.0%
- blocked Guide/Master leaks: 0

## RAG_MIN_SCORE sweep (dissertation candidates)

| min_score | P@K % | R@K % |
|---:|---:|---:|
| 0.45 | 54.67 | 72.0 |
| 0.5 | 54.67 | 72.0 |
| 0.55 | 52.0 | 72.0 |
| 0.6 | 45.33 | 64.0 |

Pick the production floor from measured P/R — never call it legal confidence.

## CURRENT vs FUTURE (Phase 11)

- **CURRENT:** RAG → legal evidence + explain; Rule Engine calculates.
- **LegalRuleEvidence:** structured legal evidence only (`executable=false`); optional candidates on explain bundle.
- **FUTURE:** human-approved candidates may incorporate into the engine — **not wired** in this phase.

