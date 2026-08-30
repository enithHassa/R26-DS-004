# Relief Interview — Phase 4 report (extract + verify + accuracy check)

- Status: **complete, accuracy gate PASSED**
- Run: `run_20260820T221919Z`
- Model: `gpt-4o`, `temperature=0`
- API calls: **133** (envelope was 220–340)
- Spend: **~$0.87** of the ~$40 budget
- Catalogs written: **none** — everything is staging, promotion is Phase 5

## 1. What Phase 4 had to prove

Fill the relief and rate catalogs from the Acts alone, and prove the pipeline on
the two years we can independently check before trusting it on the six older
years. Nothing may be hand-typed, and every row must be traceable to a verbatim
passage in an official Act PDF.

## 2. Path check — manifest is the authority

Re-run immediately before any PDF was opened. Each `source_doc_id` resolved to
its `file_name` in [corpus_manifest.json](../../models/adaptive-tax/corpus_manifest.json),
and that exact file was confirmed on disk. No plan-doc filename was used.

| `source_doc_id` | Resolved `file_name` | On disk |
|---|---|---|
| `ird-ira-2017-base` | `IR_Act_No._24_2017_E.pdf` | yes |
| `ird-amend-2021-10` | `IR_Act_No._10_2021_E.pdf` | yes |
| `ird-amend-2022-45` | `IR_Act_No._45_2022_E.pdf` | yes |
| `ird-amend-2023-04` | `IR_Act_No._04_2023_E.pdf` | yes |
| `ird-amend-2023-14` | `IR_Act_No14_2023_E.pdf` | yes |
| `ird-amend-2025-02` | `IR_Act_No_02-2025_E.pdf` | yes |
| `ird-amend-2026-11` | `IR_Act_No_11-2026_E.pdf` | yes |

The Consolidated Act was opened only by the accuracy checker, read-only. The
Guide and the ontology PDF were never opened. Neither can reach a catalog.

## 3. Pipeline

Standalone scripts, copying the focus-window pattern from the component
extractors without importing or editing them:

| Script | Role |
|---|---|
| [`scripts/relief_interview_phase4_extract.py`](../../scripts/relief_interview_phase4_extract.py) | Path check, focus windows, Pass 1, Pass 2, quote gate, staging |
| [`scripts/relief_interview_phase4_accuracy.py`](../../scripts/relief_interview_phase4_accuracy.py) | Ladder assembly, ontology diff, consolidated cross-check ($0) |
| [`scripts/relief_interview_phase4_inspect.py`](../../scripts/relief_interview_phase4_inspect.py) | Read staging rows and their gate verdicts ($0) |

Per Act: one PDF read, then 10 target provisions (sections 5, 6, 7, 8, 11, 16,
52, 89, First Schedule, Fifth Schedule). A provision whose focus window comes
back empty is skipped without an API call — 41 of 70 were skipped this way, and
spot checks confirmed those Acts genuinely do not touch those provisions.

Pass 1 pulls reliefs **and** rates/rules in the same sweep. Pass 2 asks the model
whether each quote is verbatim. The deterministic substring gate then decides
inclusion; Pass 2 is recorded as a supporting signal only, per the plan.

### Two renderings of each PDF

The single most important finding. Rate schedules are laid out column-major in
the PDF text layer: every "Taxable Income" cell is emitted, then every "Tax
payable" cell. Reading that linearly produces two failures at once — no
contiguous quote can span a band row, and the naive pairing is simply wrong. In
Act 45/2022 an early run paired "Rs. 90,000 plus 18%" with the 1.5m–2.0m band
when it belongs to 1.0m–1.5m. The deterministic gate rejected it.

So each PDF is read once into two renderings: the linear text layer, and the
layout-reconstructed tables. Both are verbatim renderings of the same file, so a
quote matching either is Act-backed, and every row records which one it came
from. Rate bands are quoted from the table rendering, where the band and its
rate are correctly paired.

### Inclusion rule

A row is included only if all three hold:

