# Adaptive Tax evaluation metrics (dissertation Chapter 4)

Filled from Phase **5.9** offline scoring run `phase6_9_2026_08_11_101701` (2026-08-11T10:17:01.192659+00:00). OpenAI explain mode is validated by the same citation/grounding scripts when live responses are saved to JSON.

| Metric | Method | Result | Notes |
|--------|--------|--------|-------|
| **Coverage** | `coverage/score_coverage.py` vs checklist | **9/9 = 100.0%** | Core areas: employment_income, first_schedule_rates, personal_relief, sec52_qualifying_payments, donations, business_income, investment_income, other_income, tax_credits |
| **Calculation accuracy** | Named goldens `test_rule_engine_examples.py` | **pass** (25 example files; 31 passed in 0.57s) | ex01–ex08 + covered-area goldens (ex09–ex17) |
| **Provenance completeness** | `provenance/score_provenance.py` (strict) | **1.0** (ok; 29 cases) | Every executable step → Act section + source_quote + source_doc_id |
| **Citation faithfulness** | `sections_cited ⊆ retrieved`; `citation_faithfulness/score_citations.py` | **1/1 = 1.0** | `explain_ex04_sample.json` |
| **Explanation grounding** | sentence → chunk / rule_source; `explanation_grounding/score_grounding.py` | **3/3 = 1.0** | Positive fixtures + production sample; negative control separate |
| **Amendment adaptivity** | dual-YA Sec 52; `amendment_adaptivity/score_adaptivity.py` | **pass** (ex08 delta tax = 42000) | T1 ≠ T2 with distinct Sec 52 quotes |
| Extraction precision (Sec 52 labeled) | `extraction/score_extraction.py` | **20/20 = 1.0** | Act 02/2025 20-field sample |
| Extraction precision (harvested sections) | `extraction/score_harvest_sections.py` | **100/100 = 1.0** (8 sections) | Per `*_harvest_v1.json` Act-backed field checks |


## Phase 6.9 (filing catalog + viva)

| Metric | Method | Result | Notes |
|--------|--------|--------|-------|
| **Legal coverage (section grain)** | `GET /knowledge/legal-coverage` / `legal_coverage.py` | **areas 9/9 = 100.0%**; Sec 5 18/18 | Viva dashboard `/adaptive-tax/coverage` |
| **Catalog confidence distribution** | `phase6/score_catalog_confidence.py` | **high=49, medium=5, low=0, pending=0** | Supported active catalog components |
| **Unsupported rule queue** | `GET /filing-catalog/unsupported` | **2 pending** | Act 11/2026: supported `qp_brought_forward`; unsupported e.g. `qp_bank_merger` |
| **Version strip (Calculated Using)** | `knowledge_versions_from_catalog()` | **pass** | Screenshot checklist in `phase6/viva_figure_checklist.md` |
| **Guide/Master not executable** | `phase6/score_executable_cites.py` | **pass** (29 goldens scanned) | No `ird-guide-ira` / Master KB in bootstrap or approved catalog |
| **Phase 6 filing-line regression** | pytest filing-line suite | **pass** (56 passed in 141.04s (0:02:21)) | Phase 5 goldens + phase6/68 + emp/inv/QP/biz/other |

Reproduce: see [README.md](../README.md) and [phase5/README.md](README.md). Viva demo: `scripts/adaptive_tax_phase5_demo.py`.