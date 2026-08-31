# Relief Interview — Phase 4 accuracy report

- Generated: 2026-08-21T06:27:21.972917+00:00
- Gate verdict: **PASS**
- Staging files: 29
- Rows included in staging: 82 of 92
- API cost of this check: $0 (no model calls)

## What this gate does

Phase 4 has to earn the right to be trusted on the older years. The only years with an independently reviewed rate pack are 2024/25 and 2025/26, so the pipeline is required to reproduce those two from the Acts alone. If it cannot, its 2018/19-2023/24 output is not trustworthy either and Phase 8 must not be written.

## YA 2024/25

- Result: **MATCH**
- Selected ladder: `ird-amend-2022-45` effective 2023-04-01
- Effective date came from: extracted
- Ontology pack: `models/adaptive-tax/ontology/rate_bands_2024_25.json`

| # | Lower | Upper | Extracted | Ontology | Quote source |
|---|-------|-------|-----------|----------|--------------|
| 1 | 0 | 500,000 | 6.0% | 6.0% | table_render |
| 2 | 500,000 | 1,000,000 | 12.0% | 12.0% | table_render |
| 3 | 1,000,000 | 1,500,000 | 18.0% | 18.0% | table_render |
| 4 | 1,500,000 | 2,000,000 | 24.0% | 24.0% | table_render |
| 5 | 2,000,000 | 2,500,000 | 30.0% | 30.0% | table_render |
| 6 | 2,500,000 | no limit | 36.0% | 36.0% | table_render |

Consolidated cross-check (`IRA_Cons_Act_-_2025_Changes.pdf`, read-only): 6/6 band boundaries corroborated.

## YA 2025/26

- Result: **MATCH**
- Selected ladder: `ird-amend-2025-02` effective 2025-04-01
- Effective date came from: extracted
- Ontology pack: `models/adaptive-tax/ontology/rate_bands_2025_26.json`

| # | Lower | Upper | Extracted | Ontology | Quote source |
|---|-------|-------|-----------|----------|--------------|
| 1 | 0 | 1,000,000 | 6.0% | 6.0% | table_render |
| 2 | 1,000,000 | 1,500,000 | 18.0% | 18.0% | table_render |
| 3 | 1,500,000 | 2,000,000 | 24.0% | 24.0% | table_render |
| 4 | 2,000,000 | 2,500,000 | 30.0% | 30.0% | table_render |
| 5 | 2,500,000 | no limit | 36.0% | 36.0% | table_render |

Consolidated cross-check (`IRA_Cons_Act_-_2025_Changes.pdf`, read-only): 5/5 band boundaries corroborated.

## Ladders discovered

| Act | Effective from | Bands | Complete | Notes |
|-----|----------------|-------|----------|-------|
| `ird-ira-2017-base` | 2017-04-01 | 6 | yes | contiguous 0 → open |
| `ird-amend-2021-10` | 2020-01-01 | 3 | yes | contiguous 0 → open |
| `ird-amend-2022-45` | 2022-04-01 | 3 | yes | contiguous 0 → open |
| `ird-amend-2022-45` | 2023-04-01 | 6 | yes | contiguous 0 → open |
| `ird-amend-2025-02` | 2025-04-01 | 5 | yes | contiguous 0 → open |

## Phase 8 gate

Both engine-supported years reproduce their ontology pack exactly from Act text, so the extraction pipeline is cleared. Phase 5 human review is still required before any catalog is promoted.

