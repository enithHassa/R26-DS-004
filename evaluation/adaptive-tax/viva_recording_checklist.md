# Viva recording checklist (Phase 5.9)

Deliverable: a **screen recording** of dual-YA adaptivity + calculator covered paths (not committed to git).

Graph size is **not** a success gate. The working calculator + Chapter 4 metrics are.

Use alongside [`docs/PHASES_RUNBOOK.md`](../../docs/PHASES_RUNBOOK.md) and [`phase5/README.md`](phase5/README.md).

## Pre-flight

- [ ] Chapter 4 metrics green: `evaluation/adaptive-tax/phase5/run_chapter4_metrics.py --write-metrics-md`
- [ ] Offline demo: `scripts/adaptive_tax_phase5_demo.py` (T1 != T2 + Sec 52 quotes + ex17 credit)
- [ ] (Optional UI) Adaptive Tax on `http://127.0.0.1:8005`, gateway `:8000`, frontend `:5173`
- [ ] (Optional) Neo4j Desktop up — preferred for GOVERNED_BY panel, not required for metrics
- [ ] Comp B / tax-optimization UI **untouched** (do not demo Component 2)

## Dry-run (API / offline)

- [ ] `COMP_ADAPTIVE_TAX_EXPLAIN_MODE=fixture` when explaining
- [ ] `scripts/adaptive_tax_phase5_demo.py` shows YA 2024/25 T1 != YA 2025/26 T2
- [ ] Distinct Sec 52 `source_quote` printed for T1 vs T2
- [ ] ex17: `final_tax_lkr` gross unchanged; `tax_payable_lkr` after APIT credit
- [ ] Coverage printed **8/8 (100%)**
- [ ] (Optional) `scripts/adaptive_tax_phase5_demo.py --http` with API live

## Screen record (UI narrative)

- [ ] Recorder started
- [ ] Calculator: assessment year **2024/25**, ex08-style inputs (salary 3M + QP 1.5M) -> **T1** -> View report (Sec 52 quote 1.2M)
- [ ] Same inputs, switch year to **2025/26** -> **T2 != T1** -> View report (Sec 52 quote 1.8M / Act 02/2025)
- [ ] Optional: APIT already paid (ex17) -> show gross vs payable
- [ ] Reports: expandable trace + Act `rule_source` quotes (no Master PDF)
- [ ] State aloud: GPT extract does not change tax until admin approve
- [ ] Recorder stopped; file saved off-repo

## After recording

- [ ] Note absolute path + date under **Recording path** in [`README.md`](README.md)
- [ ] Do **not** commit `.mp4` / `.mkv` / `.webm` into the monorepo
- [ ] Confirm `metrics_table.md` still matches latest `runs/phase5_9_*.json`
