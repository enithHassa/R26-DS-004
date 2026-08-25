# Phase 6.9 viva figure screenshot checklist

Use with [`generate_figures.py`](generate_figures.py) markdown export and live UI.

## Coverage bars (Figure 1)

- [ ] Open `http://127.0.0.1:5173/adaptive-tax/coverage`
- [ ] Capture **Phase 5 checklist rollup** (100% / 9/9 areas)
- [ ] Capture **Section 5 — Employment** card expanded (18/18 components)
- [ ] Capture **Section 52** card (shows any pending unsupported components in details)
- [ ] Click **Export JSON** — attach file to dissertation appendix if needed

## Confidence distribution (Figure 2)

- [ ] On Coverage page, note high/medium counts in section details
- [ ] Or run: `evaluation/adaptive-tax/phase6/score_catalog_confidence.py`
- [ ] Screenshot calculator **legal confidence badge** on a high field (e.g. Housing Allowance → View legal basis)

## Unsupported queue demo — Act 11/2026 novelty (Figure 3)

- [ ] Coverage page → **Unsupported rule queue** section visible
- [ ] Show `qp_bank_merger` — **Requires new Rule Engine handler** / Pending
- [ ] In calculator (YA 2025/26), show **Qualifying Payment Brought Forward** is supported (Act 11/2026)
- [ ] State aloud: supported Act amendment vs unsupported queue are different paths

## Version strip (Figure 4)

- [ ] Calculator → run any calc → **Calculated Using** strip on result panel
- [ ] Report page → sticky **Calculated Using** strip at top
- [ ] Switch YA 2024/25 vs 2025/26 — strip `rule_pack_version` changes
- [ ] Legal reasoning graph panel on report (Phase 6.8) optional fourth screenshot

## Regression gate (before recording)

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_KG_MODE = "file"
$env:COMP_ADAPTIVE_TAX_PROVENANCE_MODE = "strict"
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase6/run_chapter4_metrics.py --write-metrics-md
.\.venv-backend\Scripts\python.exe evaluation/adaptive-tax/phase6/generate_figures.py
```

- [ ] `ok=true` in run JSON
- [ ] `metrics_table.md` updated
- [ ] Guide/Master executable-cite guard passes
