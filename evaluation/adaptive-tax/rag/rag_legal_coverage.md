# Adaptive Tax — RAG legal coverage (Phase 9)

Generated: `2026-08-12T07:02:22.714979+00:00`

> Section-aware retrieval improved legal evidence Precision@3 from 13.33% to 52.0% (Recall@3 from 36.0% to 72.0%).

## Before / after tagging

| Metric | Before (pre-section-aware) | After (section-aware) |
|---|---:|---:|
| Total chunks | 1260 | 3421 |
| With `section_ref` | 231 | 3404 |
| Section-ref coverage % | 18.33 | 99.5 |
| Operative chunks | 0 | 1833 |
| TOC chunks | 0 | 11 |
| With `paragraph_ref` | 0 | 2005 |
| With `parent_provision_id` | 0 | 3404 |
| With applicable YA | 0 | 2904 |
| `metadata_source=deterministic` | 0 | 3421 |
| `metadata_source=gpt_assisted` | 0 | 0 |
| `needs_review` | 0 | 2 |

- Before corpus: `D:/R26-DS-004/R26-DS-004/data/processed/adaptive-tax/corpus_v1.pre_section_aware.jsonl`
- After corpus: `D:/R26-DS-004/R26-DS-004/data/processed/adaptive-tax/corpus_v1.jsonl`

## Per-section operative + YA counts (after)

| Section | Total | Operative | TOC | With YA | YA values | Tagging |
|---|---:|---:|---:|---:|---|---|
| 2 | 73 | 43 | 0 | 52 | 2024_25:20, 2025_26:52 | PASS |
| 5 | 33 | 14 | 0 | 26 | 2024_25:13, 2025_26:26 | PASS |
| 6 | 24 | 15 | 0 | 18 | 2024_25:7, 2025_26:18 | PASS |
| 7 | 33 | 19 | 0 | 21 | 2024_25:11, 2025_26:21 | PASS |
| 8 | 32 | 16 | 0 | 25 | 2024_25:8, 2025_26:25 | PASS |
| 11 | 24 | 12 | 0 | 19 | 2024_25:5, 2025_26:19 | PASS |
| 16 | 26 | 9 | 0 | 20 | 2024_25:7, 2025_26:20 | PASS |
| 52 | 13 | 8 | 0 | 8 | 2024_25:4, 2025_26:8 | PASS |
| 89 | 8 | 4 | 0 | 8 | 2024_25:4, 2025_26:8 | PASS |
| first_schedule | 19 | 8 | 0 | 14 | 2024_25:6, 2025_26:14 | PASS |

### Before tagging (same sections)

| Section | Total | Operative | Tagging |
|---|---:|---:|---|
| 2 | 2 | 0 | FAIL |
| 5 | 2 | 0 | FAIL |
| 6 | 0 | 0 | FAIL |
| 7 | 0 | 0 | FAIL |
| 8 | 1 | 0 | FAIL |
| 11 | 0 | 0 | FAIL |
| 16 | 2 | 0 | FAIL |
| 52 | 2 | 0 | FAIL |
| 89 | 0 | 0 | FAIL |
| first_schedule | 0 | 0 | FAIL |

## Gold Precision@3 / Recall@3

| Split | P@3 % | R@3 % | min_score | n | blocked leaks |
|---|---:|---:|---:|---:|---:|
| Before | 13.33 | 36.0 | 0.55 | 25 | 0 |
| After | 52.0 | 72.0 | 0.55 | 25 | 0 |

## Retrieval + citation-correctness (after gold)

- Queries: **20 PASS** / **5 FAIL** (80.0% pass)
- Criteria: P@3 ≥ 0.3333, R@3 ≥ 0.01, no Guide/Master leak

