# Phase 6.9 — Eval / viva metrics

Extends [Phase 5.9](../phase5/README.md) Chapter 4 runner with filing-catalog + dashboard metrics.

## One-shot

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase6/run_chapter4_metrics.py --write-metrics-md
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase6/generate_figures.py
.\.venv-backend\Scripts\python.exe scripts/adaptive_tax_phase6_demo.py
```

## Layout

| Script | Purpose |
|--------|---------|
| `run_chapter4_metrics.py` | All Phase 5.9 + Phase 6.9 metrics → `runs/phase6_9_*.json` |
| `score_catalog_confidence.py` | high/medium/low/pending distribution |
| `score_executable_cites.py` | Guide/Master never in executable provenance |
| `generate_figures.py` | `figures/FIGURES.md` + `figure_data.json` |
| `viva_figure_checklist.md` | Screenshot checklist for dissertation figures |

## Phase 6.9 additions (vs 5.9)

| Metric | Target |
|--------|--------|
| Legal coverage (section grain) | Checklist 100% + per-section catalog bars |
| Catalog confidence distribution | Counts by `legal_confidence` tier |
| Unsupported rule queue | ≥1 pending; Act 11/2026 novelty narrative |
| Version strip checklist | `knowledge_versions` for both YAs |
| Guide/Master not executable | 0 violations in bootstrap/catalog/goldens |
| Filing-line regression | Phase 5 goldens + phase6/68 + emp/inv/QP/biz/other tests |

## Dependency graph

```
6.0 Foundation → 6.1–6.5 Catalog heads → 6.6 Field explain → 6.7 UI versions
  → 6.8 Coverage dashboard → 6.9 Eval (this folder)
```

See [`docs/PHASES_RUNBOOK.md`](../../../docs/PHASES_RUNBOOK.md) Phase 6.9 section.
