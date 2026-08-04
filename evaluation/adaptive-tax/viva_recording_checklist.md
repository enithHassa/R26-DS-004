# Viva recording checklist (Phase 4 Step 8)

Deliverable: a **screen recording** of the amendment adaptivity + report demo (not committed to git).

Use alongside [`docs/PHASES_RUNBOOK.md`](../../docs/PHASES_RUNBOOK.md) — **Adaptive Tax Phase 4 — Viva recording checklist**.

## Pre-flight

- [ ] Adaptive Tax running on `http://127.0.0.1:8005`
- [ ] API gateway on `http://127.0.0.1:8000`
- [ ] Frontend on `http://127.0.0.1:5173`
- [ ] Postgres reachable (`DATABASE_MODE` in `.env`)
- [ ] Chroma index present (`data/processed/adaptive-tax/chroma` or rebuild script)
- [ ] Neo4j Desktop up (optional; preferred for MODIFIES panel)
- [ ] Act PDF available **or** fixture extract + `--allow-stub-pdf` for API dry-run

## Dry-run

- [ ] `COMP_ADAPTIVE_TAX_EXPLAIN_MODE=fixture` on `:8005`
- [ ] `scripts/adaptive_tax_phase4_demo.py` (or manual reset → T1 → approve → T2) succeeds with T2 ≠ T1
- [ ] Open both report URLs from script output
- [ ] (Optional) Restart `:8005` with `EXPLAIN_MODE=openai` + `OPENAI_API_KEY`; confirm one report narrative

## Screen record (UI narrative)

- [ ] Recorder started
- [ ] Calculator: ex04 inputs → **T1** → View report (calc_id_1)
- [ ] Upload → extract → approve Act 02/2025 (Sec 52)
- [ ] Calculator: same inputs → **T2 ≠ T1** → View report (calc_id_2)
- [ ] Reports: expandable trace + legal evidence + rule_source (changed) + MODIFIES + narrative
- [ ] Recorder stopped; file saved off-repo

## After recording

- [ ] Note absolute path + date under **Recording path** in [`README.md`](README.md)
- [ ] Do **not** commit `.mp4` / `.mkv` / `.webm` into the monorepo
