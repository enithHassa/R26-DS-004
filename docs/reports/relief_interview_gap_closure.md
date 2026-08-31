# Relief Interview — gap closure after Phases 0–8

**Date:** 2026-08-21  
**Promotion run:** `20260821T112914Z`  
**Phase 5 verify:** clean (104 promoted entries match staging)

## What changed

### Extractor (Phase 4)

- Fifth Schedule dual Pass-1 focuses (¶1 qualifying payments vs ¶2 reliefs).
- Schedule focus windows keep densest blocks under `MAX_STREAM_CHARS` (fixes TOC truncating the schedule body).
- Running-header strip accepts single-line Act titles; marginal notes (`Amendment of section … enactment`) stripped so Sec 52(4) quotes pass the substring gate.
- `MAX_SCHEDULE_WINDOWS` raised to 4.

### Human review + promote (Phase 5)

Approved (extractor-only, gate-passed):

| Group | Provenance | Notes |
|---|---|---|
| `donations_approved_charitable` | Base Act · cap 75,000 | Binding `qualifying_payments` |
| `qp_film_production` / `qp_cinema_upgrading` / `qp_samurdhi_shop` / `qp_bank_merger` | Act 10/2021 | `filing_line` → Calculator component ids |
| `expenditure_relief` | Act 10 1.2M (from 2020-01-01); Act 45 900k (from 2022-04-01) | Rule 1b closes 1.2M at Act 45 start |
| `solar_panel_relief` | Act 10 600k from 2020-01-01 | Restored after re-extract |
| `personal_relief` | Act 45 2.25M + 1.2M rows re-approved | YoY dry-run restored |
| Sec 52(4) CF | Act 11/2026 · rule | Lands in `rates/{ya}.json` `special_formulas` from YA 2025/26 |

Rejected: Act 10 500k personal restatement; Act 45 300k personal mid-window; empty-cap bank-merger restatement.

### UI / calculate mapping

- Reliefs page: “N questions for YA …”, “changed this YA” / changed-count chips.
- Changing as-of YA clears `reliefAnswers`.
- `build-calculate-request.ts` maps `qualifying_payments` / `donations` / `filing_line` answers (no longer hardcodes zeros).
- Result: Act-rules panel from `GET /relief-interview/rates/{ya}` (`special_formulas`, read-only).
- Approve CLI: `--binding qualifying_payments|donations|…` and `--component-id` for filing lines.

## YoY spot-check (post-promote)

| YA | personal_relief | expenditure_relief | charity donation |
|---|---|---|---|
| 2018/19–2019/20 | 500k (base) | — | 75k |
| 2020/21–2021/22 | 3M (Act 10) | 1.2M | 75k |
| 2022/23 | 2.25M (Act 45) | 900k (Act 45) | 75k |
| 2023/24–2024/25 | 1.2M (Act 45) | **Not available** (removed w.e.f. 1 Jan 2023) | 75k |
| 2025/26 | 1.8M (Act 02/2025) | **Not available** | 75k |

\*Earlier catalog Rule 1 kept Act 45’s 900k open after 2022/23 because the extract had no `effective_to`. IRD / Act 45 guidance: expenditure relief **Not applicable** for YA 2023/24 onward. Interview UI now hides ¶2(f) for YA ≥ 2023/24.

## Incoming Acts (human review — do not auto-promote)

```powershell
$env:PYTHONPATH = "$PWD"
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase6_watcher.py ingest --source-doc-id <id>
# → proposed/{id}.json

# Set proposed_for_assessment_year in the proposed file, then:
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase6_watcher.py promote --source-doc-id <id>

# Or Phase 5 path for corpus Acts already in the manifest:
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase4_extract.py --only-doc <id> --only-section "Fifth Schedule" --force
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase5_review.py list --kind relief --status pending
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase5_review.py --reviewer <you> approve <row_id> --compare-group-id <group> ...
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase5_review.py --reviewer <you> promote --force
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase5_review.py verify
```

Past `approved/*.json` / `rates/*.json` hashes stay immutable except via `promote --force` after review.

## Still out of scope / known gaps

- Full Fifth Schedule ¶1 category set (Government, university, listed funds, …) — base focus has text; Pass 1 still under-emits distinct category quotes beyond the 75k charity row.
- Act 45 expenditure `effective_to` for the nine-month YA 2022/23 bound (not invented).
- `rates/{ya}.json` still `needs_manual_verification: true` (Workstream D clear-flag not run).
- `special_formulas` are provenance-only on Result unless a per-rule engine binding exists.
- Calculator `calculate()` YA enum unchanged (`2024_25` / `2025_26` only).
