# Adaptive Tax evaluation metrics (dissertation Chapter 4)

Filled from local **fixture-mode** scoring runs on 2026-08-03. OpenAI explain mode is validated by the same citation/grounding scripts when live responses are saved to JSON.

| Metric | Method | Result | Notes |
|--------|--------|--------|-------|
| Extraction precision | Manual 20-field gold vs `section52_extract_sample.json`; `extraction/score_extraction.py` | **20/20 = 1.00** | Act 02/2025 Sec 52 labeled sample |
| Calculation accuracy | `test_rule_engine_examples.py` (ex01–ex08) | **8/8** | See `calculation/RESULTS.md` (11 pytest cases) |
| Citation faithfulness | `sections_cited ⊆ sections_retrieved`; `citation_faithfulness/score_citations.py` | **1/1 = 1.00** | `explain_ex04_sample.json` |
| Explanation grounding | Sentence → step `evidence_chunk_ids` / `rule_source_id`; `explanation_grounding/score_grounding.py` | **1.00** on production sample; **2/2** on positive fixture JSONL | Negative control in `fixtures/explain_grounding_negative.jsonl` |
| Amendment adaptivity | ex08 pre/post + ex04 override T1≠T2; `amendment_adaptivity/score_adaptivity.py` | **pass** | Δtax ex08 = 30000; demo T1=48000 → T2=0 |

Reproduce: see [README.md](README.md).
