# Adaptive Tax — Phase 5 evaluation

Calculator-first accuracy expansion for resident individual APIT (YA 2024/25 + 2025/26).

## Principles

- Official IRD Acts are the source of truth (not Tax Knowledge Base Master).
- GPT extracts only; Python Rule Engine calculates.
- Admin must approve before rules affect tax.
- **Provenance:** every executable engine step → approved `rule_source` → Act section + `source_quote`.
- **Coverage:** fraction of checklist areas that are harvested + approved + engine-wired + provenance-complete.
- **Store sync (standing):** after **every** Phase 5 capability area, keep PostgreSQL / Neo4j / Chroma / param packs / Rule Engine / Explanation evidence aligned. Calc-ontology Neo4j reload is per-milestone; bulk corpus edge import remains Phase 5.10.

## Post-milestone knowledge sync (required)

After completing an area (Business, Investment, Tax Credits, …):

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "adaptive-tax-dev"

# Reload Neo4j calc ontology + verify packs / engine / graph
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_sync_verify.py --apply-neo4j

# When corpus / Act PDFs / manifest changed — also rebuild Chroma + RAG smoke
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_sync_verify.py `
  --apply-neo4j --apply-chroma --chroma-smoke
```

| Store | What must stay aligned | How |
|-------|------------------------|-----|
| **PostgreSQL** | Amendment-approved `rule_source` / `rule_versions` | Approve path; calc uses bootstrap offline |
| **Neo4j** | Concepts + `CONTRIBUTES_TO` / `DEFINES` / `GOVERNED_BY` / … | `neo4j_load_calc_ontology_nodes.py` + `neo4j_load_curated_edges.py` (via `--apply-neo4j`) |
| **Chroma** | Act paragraphs for explain RAG (`usable_for_explain`; Master blocked) | `adaptive_tax_build_chroma.py` when corpus changes (`--apply-chroma`) |
| **Param packs** | Each band/relief `rule_source_id` ∈ bootstrap | Verified by sync script |
| **Rule Engine** | Deterministic handlers + provenance gates | Sync script calc smoke (`file`/`neo4j`) |
| **Explanation** | Evidence from Chroma + approved PG quotes only | `--chroma-smoke`; Master PDF excluded |

Script: [`scripts/adaptive_tax_phase5_sync_verify.py`](../../../scripts/adaptive_tax_phase5_sync_verify.py)

## Checklist / scorers

| Artifact | Path |
|----------|------|
| Coverage checklist | [`models/adaptive-tax/harvest/coverage_checklist_v1.json`](../../../models/adaptive-tax/harvest/coverage_checklist_v1.json) |
| Section harvest targets | [`models/adaptive-tax/harvest/section_targets_v1.json`](../../../models/adaptive-tax/harvest/section_targets_v1.json) |
| Coverage scorer | [`../coverage/score_coverage.py`](../coverage/score_coverage.py) |
| Provenance bootstrap | [`models/adaptive-tax/fixtures/provenance_bootstrap_v1.json`](../../../models/adaptive-tax/fixtures/provenance_bootstrap_v1.json) |
| Provenance scorer | [`../provenance/score_provenance.py`](../provenance/score_provenance.py) |
| Metrics table | [`../metrics_table.md`](../metrics_table.md) |

## Phase 5.10 — Bulk graph import (last; optional scale)

**After** Evaluation (5.9). Scales Neo4j calc-related relationships to **≥300** for dissertation breadth — **not** a Coverage gate. Bulk `MENTIONS` are non-executable.

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "adaptive-tax-dev"

# Build calculation_edges_full.jsonl (seed + harvest hints + corpus MENTIONS) and load Neo4j
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_import_calc_edges.py --min-edges 300 --load-neo4j

# Or reload via sync (prefers calculation_edges_full when present)
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_sync_verify.py --apply-neo4j
```

| Check | Expect |
|-------|--------|
| `GET /api/v1/knowledge/graph-stats` → `calc_edge_total` | **≥ 300** (includes MENTIONS) |
| `executable_calc_edge_total` | curated DEFINES/GOVERNED_BY/… only |
| Coverage | **unchanged** (8/8) — MENTIONS do not inflate checklist |
| Provenance / goldens | still **1.00** / green on executable paths |
| File KG | reads `calculation_edges_full.jsonl` when present |

Script: [`../../../scripts/adaptive_tax_import_calc_edges.py`](../../../scripts/adaptive_tax_import_calc_edges.py)

## Phase 5.9 — Evaluation & viva hardening (before bulk graph)

Dissertation **Chapter 4** metrics while the calculator is the product. **Graph size is not a success gate.**

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"

# One-shot Chapter 4 table + run JSON
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase5/run_chapter4_metrics.py --write-metrics-md

# Dual YA + Sec 52 quotes + ex17 credit smoke (offline)
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_demo.py

# Optional live API demo (:8005)
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_demo.py --http
```

