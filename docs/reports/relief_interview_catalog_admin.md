# Relief Interview — catalog-admin report (Add New Act)

**Status:** delivered. Gated admin upload → hash-first duplicate check → Phase 4 extract → `harvest_act` on this PDF only → `proposed/` stage → human review → UPDATE or NEW YEAR promote, with Step 8 immutability.
**Canonical plan:** Add New Act Admin (`add_new_act_admin_dccd3947.plan.md`).
**Date:** 2026-08-23

This is **not** taxpayer Relief Interview, and it is **not** `/adaptive-tax/admin/upload` (GPT rules → Neo4j/params). Taxpayer Result dual cards, interview Report, `build-calculate-request.ts`, and `buildCatalogEngineRequestFromSession` were not taught about this flow.

---

## 1. Goal

A reviewer can add a new Inland Revenue Act PDF to the interview catalog **without rewriting the past**.

That means:

1. Token + reviewer name gate the UI and every mutating call.
2. Cheap text-hash identity check against the corpus and complete `proposed/` (failed jobs stay retryable).
3. Extract + quote-gate, then Phase 1 `harvest_act` on **this PDF only** (never Phase 1 `main()`, never overwrite `harvest/commencement_records.json`).
4. Stage `proposed/{source_doc_id}.json` only after a complete successful run.
5. A human classifies UPDATE vs NEW_YEAR, binds engine effects, and approves quote-gated rows.
6. Promote writes **only** touched year files through Phase 5 `_write_year_file` with a matching `content_sha256`. Untouched years are not opened for write. `corpus_manifest.json` is never rewritten.

---

## 2. How to run

Catalog-admin is served by Adaptive Tax (Component 5). Use a dedicated port if `:8002` is taken (local work used `:8006`). Do **not** use `--reload` while iterating on `step` — it often sticks on an old process.

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
$env:COMP_ADAPTIVE_TAX_CATALOG_ADMIN_TOKEN = "local-catalog-admin"
.\.venv-backend\Scripts\python.exe -m uvicorn adaptive_tax_app.main:app `
  --app-dir backend/comp-adaptive-tax --host 127.0.0.1 --port 8006
```

Frontend (Vite already proxies `/api/v1/adaptive-tax/**`; catalog-admin is mounted on the same Component 5 app at `/api/v1/catalog-admin`):

- Queue: http://127.0.0.1:5173/adaptive-tax/catalog-admin
- Upload: http://127.0.0.1:5173/adaptive-tax/catalog-admin/upload
- Review: http://127.0.0.1:5173/adaptive-tax/catalog-admin/review/{sourceDocId}

Empty token → API refuses to serve (`503`). Wrong/missing token → `401`. Mutating calls without `X-Catalog-Admin-Reviewer` (or a blank name) → `400`. The reviewer header is a name for the Phase 5 ledger, not a second password.

---

## 3. HTTP surface

Prefix `/api/v1/catalog-admin` on Component 5. All routes are token-gated; mutating ones also require the reviewer header.

| Method | Path | Role |
|---|---|---|
| GET | `/session` | Token check |
| POST | `/session/check` | Token + reviewer |
| POST | `/upload` | Store PDF + Step 2 duplicate check only |
| POST | `/jobs/{id}/extract` | Background extract + harvest + stage |
| GET | `/jobs/{id}` | Job status |
| POST | `/jobs/{id}/retry` | Retry a failed extract |
| DELETE | `/jobs/{id}` | Delete a failed/discarded job |
| GET | `/queue` | Pending proposals + failed jobs |
| GET | `/proposed/{source_doc_id}` | Review payload |
| POST | `/proposed/{id}/classification` | Human UPDATE / NEW_YEAR |
| POST | `/proposed/{id}/rows/{row_id}/approve\|reject` | Phase 5 `_record` wrapper |
| POST | `/proposed/{id}/confirm-new-year` | Hard-stop before creating a new YA file |
| POST | `/proposed/{id}/promote-preview` | Write-set + frozen-set + gap-ack |
| POST | `/proposed/{id}/promote` | 7a UPDATE |
| POST | `/proposed/{id}/promote-new-year` | 7b NEW YEAR (after confirm) |

Phase 1/4/5/6 are loaded with the same `importlib` pattern as the watcher. Pass 1/2 are **not** copied into `services/extraction.py` (that file belongs to the other amendment pipeline).

---

## 4. Pipeline

