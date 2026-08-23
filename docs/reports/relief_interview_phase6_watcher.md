# Relief Interview — Phase 6 report (amendment watcher)

**Status:** delivered. Watcher script + immutability check run against a synthetic out-of-manifest PDF.
**Canonical plan:** [relief_interview_plan.md](relief_interview_plan.md).
**Date:** 2026-08-21

---

## 1. Goal

Future Acts must be able to propose catalog changes **without rewriting the past**.

That means:

1. Ingest a PDF that is **not** already in `corpus_manifest.json`.
2. Extract + verify → `proposed/{source_doc_id}.json`.
3. A human sets `proposed_for_assessment_year` → create **only** a new `approved/YYYY_YY.json` (and matching `rates/`).
4. Every previously live year-file hash stays unchanged.

Act 04/2023 (`ird-amend-2023-04`) is already in the Phase 4 extract corpus — it is **not** a watcher demo, and the CLI refuses it.

---

## 2. CLI

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase6_watcher.py <command>
```

| Command | Purpose |
|---|---|
| `status` / `list` / `show` | Inspect proposals |
| `refuse-corpus-docs` | List every PDF the watcher will reject |
| `make-demo-pdf` | Write the synthetic out-of-manifest demo PDF |
| `ingest --pdf PATH --source-doc-id ID` | Extract + verify → `proposed/` |
| `set-year --source-doc-id ID --ya YYYY_YY` | Human assigns a **new** assessment year |
| `promote --source-doc-id ID` | Create only that year's `approved/` + `rates/` |
| `check-immutable [--past-only]` | Assert sealed year-file hashes are intact |

Extraction reuses the Phase 4 Pass 1 / Pass 2 / quote-gate pipeline (loaded by path, not by editing `gpt_extract.py`). Promotion never opens past year files for write.

---

## 3. Hard refusals

The watcher rejects a PDF when any of these hold:

- `source_doc_id` is already in `corpus_manifest.json`
- file name matches a manifest `file_name`
- `source_doc_id` is in the Phase 4 extract corpus (including Act 04/2023)

Verified on ingest of `IR_Act_No._04_2023_E.pdf` / `ird-amend-2023-04`:

```
INGEST REFUSED - watcher only accepts PDFs outside the corpus.
  - source_doc_id 'ird-amend-2023-04' is already in corpus_manifest.json
  - already in the Phase 4 extract corpus
  - file name matches corpus_manifest entry
```

`set-year` / `promote` also refuse if `approved/{ya}.json` already has live entries — the watcher may only create a new year.

---

## 4. Demo run (synthetic fixture)

All ten PDFs under `data/raw/adaptive-tax/` are already in the manifest, so the demo uses a clearly marked synthetic Act:

- PDF: `models/adaptive-tax/relief-interview/watcher-demo/IR_Act_No_Watcher_Demo_2026_E.pdf`
- `source_doc_id`: `ird-amend-watcher-demo-2026`
- Content: adds Fifth Schedule item `(vi) Rs. 2,000,000` from 1 April 2026, plus a First Schedule rate table
- Banner text: **SYNTHETIC FIXTURE — NOT A REAL STATUTE**

### Pipeline

1. `make-demo-pdf` → fixture written outside the corpus.
2. `ingest` (Fifth + First Schedule only) → 3 included rows, ~$0.04, proposal written with `proposed_for_assessment_year: null`.
3. Diff vs `2025_26`: one **new** relief (2,000,000 cap).
4. `set-year --ya 2026_27`.
5. `promote` → wrote **only** `approved/2026_27.json` and `rates/2026_27.json`.

### Result

| YA | Personal relief cap | Source |
|---|---|---|
| 2024/25 | 1,200,000 | Amendment Act No. 45 of 2022 (unchanged) |
| 2025/26 | 1,800,000 | Amendment Act No. 02 of 2025 (unchanged) |
| **2026/27** | **2,000,000** | watcher demo proposal (new file) |

`2026_27` carries forward the other eight relief entries from `2025_26` and clones its rate bands with `needs_manual_verification: true`. Overlay values come only from quote-gated proposal rows — no hand-typed numbers.

---

## 5. Immutability check

Before ingest, the watcher freezes `content_sha256` for every live year file into:

`models/adaptive-tax/relief-interview/review/immutable_baseline.json`

After promote it re-checks that baseline. A failed check rolls back the new year files.

```
past year hashes unchanged (16 files checked)
check-immutable --past-only → PASS
```

The 16 files are `approved/` + `rates/` for 2018/19–2025/26. None were rewritten.

---

## 6. Files

| Path | Role |
|---|---|
| `scripts/relief_interview_phase6_watcher.py` | Watcher CLI |
| `models/adaptive-tax/relief-interview/proposed/ird-amend-watcher-demo-2026.json` | Proposal (not live until promote) |
| `models/adaptive-tax/relief-interview/watcher-demo/*.pdf` | Synthetic out-of-manifest demo PDF |
| `models/adaptive-tax/relief-interview/approved/2026_27.json` | New year only |
| `models/adaptive-tax/relief-interview/rates/2026_27.json` | New year only |
| `models/adaptive-tax/relief-interview/review/immutable_baseline.json` | Hash baseline for the immutability gate |

**Note:** `2026_27` is on disk for the immutability demo. The Relief Interview API still lists 2018/19–2025/26 only (Phase 3 router). Phase 7 can decide whether to discover years from the directory or keep the demo year out of the UI.

**Cost:** ~13 gpt-4o calls, ~$0.04 for the demo ingest.