| Query | YA | P@3 | R@3 | Status |
|---|---|---:|---:|---|
| `q01_sec5_employment` | 2025_26 | 1.0 | 1.0 | **PASS** |
| `q02_sec5_benefits` | 2024_25 | 0.3333 | 0.5 | **PASS** |
| `q03_sec52_qp` | 2025_26 | 1.0 | 1.0 | **PASS** |
| `q04_sec52_reliefs_resident` | 2025_26 | 0.0 | 0.0 | **FAIL** |
| `q05_sec52_4_carry_forward` | 2025_26 | 0.0 | 0.0 | **FAIL** |
| `q06_sec52_cap_2025` | 2025_26 | 0.6667 | 1.0 | **PASS** |
| `q07_personal_relief` | 2025_26 | 0.3333 | 1.0 | **PASS** |
| `q08_first_schedule_rates` | 2024_25 | 1.0 | 1.0 | **PASS** |
| `q09_first_schedule_2022_bands` | 2025_26 | 0.0 | 0.0 | **FAIL** |
| `q10_sec89_apit_credit` | 2025_26 | 1.0 | 0.5 | **PASS** |
| `q11_sec89_2_credit_amount` | 2024_25 | 0.3333 | 1.0 | **PASS** |
| `q12_sec6_business` | 2025_26 | 1.0 | 0.5 | **PASS** |
| `q13_sec6_2_calculating` | 2025_26 | 0.3333 | 1.0 | **PASS** |
| `q14_sec7_investment` | 2025_26 | 1.0 | 1.0 | **PASS** |
| `q15_sec7_2` | 2024_25 | 0.3333 | 1.0 | **PASS** |
| `q16_sec8_other_income` | 2025_26 | 0.3333 | 0.5 | **PASS** |
| `q17_sec8_exclusions` | 2025_26 | 0.6667 | 1.0 | **PASS** |
| `q18_digit_aware_sec5_vs_52` | 2025_26 | 0.3333 | 1.0 | **PASS** |
| `q19_sec52_vs_5_negative` | 2024_25 | 0.3333 | 1.0 | **PASS** |
| `q20_ya_2024_base_act` | 2024_25 | 0.3333 | 1.0 | **PASS** |
| `q21_ya_2025_amendment` | 2025_26 | 0.6667 | 1.0 | **PASS** |
| `q22_toc_should_not_win` | 2025_26 | 0.0 | 0.0 | **FAIL** |
| `q23_sec3_taxable_income_qp` | 2025_26 | 1.0 | 1.0 | **PASS** |
| `q24_blocked_guide_never` | 2025_26 | 0.0 | 0.0 | **FAIL** |
| `q25_donation_sec52_link` | 2025_26 | 1.0 | 1.0 | **PASS** |

## Chosen `RAG_MIN_SCORE` (noise floor — not legal confidence)

- Configured / experimental default: **0.55**
- Chosen for this report: **0.55**
- Sweep recommendation (informational): `0.5`

| min_score | P@3 % | R@3 % |
|---:|---:|---:|
| 0.45 | 54.67 | 72.0 |
| 0.5 | 54.67 | 72.0 |
| 0.55 | 52.0 | 72.0 |
| 0.6 | 45.33 | 64.0 |

Configured/experimental default RAG_MIN_SCORE=0.55. This is a retrieval similarity noise floor only — never legal confidence. Production value should be selected from measured P@K/R@K at 0.45 / 0.50 / 0.55 / 0.60. Sweep suggests candidate floor=0.5 (P@3=54.67%, R@3=72.0%). Report still records configured=0.55 as current experimental default.

## Deterministic metadata (GPT assist optional)

- After deterministic count: **3421**
- After GPT-assisted count: **0** (must stay 0 unless manual enrich was accepted)
- After `needs_review`: **2**

## CURRENT vs FUTURE terminology (Phase 11)

| Term | Meaning in this report |
|---|---|
| **CURRENT** | RAG → legal evidence + explain. Rule Engine is the sole tax calculator. |
| **LegalRuleEvidence** | Structured legal evidence (non-executable). Not “RAG calculation”. |
| **Human approval path** | Stub: candidate → needs_review → approved/rejected. No calc wiring. |
| **FUTURE** | Validated rule candidates → explicit incorporation into engine (not this phase). |

Dissertation claim: the LLM/RAG does **not** automatically change the tax calculation. Future RAG-grounded rule candidates require validation before incorporation into the calculation engine.

## Notes

- GPT-assisted metadata count is 0 unless scripts/adaptive_tax_enrich_corpus_metadata.py was run manually.
- RAG_MIN_SCORE is a retrieval noise floor only — not legal confidence.
- Guide (ird-guide-ira) and Master (ird-calc-ontology-v5) remain blocked from Chroma explain evidence.
- Calc / Rule Engine path unchanged.
- Phase 11 LegalRuleEvidence is evidence-only (`executable=false`); no silent RAG→calc.
