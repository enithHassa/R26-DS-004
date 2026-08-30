# System-wide Provenance Audit Report

**Date:** 2026-08-18  
**Mode:** READ-ONLY investigation — no fixture or engine changes made.  
**Artifacts:** `data/processed/adaptive-tax/audit/` (inventory, quote checks, 18 harvest JSON files)

---

## Executive summary

This audit inventoried **76 rows** (param packs, 47 bootstrap quotes, ontology LIMITED_BY edges, 6 hardcoded engine constants), synced **9 IRD Act PDFs** from Desktop, built a text corpus, ran **18 OpenAI section-harvest extractions**, and performed **deterministic full-document quote substring checks** on all bootstrap rules.

### Category counts (after manual review of harvest limitations)

| Cat | Name | Count | Notes |
|-----|------|-------|-------|
| **5** | NO CORRESPONDING ACT TEXT FOUND | **3** | Stale aggregate QP cap (×2 ontology rows) + rent-relief quote wording |
| **3** | VALUE MISMATCH | **0** | No confirmed numeric errors |
| **4** | SECTION/ACT MISATTRIBUTION | **2** | Cinema construction quote source; carry-forward attribution **confirmed correct** |
| **2** | QUOTE MISMATCH ONLY | **~35** | Paraphrased bootstrap quotes; underlying numbers generally correct |
| **6** | UNABLE TO VERIFY (harvest focus miss) | **~12** | Automated harvest hit wrong section/window; full-text check used instead |
| **1** | MATCH | **~24** | Verbatim quotes or value+Act text confirmed |

**No category-3 (VALUE MISMATCH) findings were confirmed.** The severe QP aggregate-cap bug class (invented numeric) does **not** appear elsewhere in live executable parameters beyond the already-removed aggregate cap and stale ontology edges.

### Highest-priority confirmed issues

1. **Stale `sec52_qualifying_payment_cap` ontology edges** (Cat **5**) — aggregate QP cap removed from engine (Path B) but COVERS_RELIEF edges remain.
2. **`bootstrap:rent_relief` quote** (Cat **2**→borderline **4**) — bootstrap cites Fifth Schedule 2(c) wording that does **not** appear verbatim in any Act PDF; consolidated Act has a **different** 25%-of-rental provision (investment-asset repair/maintenance relief, not the cited text).
3. **Widespread paraphrased bootstrap quotes** (Cat **2**) — Sec 5–8, 11, 16, 89, personal relief, rate slabs, Sec 52 deduct, solar relief, carry-forward: values largely correct but quotes are editorial summaries, not verbatim Act substrings.
4. **`bootstrap:qp_cinema_construction`** (Cat **4**, low) — "twenty five million rupees" text found in consolidated Act; amend-2021 PDF alone did not match in full-text scan (may be consolidation artifact — treat as **6** until amend PDF re-checked).

---

## Stage A — Consolidated inventory

Full machine-readable inventory: `data/processed/adaptive-tax/audit/stage_a_inventory.json` (76 rows).

### Executable numeric parameters (live calculation)

| concept_id | claimed value | section | source_doc_id | rule_source_id | file(s) |
|------------|---------------|---------|---------------|----------------|---------|
| `personal_relief` | 1,200,000 | First Schedule | `ird-ira-2017-base` | `bootstrap:personal_relief_2024_25` | `relief_caps_2024_25.json`, `relief_caps_pre_amend_2025.json` |
| `personal_relief` | 1,800,000 | First Schedule | `ird-amend-2025-02` | `bootstrap:personal_relief_2025_26` | `relief_caps_2025_26.json` |
| `donation_cap` | 75,000 (+ one-third) | Fifth Sch 1(a) | `ird-ira-2017-base` | `bootstrap:donation_cap_*` | all relief packs |
| `solar_panel_relief` | 600,000 | Fifth Sch 2(g) | `ird-amend-2021-10` | `bootstrap:solar_panel_relief` | all relief packs + `rule_engine.py` |
| `rent_relief` | 25% of included rents | Fifth Sch 2(c) | `ird-ira-2017-base` | `bootstrap:rent_relief` | relief packs + `rule_engine.py` `_RENT_PCT` |
| `first_schedule_rates` | 6 bands (6/12/18/24/30/36%) | First Schedule | `ird-ira-2017-base` | `bootstrap:first_schedule_rates_2024_25` | `rate_bands_2024_25.json` |
| `first_schedule_rates` | 5 bands (6/18/24/30/36%; 12% removed) | First Schedule | `ird-amend-2025-02` | `bootstrap:first_schedule_rates_2025_26` | `rate_bands_2025_26.json` |
| `qp_approved_charitable` | min(claimed, 75k, floor(AI/3)) | Fifth Sch 1(a) | `ird-ira-2017-base` | `bootstrap:qp_approved_charitable` | `qp_categories.py` |
| `qp_film_production` | cost ≥ 5,000,000 | Fifth Sch 1(f)(i) | `ird-amend-2021-10` | `bootstrap:qp_film_production` | `qp_categories.py` |
| `qp_cinema_construction` | 25,000,000 | Fifth Sch 1(f)(ii) | `ird-amend-2021-10` | `bootstrap:qp_cinema_construction` | `qp_categories.py` |
| `qp_cinema_upgrading` | 10,000,000 + one-third TI | Fifth Sch 1(f)(iii) | `ird-amend-2021-10` | `bootstrap:qp_cinema_upgrading` | `qp_categories.py` |

