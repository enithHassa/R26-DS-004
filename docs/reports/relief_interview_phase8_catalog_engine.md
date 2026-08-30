# Relief Interview — Phase 8 report (catalog rate engine)

**Status:** delivered. Additive catalog engine serves tax for `2018_19`–`2023_24` from `rates/{ya}.json`. Existing `calculate()` remains authority for `2024_25` / `2025_26`.
**Canonical plan:** [relief_interview_plan.md](relief_interview_plan.md).
**Date:** 2026-08-21

---

## 1. Gate

Phase 4 `accuracy_result.json` has `gate_pass: true` (2024/25 and 2025/26 ladders match ontology packs). The catalog engine refuses to run if that flag is false.

---

## 2. What was added (nothing patched in `calculate()`)

| Piece | Path |
|---|---|
| Engine module | `backend/comp-adaptive-tax/adaptive_tax_app/services/catalog_rate_engine.py` |
| HTTP router | `backend/comp-adaptive-tax/adaptive_tax_app/routers/catalog_engine.py` |
| Registration | one `include_router` line in `main.py` |
| Frontend client | `calculateCatalogTax` in `frontend/.../api.ts` |
| Result UI | `relief-interview/result.tsx` — engine years → `calculate()`; others → catalog engine + badge |

`rule_engine.calculate` and its YA enum were **not** modified.

---

## 3. Behaviour

1. Sum session income heads (employment / business / investment / other).
2. Apply catalog personal relief (auto), then claimed solar / rent capped from `approved/{ya}.json`.
3. Apply progressive slabs from `rates/{ya}.json` (extractor bounds normalized to ontology-style exclusive lowers so shared boundaries like `500000`/`500000` become `500000`/`500001`).
4. Return tax plus expandable receipts (`act_name` / `section_ref` / `quote` / `source_doc_id`) for every relief and band slice used.
5. If `rates/{ya}.json` still has `needs_manual_verification: true`, the UI shows an open expandable badge: **“extracted from source, not independently verified”**. After a Phase 5 `clear-flag` + re-promote, the badge switches to “catalog rates spot-checked”.

Engine years (`2024_25`, `2025_26`) posted to `/catalog-engine/calculate` are **rejected** (422) with a pointer to `/calculate`.

---

## 4. Verification

Slab math on the accuracy-gated years (same taxable income, catalog ladder vs ontology pack `_allocate_slabs`):

| YA | Taxable | Catalog tax | Ontology tax | Match |
|---|---|---|---|---|
| 2024/25 | 3,800,000 | 918,000 | 918,000 | yes |
| 2025/26 | 3,200,000 | 672,000 | 672,000 | yes |

Sample live path: `2023_24`, employment 5,000,000 → personal relief 1,200,000 → taxable 3,800,000 → tax 918,000, badge shown, 7 provenance receipts.

HTTP:

- `GET /api/v1/catalog-engine/status` → gate passed, supported YAs listed
- `POST /api/v1/catalog-engine/calculate` with `2020_21` → 200 + tax figure
- Same with `2024_25` → 422 refuse

---

## 5. UI

On Result for a non-engine YA:

- Amber expandable badge with the required wording until rates are spot-checked
- Final tax / taxable / gross / personal relief summary
- Expandable **Provenance receipt** listing each relief and band with Act citation and quote

Engine-year Result path is unchanged (`calculate()` + `TaxpayerResultSummary`).

---

## 6. Honesty limits

This engine is a **simplified** catalog path (heads + personal / solar / rent + First Schedule slabs). It does not reproduce every `calculate()` provenance gate. That is intentional: older years get an Act-backed figure with a receipt, while 2024/25 and 2025/26 stay on the full authority engine.