1. its quote is a contiguous substring of the full document (whitespace and
   typography normalised) in one of the two renderings;
2. `act_name`, `section_ref`, `quote` and `source_doc_id` are all present;
3. the quote clears a 15-character evidentiary floor.

## 4. Results

104 rows extracted, **92 included** (88%).

| Row kind | Extracted | Included |
|---|---|---|
| Rate bands | 44 | 39 |
| Rules | 42 | 37 |
| Reliefs | 18 | 16 |

| Act | Included / extracted |
|---|---|
| `ird-ira-2017-base` | 47 / 47 |
| `ird-amend-2021-10` | 8 / 16 |
| `ird-amend-2022-45` | 18 / 19 |
| `ird-amend-2023-04` | 2 / 2 |
| `ird-amend-2023-14` | 4 / 5 |
| `ird-amend-2025-02` | 11 / 11 |
| `ird-amend-2026-11` | 2 / 4 |

Quote provenance: 57 rows quote the text layer, 35 quote the table rendering.

All 12 rejections were the same failure — the quote was not verbatim in the
source, almost always because the model reassembled a readable sentence out of
scattered table cells. None were rejected for missing provenance. Per the plan
these stay missing rather than being hand-typed; they remain in staging with
their verdict recorded, so Phase 5 can re-extract them.

Two review flags carried into staging, neither of which blocks inclusion:
6 included rows where Pass 2 disagreed with the deterministic gate, and 5 rows
citing a provision other than the one requested (a window reaching into a
neighbouring clause).

## 5. Accuracy gate

Full detail in [relief_interview_phase4_accuracy.md](relief_interview_phase4_accuracy.md).

Candidate individual rate ladders were assembled from staging alone: included
First Schedule bands for individuals, grouped by the `effective_from` date the
model read off the Act, kept only where they form a contiguous ladder from zero
to an open-ended top band, and matched to a year by taking the latest ladder
effective on or before 1 April of that year. No value was supplied by hand.

**Both gate years reproduce their ontology pack exactly.**

| YA | Source | Effective | Bands | Verdict |
|---|---|---|---|---|
| 2024/25 | `ird-amend-2022-45` | 2023-04-01 | 6 | MATCH |
| 2025/26 | `ird-amend-2025-02` | 2025-04-01 | 5 | MATCH |

The consolidated Act corroborated 6/6 and 5/5 band boundaries respectively,
read-only.

The same procedure also recovered a complete 6-band ladder from the base Act
effective 2018-04-01 (4/8/12/16/20/24%), which is the starting point for the
older years in Phase 5.

## 6. Deliverables

| Artefact | Path |
|---|---|
| Staging JSON, one file per Act/provision | `models/adaptive-tax/relief-interview/extracted/*__*.json` |
| Run log (per-section status, tokens, spend) | `models/adaptive-tax/relief-interview/extracted/runs/run_20260820T221919Z.json` |
| Candidate rate packs (not promoted) | `models/adaptive-tax/relief-interview/extracted/candidate_rates_{2024_25,2025_26}.json` |
| Machine-readable accuracy result | `models/adaptive-tax/relief-interview/extracted/accuracy_result.json` |
| Accuracy report | `docs/reports/relief_interview_phase4_accuracy.md` |

Each staging file keeps the focus window that produced it alongside the rows, so
every verdict can be re-checked offline without re-reading the PDF.

`approved/{ya}.json` and `rates/{ya}.json` are untouched and still empty — all 8
of them. Promotion is Phase 5's job.

## 7. Phase 8 gate

Cleared. Both engine-supported years are reproducible from Act text alone, so
the extraction pipeline may be trusted for the older years.

## 8. What Phase 5 review should look at first

1. The 12 rejected rows — re-extract, do not hand-type.
2. The 5 rows citing an off-target provision.
3. The 6 rows where Pass 2 disagreed with the deterministic gate.
4. Table-rendered quotes still carry the ` | ` cell separator; decide the display
   form before these reach the UI.
5. Acts 10/2021 and 11/2026 have the weakest yield and deserve a second look.
