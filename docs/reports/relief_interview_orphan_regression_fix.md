# Relief Interview — orphan regression fix

**Date:** 2026-08-21  
**Promotion run (fix):** `20260821T173232Z`  
**Phase 5 verify:** clean (184 promoted entries match staging)

---

## 1. Original four-group audit (solar / Samurdhi / merger / expenditure)

### BEFORE recovery

Cursor Local History and `git log --follow` on `approved/*.json` found **no** recoverable pre-re-extract snapshot. Those catalogs are **untracked** (see §6).

**BEFORE values could not be recovered.** Confirming that current AFTER values match prior documented findings is **not** the same claim as proving no intermediate change occurred.

### AFTER vs documented expected (substance check only)

| Group | Documented expectation | Live AFTER (post–para1 promote / re-approve) |
|---|---|---|
| `solar_panel_relief` | 600000 · Act 10 · from 2020-01-01 | Same · entry `9f5ed780d4a4` |
| `qp_samurdhi_shop` | uncapped · Act 10 · from 2021-04-01 | Same · `d996b18716da` |
| `qp_bank_merger` | uncapped · Act 10 · from 2021-04-01 | Same · `1bae78b25b59` |
| `expenditure_relief` | 1.2M Act 10 (2020/21–21/22); 900k Act 45 from 2022-04-01 with nine-month quote | Same · `1a03b7af47fb` / `14ffa05e6654`; Rule 1b derives Act 10 end at 2022-04-01 |

Expenditure UI status (TS `compareRowStatus` on live quotes): **Listed** for 2022/23; **Last known figure — not confirmed for this year** for 2023/24–2025/26.

---

## 2. Personal relief 2025/26 regression — discovery and fix

### Symptom

Known-table dry-run after Fifth Schedule re-extract:

| YA | Expected | Actual (broken) |
|---|---|---|
| … | … | … |
| 2025_26 | **1800000** | **1200000** (Act 45 open row) |

### Root cause

Fifth Schedule `--force` re-extract **rehashed staging row_ids**. Prior `personal_relief` ledger decisions for Act 02/2025 became **orphans**. The gate-passed 1.8M staging row `6d8491ce220f` stayed **pending**. Re-approvals for para1 donees restored solar/Samurdhi/merger/expenditure but **did not** re-approve the 1.8M personal row. Rule 1 kept the open Act 45 1.2M (`98233f85b58e`) into YA 2025/26.

### Fix applied

1. Approved `6d8491ce220f` → `personal_relief` (cap 1800000, from 2025-04-01, auto-applied notice).
2. Pre-promote dry-run **passed all 8 YAs** with only that approval (Rule 1b closes 1.2M at 2025-04-01).
3. Therefore rejected empty-cap Act 02 date-only rows `7258fc9ba4a8` and `2c70869e7be8` (not needed for the series).

### Final known-table dry-run (PASS)

| YA | Cap | Source |
|---|---|---|
| 2018_19 | 500000 | ird-ira-2017-base |
| 2019_20 | 500000 | ird-ira-2017-base |
| 2020_21 | 3000000 | ird-amend-2021-10 |
| 2021_22 | 3000000 | ird-amend-2021-10 |
| 2022_23 | 2250000 | ird-amend-2022-45 |
| 2023_24 | 1200000 | ird-amend-2022-45 |
| 2024_25 | 1200000 | ird-amend-2022-45 |
| 2025_26 | **1800000** | **ird-amend-2025-02** (`6d8491ce220f`) |

**FINAL_SERIES_PASS = True**

---

## 3. Comprehensive orphan / pending inventory

### Orphaned ledger (no staging) — left untouched per scope

| Status | Count | Notable groups |
|---|---|---|
| approved | 19 | Includes superseded solar/Samurdhi/merger/expenditure/charity/personal ids; plus 8 **ungrouped** approved (out of scope) |
| needs_manual_verification | 2 | solar (old) |
| rejected | 3 | **ungrouped** (out of scope) |

Ungrouped approved/rejected orphans were **not** pruned in this fix.

### Live pending cleared this fix

| Action | Rows |
|---|---|
| Approve | `6d8491ce220f` (1.8M personal) |
| Reject empty-cap Act 02 | `7258fc9ba4a8`, `2c70869e7be8` |
| Reject Act 45 donee fragments | `d6df8449b1d9` … `86b0c1efa7df` (10) — confirmed: gate-failed; empty cap; empty dates; quotes are labels only vs live base `qp_donee_*` |
| Reject Act 45 charity fragments | `62312fc69d0b` (same 75k, incomplete quote vs live iia); `ab6d4c6f567e` (non-digit fragment “cap”, not a new ceiling vs live iib 500000) |
| Reject other gate-fails | cinema `a788688dfb88`; Act 11 charity `55f3c932b985`/`66a023213967`; Act 45 expenditure close `c132678804ba` |

**Remaining live relief pending/blocked/NMV after fix: 0**

---

## 4. Promote / verify / hash note

- `promote --force` → run `20260821T173232Z`
- `verify` → no staging drift (184 entries)

**Byte hashes:** all `approved/{2018_19…2025_26}.json` and matching `rates/*.json` changed because promote rewrites `promotion_run` / `promoted_at` on every supported YA. `approved/2026_27.json` and `rates/2026_27.json` unchanged (outside promote set).

**Substance:** only YA **2025/26** `personal_relief` winner changed (1200000 → 1800000). Other YA personal winners unchanged (`d2db29edf77b` / `3035bcfe0fc7` / `503e7b27e490` / `98233f85b58e`).

---

## 5. Named follow-up (not done in this fix)

### ACTION: Track catalog JSON in git

`models/adaptive-tax/relief-interview/approved/*.json` and `rates/*.json` are **untracked** (not ignored by a JSON rule — simply never committed). That is why BEFORE recovery failed and why promote history is not a permanent audit trail.

**Own PR:** add these files to version control so every promote is a reviewable diff. Content-hash / `verify` only proves internal consistency at a moment in time, not historical correctness across promotes.

---

## 6. Closing checklist

- [x] 1.8M personal_relief approved and promoted  
- [x] Known-table dry-run PASS all 8 YAs  
- [x] Act 45 paraphrase rejects only after no-new-info confirmation  
- [x] Gate-failed leftovers rejected  
- [x] Ungrouped ledger orphans left alone  
- [x] Verify clean  
- [ ] Git-track `approved/` + `rates/` — **separate PR**  