**Leftover (not param_store):** `relief_caps.json` — KG relief-id map only.

### Bootstrap quotes inventoried

47 rules in `provenance_bootstrap_v1.json`. Full-text quote verification summary (`stage_b_quote_checks_refined.json`):

- **14 verbatim** in claimed PDF
- **7 partial** match (opening clause only)
- **26 non-verbatim** (paraphrase or editorial)
- **0** found only in a different official PDF (except cinema construction → consolidated)

---

## Stage B — Independent re-extraction

### PDFs synced and corpus built

All 9 Desktop PDFs copied to `data/raw/adaptive-tax/`:

| source_doc_id | PDF | Text extracted |
|---------------|-----|----------------|
| `ird-ira-2017-base` | IR_Act_No._24_2017_E.pdf | 354 KB / 8,131 lines |
| `ird-amend-2021-10` | IR_Act_No._10_2021_E.pdf | yes |
| `ird-amend-2022-45` | IR_Act_No._45_2022_E.pdf | yes |
| `ird-amend-2023-04` | IR_Act_No._04_2023_E.pdf | yes |
| `ird-amend-2023-14` | IR_Act_No14_2023_E.pdf | yes |
| `ird-amend-2025-02` | IR_Act_No_02-2025_E.pdf | yes |
| `ird-amend-2026-11` | IR_Act_No_11-2026_E.pdf | yes |
| `ird-consolidated-2025` | IRA_Cons_Act_-_2025_Changes.pdf | yes |
| `ird-guide-ira` | Guide to Inland Revenue Act.pdf | excluded from executable SoT |

18 OpenAI harvest runs persisted under `data/processed/adaptive-tax/audit/stage_b_harvest/`.

### Harvest limitation (important)

Automated section harvest frequently **missed the intended section** because `focus_section_text` matched wrong headings (e.g. `--section 5` landed on Section **56** partnership text; `fifth_schedule` landed on TOC page 13; `first_schedule` on base Act returned only "FIRST SCHEDULE Tax Rates 200"). **Full-document text search was used as the authoritative Stage B cross-check** where harvest focus failed.

---

## Stage C — Findings (sorted by severity)

### Category 5 — NO CORRESPONDING ACT TEXT FOUND

| Row | System claim | Independent finding | Confidence | Files if confirmed |
|-----|--------------|---------------------|------------|-------------------|
| `ontology:…:sec52_qualifying_payment_cap` (×2) | COVERS_RELIEF edge to aggregate QP cap | Engine Path B removed aggregate cap; no Act text supports a single Sec 52 aggregate ceiling | **high** | `mvp_calc_edges_seed.jsonl`, `calculation_edges_full.jsonl` |
| `bootstrap:rent_relief` / `engine:rent_relief_pct` | Quote: "twenty five per centum of the total rental income from any land or building" (Fifth Sch 2(c)) | Phrase **not found** in any official PDF. Consolidated Act has: "25 percent of the total rental income … being a relief for the repair, maintenance, and depreciation relating to the **investment asset**" — different operative text. 25% numeric may still be intended but cited quote is **not Act text**. | **medium** | `provenance_bootstrap_v1.json`, `rule_engine.py` (verify correct provision first) |

### Category 4 — SECTION/ACT MISATTRIBUTION

| Row | System claim | Independent finding | Confidence | Files if confirmed |
|-----|--------------|---------------------|------------|-------------------|
| `bootstrap:sec52_carry_forward_2025_26` | `ird-amend-2026-11`, Sec 52(4) | **Attribution CORRECT.** Act 11/2026 contains Sec 52(4) carry-forward. Bootstrap quote is **paraphrase** (Cat 2): Act says "shall be carried forward **and deducted from the assessable income…**"; bootstrap says "such amount which cannot be deducted shall be carried forward". **Reclassified: Cat 2 only, not 4 or 5.** | **high** | `provenance_bootstrap_v1.json` (quote fix only) |
| `bootstrap:qp_cinema_construction` | `ird-amend-2021-10` | "twenty five million rupees" found in **consolidated** Act; not confirmed in amend-2021 PDF full-text scan alone | **low** | `provenance_bootstrap_v1.json`, `qp_categories.py` |