| Artifact | Path |
|----------|------|
| Filled metrics table | [`../metrics_table.md`](../metrics_table.md) |
| Metrics runner | [`run_chapter4_metrics.py`](run_chapter4_metrics.py) |
| Harvest-section extraction | [`../extraction/score_harvest_sections.py`](../extraction/score_harvest_sections.py) |
| Viva checklist | [`../viva_recording_checklist.md`](../viva_recording_checklist.md) |
| Demo script | [`../../../scripts/adaptive_tax_phase5_demo.py`](../../../scripts/adaptive_tax_phase5_demo.py) |

**DoD (calculator track):** Coverage 8/8; provenance 1.00 strict on covered paths; goldens pass; citation/grounding 1.00 on fixtures; dual-YA T1≠T2 with Sec 52 quotes; Comp B untouched; GPT does not affect tax until admin approve.

## Phase 5.0 foundations (this milestone)

- Dual YA packs: `relief_caps_2024_25.json` (Sec 52 = 1.2M), `relief_caps_2025_26.json` (1.8M)
- Section harvest CLI: `scripts/adaptive_tax_section_harvest.py`
- Master PDF demoted: `usable_for_explain=false` in corpus manifest

## Phase 5.8 — Credits & final liability (APIT already paid)

- **Gross vs payable:** `final_tax_lkr` remains First Schedule gross liability; `tax_payable_lkr = max(0, liability − credits)` when Act-backed `tax_credit` provenance resolves
- Request: `apit_already_paid` (non-final WHT / APIT already paid); response also exposes `tax_credits_applied_lkr`
- Handler: `tax_credit` → trace step `apply_tax_credit` with `rule_source_ids` (Sec **89**; Sec **2(3)** deducts credits)
- Harvest seed: [`sec89_tax_credit_harvest_v1.json`](../../../models/adaptive-tax/fixtures/sec89_tax_credit_harvest_v1.json)
- Golden: **ex17** (salary 1.8M → gross 42,000; APIT 20,000 → payable 22,000)
- Coverage: `tax_credits` covered → **8/8**
- **Neo4j / RAG sync** after pull:

```powershell
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<your-password>"
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase5_sync_verify.py --apply-neo4j --chroma-smoke
```

Verify in Neo4j Browser:

```cypher
MATCH (c:Concept)-[r:GOVERNED_BY]->(s:Section)
WHERE c.concept_id IN ['tax_credit','apit_already_paid']
RETURN c.concept_id, s.section_uid, r.rule_source_id;
```

## Phase 5.7 — Investment income

- **Base path:** `investment_income` → assessable under Sec 7; `DEFINES` + `GOVERNED_BY` + `CONTRIBUTES_TO`
- Harvest seed: [`sec7_investment_harvest_v1.json`](../../../models/adaptive-tax/fixtures/sec7_investment_harvest_v1.json)
- Optional Sec **7(3)(a)** exclusion: `investment_final_withholding` via `exclude_investment_final_wht` (Act quote required; otherwise sum as entered)
- Goldens: **ex15** (base 1.8M → 42,000); **ex16** (exempt interest / final-WHT 200k → tax 24,000) — plan name `ex13_investment_exempt_interest` mapped to **ex16** (ex13 already used for business 5.6b)
- Coverage: `investment_income` covered → **7/8**

## Phase 5.6 — Business income (simplified assessable)

- **5.6a:** `business_income` field = net assessable business profits (single amount); no gross/expense split
- Graph: Sec 6 `DEFINES` + `GOVERNED_BY` + `CONTRIBUTES_TO` assessable; bootstrap `bootstrap:business_income`
- Harvest seed: [`sec6_business_harvest_v1.json`](../../../models/adaptive-tax/fixtures/sec6_business_harvest_v1.json)
- Golden: **ex02** (1.8M business → tax 42,000, same as ex01)
- **5.6b:** optional `business_gross` / `business_deductions` (Sec 11) / `capital_allowances` (Sec 16) — Act-gated `compute_business_net`; simplified formula (no full CA schedule engine); goldens **ex13**, **ex14**
- Coverage: `business_income` covered → **6/8**
- **Neo4j sync:** after pulling Phase 5.6 ontology changes, re-run the existing loaders (idempotent MERGE):

```powershell
$env:NEO4J_URI = "bolt://127.0.0.1:7687"
$env:NEO4J_USER = "neo4j"
$env:NEO4J_PASSWORD = "<your-password>"
.\.venv-backend\Scripts\python.exe scripts/neo4j_load_calc_ontology_nodes.py
.\.venv-backend\Scripts\python.exe scripts/neo4j_load_curated_edges.py `
  --edges-jsonl models/adaptive-tax/ontology/mvp_calc_edges_seed.jsonl --warn-miss
```

Verify in Neo4j Browser:

```cypher
MATCH (bi:Concept {concept_id:'business_income'})-[r:CONTRIBUTES_TO]->(ai:Concept {concept_id:'assessable_income'})
RETURN bi.concept_id, type(r), ai.concept_id, r.rule_source_id;