1. **Sign-in** — shared token in `sessionStorage` plus a reviewer name. Layout: `CatalogAdminLayout` under `/adaptive-tax/catalog-admin/*`.
2. **Upload** — PDF bytes stored; `read_act_text` + `text_sha256` vs corpus hash index and complete `proposed/`. Filename fallback. Act No/year parse. Same Act number + different hash pauses for treat-as-new (mints a new `source_doc_id`) or cancel. Never auto-supersedes; never rewrites `corpus_manifest.json`.
3. **Extract** — `extract_proposal` (full quote gate) on a background job. Statuses: `uploaded` / `extracting` / `extracted` / `failed` / `discarded`. Failed extract leaves **no** `proposed/` file. Failed jobs are excluded from pending-duplicate and remain retryable.
4. **Classify** — `harvest_act(pdf)` on this file only, then `ya_for_operation_date`. Suggestions are never a selected decision; humans set `kind_human`. Mixed commencement dates produce per-row suggestions, not one PDF-wide label.
5. **Stage** — `proposed/{id}.json` only after extract+harvest both complete.
6. **Review** — Phase 5 approve/reject (gate-fail cannot approve). Engine binding is unset until chosen: `WILL reduce calculated tax` vs `visible but will NOT affect tax` (`kind: none`). NEW_YEAR rate rows need the sole-check control, not routine Approve. Gap-ack fingerprint resets when bindings change.
7a. **UPDATE promote** — `select_for_year` union; `personal_relief` known-table can block; every other touched group shows the gap banner. Writes only changed year files. `cmd_promote` (Phase 5 or 6) is **not** called.
7b. **NEW YEAR** — confirm copy: *This Act's commencement suggests YA {new_year} — confirm before creating a new year file.* Then `write_empty_skeletons` (immediately sealed), Phase 6 `cmd_set_year`, Phase 6 `cmd_promote`, reseal the new YA through `_write_year_file`, optional rate overlay. Taxpayer `SUPPORTED_YAS` / `CATALOG_YAS` / year picker are **not** auto-extended.

---

## 5. Step 8 — Immutability

No catalog-admin write path skips `content_sha256`.

| Rule | How it is kept |
|---|---|
| Every year-file write goes through `_write_year_file` | Wrapper in `catalog_promote.py` always stamps `content_sha256` then calls Phase 5 `_write_year_file`. Skeletons from `write_empty_skeletons` and the new YA from Phase 6 `cmd_promote` (`write_text`) are resealed immediately. |
| Promote starts and ends with Phase 6 snapshot/assert | `snapshot_year_hashes` / `assert_past_years_unchanged` on the frozen set. If live `approved/*.json` already have stale seals, the Phase 6 call `SystemExit`s and catalog-admin falls back to whole-file hashes so a rates-only UPDATE is not blocked. Frozen live years are **not** resealed. |
| `cmd_verify` is post-hoc | After a successful write set, seals are re-checked and Phase 5 `cmd_verify` is run. Promote fails only on hash-mismatch lines for **written** files (staging-row noise on overlays is ignored). |
| Untouched years are not opened for write | Preview publishes `year_files_that_would_be_written` vs `year_files_frozen`. Promote writes only the former. Tests assert frozen byte hashes are unchanged and `_write_year_file` is never called on a frozen path. |

Work-dir tests copy live `approved/` + `rates/` then reseal **in the copy** so Phase 6 snapshot/assert can run for real. Production still refuses to rewrite live frozen hashes.

---

## 6. Hard refusals (unchanged)

- Never rewrite `corpus_manifest.json`; never auto-supersede
- Treat-as-new mints a different `source_doc_id`
- Do not call Phase 1 `main()` or overwrite `harvest/commencement_records.json`
- Attribution fields must not overwrite each other
- Do not edit taxpayer `result.tsx`, interview Report, `catalog_rate_engine.py`, or `calculate()`
- Do not auto-extend `SUPPORTED_YAS`, `CATALOG_YAS`, or the interview year picker
- Do not invent known-tables for non-`personal_relief` groups
- Do not fork Phase 5 approve; blank reviewer is rejected
- Gate-fail rows cannot be approved
- NEW_YEAR rates cannot look like routine approvals

---

## 7. Files

| Path | Role |
|---|---|
| `backend/comp-adaptive-tax/adaptive_tax_app/routers/catalog_admin.py` | Token/reviewer gate + HTTP |
| `.../services/catalog_admin_store.py` | Jobs, work-dir, proposed paths |
| `.../services/catalog_duplicate.py` | Hash-first identity |
| `.../services/catalog_extract.py` | Background extract; no partial `proposed/` |
| `.../services/catalog_classify.py` | `harvest_act` on this PDF |
| `.../services/catalog_stage.py` | `proposed/` only after success |
| `.../services/catalog_review.py` | Phase 5 wrapper, preview, gap-ack |
| `.../services/catalog_promote.py` | 7a UPDATE, 7b NEW YEAR, Step 8 seals |
| `frontend/src/features/adaptive-tax/pages/catalog-admin/` | Queue, upload, job, review + layout |
| `backend/comp-adaptive-tax/tests/test_catalog_admin_*.py` | Auth, duplicate, extract, classify, stage, review, 7a, 7b |

---

## 8. Tests (plan list)

| Requirement | Where |
|---|---|
| Duplicate short-circuit (corpus hash, proposed hash, failed-job still retryable, Act-No mismatch-hash) | `test_catalog_admin_duplicate.py` |
| Classification suggestions from mixed dates | `test_catalog_admin_classify.py` |
| promote-preview hash drift on untouched years | `test_promote_preview_frozen_years_do_not_drift` |
| Gate-fail cannot approve | `test_gate_fail_cannot_approve` |
| Empty token → 401/503 | `test_catalog_admin_auth.py` |
| Blank reviewer on approve → 400 | `test_approve_blank_reviewer_is_400` |
| `harvest_act` on a single fixture PDF (no manifest sibling) | `test_harvest_act_on_lone_pdf_without_manifest_sibling` |
| Failed extract leaves no `proposed/` file | `test_extract_failure_writes_no_proposal` |

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe -m pytest backend/comp-adaptive-tax/tests/test_catalog_admin_*.py -q --tb=short
```