### Category 2 — QUOTE MISMATCH ONLY (numeric value corroborated)

| Row | Value OK? | Issue | Act evidence |
|-----|-----------|-------|--------------|
| `personal_relief` 1.2M | **yes** | Bootstrap quote is editorial | Consolidated First Schedule: "Rs. 1,200,000 … prior to April 1, 2025" |
| `personal_relief` 1.8M | **yes** | Bootstrap cites IRD PN; quote not verbatim | Act 02/2025: "Rs. 1,800,000, for each year of assessment commencing on or after April 1, 2025" |
| `first_schedule_rates` 2024/25 | **yes** | Bootstrap quote is tax-chart summary, not verbatim | Consolidated Act First Schedule rate table (6 bands incl. 12%) |
| `first_schedule_rates` 2025/26 | **yes** | Bootstrap quote is summary | Act 02/2025 amends First Schedule; 12% band removed in param pack |
| `solar_panel_relief` 600k | **yes** | Bootstrap quote paraphrased | Act 10/2021: "Rs. 600,000 for each year of assessment, upto the total expenditure on such solar panels…" |
| `donation_cap` / `qp_approved_charitable` 75k + ⅓ | **yes** | Quote **verbatim** in base/consolidated | "(iia) … one-third of the taxable income … or Rupees seventy five thousand, whichever is less" |
| `qp_film_production` 5M | **yes** | Quote verbatim in consolidated | "not less than five million rupees" |
| `qp_cinema_upgrading` 10M + ⅓ | **yes** | Quote verbatim in consolidated | "not exceeding ten million rupees" + one-third restriction |
| Sec 5–8, 11, 16, 89 bootstrap rules | n/a (structural) | Heading/summary paraphrases; punctuation differs from PDF OCR | Concepts present in base Act; quotes not verbatim substrings |
| `sec52_deduct_qp_*` | n/a | Paraphrased section headings | Sec 52 operative text differs between pre/post 2025 amendment wording |
| `sec52_carry_forward_2025_26` | n/a | Paraphrase of Act 11/2026 Sec 52(4) | Substance in Act 11/2026; wording differs |

### Category 6 — UNABLE TO VERIFY (automated harvest only)

Rows where OpenAI harvest focus window failed but **full-text manual check resolved** are listed above under Cat 2/1. Remaining Cat 6 items are duplicate param-pack rows sharing the same underlying finding as their engine/bootstrap row.

### Category 1 — MATCH (selected)

- `bootstrap:qp_approved_charitable`, `donation_cap*`, `qp_government_*`, `qp_samurdhi_shop`, `qp_film_production`, `qp_cinema_upgrading` — verbatim Fifth Schedule quotes in base/consolidated Act
- `param:relief_caps_*:donation_cap` — 75k dual cap confirmed
- `param:relief_caps_2025_26:personal_relief` — 1.8M confirmed in Act 02/2025

---

## Stage D — Key cross-check table (executable parameters only)

| concept_id | claimed | quote status | value status | category | files to change if confirmed |
|------------|---------|--------------|--------------|----------|------------------------------|
| personal_relief 1.2M | 1,200,000 | paraphrase | **MATCH** | 2 | `provenance_bootstrap_v1.json` |
| personal_relief 1.8M | 1,800,000 | paraphrase | **MATCH** | 2 | `provenance_bootstrap_v1.json` |
| donation_cap | 75k / ⅓ AI | verbatim | **MATCH** | 1 | — |
| solar_panel_relief | 600,000 | paraphrase | **MATCH** | 2 | `provenance_bootstrap_v1.json` |
| rent_relief | 25% | **wrong quote text** | **uncertain provision** | 5/6 | `provenance_bootstrap_v1.json`, `rule_engine.py` — needs human legal review |
| first_schedule 2024/25 | 6 bands | paraphrase | **MATCH** | 2 | `provenance_bootstrap_v1.json` |
| first_schedule 2025/26 | 5 bands | paraphrase | **MATCH** | 2 | `provenance_bootstrap_v1.json` |
| qp_film 5M | gate | verbatim | **MATCH** | 1 | — |
| qp_cinema 25M | cap | not in amend PDF alone | likely OK in consolidated | 4/6 | `provenance_bootstrap_v1.json` |
| qp_cinema 10M | cap | verbatim | **MATCH** | 1 | — |
| sec52_carry_forward | n/a | paraphrase | substance in Act 11/2026 | 2 | `provenance_bootstrap_v1.json` |
| sec52_qualifying_payment_cap | stale edge | n/a | **removed from engine** | 5 | ontology JSONL files |

**Category 3 (VALUE MISMATCH): none confirmed.**

---

## Methodology