MATCH (c:Concept)-[r:GOVERNED_BY]->(s:Section)
WHERE c.concept_id IN ['business_income','business_gross','business_deductions','capital_allowances']
RETURN c.concept_id, s.section_uid, r.rule_source_id ORDER BY c.concept_id;
```

Expect **0 missing endpoint(s)** from the edge loader and `POST /api/v1/calculate` with `COMP_ADAPTIVE_TAX_KG_MODE=neo4j` to resolve `business_income` via the live graph.

## Phase 5.5 — Donations / charitable relief

- Live path: Fifth Sch **1(a)** `qp_approved_charitable` — `allowable = min(claimed, 75000, floor(assessable/3))`
- Standalone Donations card retired (`don_approved_charitable` inactive). Scalar / `don_*` lines fold into 1(a); no second donation deduct and no 33% path
- KG: `donation` / `donation_cap` remain as aliases (explain still finds “charitable donation”); `LIMITED_BY` documents the 75k / one-third ceiling — **no** `donation` `DEDUCTED_FROM`
- Harvest seed: [`donations_harvest_v1.json`](../../../models/adaptive-tax/fixtures/donations_harvest_v1.json) (non-executable alias)
- Goldens: **ex03_donation_cap_on_assessable.json**, **ex11_donation_over_cap.json**, **ex23_donation_components.json**
- 1(b) government / local authority / university / fund donations stay on the QP Donations subgroup
- Coverage: `donations` covered → **5/8**

## Phase 5.4 — Section 52 qualifying payments + carry-forward

- Act-verified aggregate caps: YA 2024/25 **1.2M**; YA 2025/26 **1.8M** (Act 02/2025)
- Handlers: `cap_absolute` (5.4a trace step `cap_qualifying_payment_cap`); `carry_forward_qp` (5.4b, YA 2025/26 only when provenance resolves)
- Request: `qualifying_payment_brought_forward`; response/trace: `qualifying_payment_carry_forward_out`
- Harvest seed: [`sec52_harvest_v1.json`](../../../models/adaptive-tax/fixtures/sec52_harvest_v1.json)
- Goldens: ex04, ex08 (dual YA adaptivity), **ex10** (carry-forward)
- Viva demo: `scripts/adaptive_tax_phase4_demo.py` — ex08 YA switch T1≠T2 (optional `--with-approve` for ex04 override)
- Coverage: `sec52_qualifying_payment_cap` covered → **4/8**; optional `sec52_carry_forward` covered when enabled

## Phase 5.3 — Personal relief (resident)

- Act-verified caps: YA 2024/25 **1.2M**; YA 2025/26 **1.8M** (Act 02/2025 / IRD PN IT/2025-01)
- Handler: `personal_relief_resident`; non-resident → 0 relief with provenance on step
- Approve writer: `write_personal_relief_override_from_rules` (YA-scoped `relief_updates`)
- Harvest seed: [`personal_relief_harvest_v1.json`](../../../models/adaptive-tax/fixtures/personal_relief_harvest_v1.json)
- Goldens: ex05, ex06 (2024/25); YA 2025/26 salary 1.8M → tax **0**
- Coverage: `personal_relief` covered → **3/8**

## Phase 5.2 — First Schedule rates (legal verify)

- Act-verified packs: YA 2024/25 **six** bands (includes **12%**); YA 2025/26 **five** bands (6% on first **1M**, no 12%)
- Each band carries `rule_source_id` → bootstrap Act quote; slab steps cite First Schedule section UID
- Approve writer: `write_rate_band_override_from_rules` for `rule_type=rate`
- Goldens: ex07 (top band) + `ex09_first_schedule_band_edges.json`
- Coverage: `first_schedule_rates` covered → **2/8**

## Phase 5.1 — Employment income (Section 5)

- Gross employment → `CONTRIBUTES_TO` assessable with Sec 5 provenance
- Optional Sec **5(3)(a)** exclusion: `employment_final_withholding` via `exclude_if_final_wht` (Act quote required)
- Harvest seed: [`sec5_employment_harvest_v1.json`](../../../models/adaptive-tax/fixtures/sec5_employment_harvest_v1.json)
- Golden: `ex12_employment_with_excluded_allowance.json` (1.8M − 0.2M FWH → tax 24000)
- Coverage checklist: `employment_income` marked covered

## Phase 5.0b — Provenance gate

- Services: `provenance.py` + `engine_handlers.py`; rule engine attaches `rule_source_ids` per step
- Bootstrap Act quotes keep CI/offline goldens green without Postgres rows
- Default: `COMP_ADAPTIVE_TAX_PROVENANCE_MODE=legacy` (warn + `legacy_seed`); flip to `strict` for viva after verifying bootstrap
- Report UI: Provenance panel (section + quote)

```powershell
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/provenance/score_provenance.py
```

## Reproduce Coverage score

```powershell
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/coverage/score_coverage.py
```