1. **Stage A:** `scripts/adaptive_tax_provenance_audit.py` parsed param packs, bootstrap, ontology LIMITED_BY edges, hardcoded constants.
2. **PDF sync:** `scripts/adaptive_tax_sync_ird_docs.py --source Desktop/IRD_Docs`
3. **Corpus:** `scripts/adaptive_tax_build_corpus.py` → `data/processed/adaptive-tax/text/*.txt`
4. **Layer 1 — Quote check:** Normalized whitespace substring test of each bootstrap `source_quote` against claimed PDF full text (+ refined pass in `stage_b_quote_checks_refined.json`).
5. **Layer 2 — OpenAI harvest:** 18 runs via `extract_rules(harvest_mode=section)` with `COMP_ADAPTIVE_TAX_EXTRACTION_MODE=openai`.
6. **Layer 3 — Manual full-text verification:** Python context search on consolidated Act and amendment PDFs for numeric phrases (75k, 600k, 1.2M, 1.8M, carry-forward, cinema caps).
7. **Classification:** Conservative rules per plan; harvest-only failures downgraded when full-text resolved.

### Limitations

- Section harvest focus windows are unreliable for numeric schedule extraction on this corpus (TOC hits, Section 5 → 56 confusion).
- Consolidated Act used as secondary SoT when amendment PDFs contain only delta text.
- Guide PDF excluded from executable verification.
- No changes made to forbidden files per audit charter.

---

## Stage E — Recurring-amendment process check

### E1. Can a new Act PDF enter the system end-to-end without manual JSON editing?

**No — not today.**

| Step | Supported? | Gap |
|------|------------|-----|
| PDF sync / corpus build | yes | `adaptive_tax_sync_ird_docs.py`, `adaptive_tax_build_corpus.py` |
| Section re-extract (OpenAI) | partial | `adaptive_tax_section_harvest.py`; output → `harvest_pending/*.json`, **not auto-applied** |
| Amendment API pipeline | partial | `upload → extract → review → approve` writes Postgres + optional `active_relief_caps.json` for **personal relief, rate bands, donation cap only** |
| Sec 52 / QP / Fifth Schedule caps | **no** | `write_sec52_override_from_rules` deprecated (no-op); QP caps live in `qp_categories.py` |
| Provenance quotes for calculate() | **no** | `provenance.py` reads **`provenance_bootstrap_v1.json` only** — approved Postgres `rule_source` rows are **not** loaded |
| Ontology edges | manual | `mvp_calc_edges_seed.jsonl` + `*_harvest_v1.json` → `calculation_edges_full.jsonl` via import script |

`section_targets_v1.json` omits Fifth Schedule, Sec 7/8/11/16/89 — new Acts need custom harvest keys or manifest updates.

### E2. Bypass paths (root cause of QP-class bugs)

| Bypass | Location | Risk |
|--------|----------|------|
| Bootstrap quotes + handler map | `provenance_bootstrap_v1.json` | Hand-typed/paraphrased quotes bypass review; drives strict provenance gate |
| Param packs | `relief_caps_*.json`, `rate_bands_*.json` | Direct numeric edits (`act_verified` / `manual_seed`) |
| Hardcoded caps | `qp_categories.py`, `rule_engine.py` | No JSON, no amendment pipeline |
| Ontology edges | `mvp_calc_edges_seed.jsonl`, harvest fixtures | Manual seed → `calculation_edges_full.jsonl`; stale edges persist after engine changes |
| Viva reset | `POST /admin/params/reset-to-pre-amend` | Seeds override without extract/review |
| LegalRuleEvidence approve | stub | Does not mutate engine params |

**Process conclusion:** The reviewed amendment pipeline is **not** the sole path executable data enters the system. Bootstrap fixtures, param packs, and engine constants remain authoritative for `calculate()`. The QP aggregate-cap incident was enabled by direct bootstrap/ontology seeding without a hard gate tying quotes to verbatim PDF substrings. Closing this gap requires a future policy decision (e.g. require amendment-pipeline approval for all bootstrap/param/engine changes).

---

## Recommended follow-up decisions (no action taken)

Each item below should be its own go/no-go fix pass (like Path A vs Path B for QP cap):

1. **Remove stale `sec52_qualifying_payment_cap` ontology edges** (high confidence, Cat 5).
2. **Replace paraphrased bootstrap quotes** with verbatim Act substrings for strict provenance (bulk Cat 2 — ~26 rules).
3. **Investigate rent relief provision** — confirm whether engine should use investment-asset 25% repair relief vs Fifth Schedule 2(c); quote may cite wrong provision (Cat 5/6).
4. **Wire approved Postgres rules into `provenance.py`** or deprecate bootstrap bypass (process fix).
5. **Extend section harvest targets** to Fifth Schedule and missing sections; fix Section 5 vs 56 focus collision.

---

*Audit script: `scripts/adaptive_tax_provenance_audit.py`. Re-run with `--skip-harvest` to reuse cached harvest JSON.*
