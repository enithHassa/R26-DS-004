# Relief Interview — Phase 5 report (human review and promotion)

**Status:** delivered. All eight years now carry live `approved/` and `rates/` files.
**Canonical plan:** [relief_interview_plan.md](relief_interview_plan.md).
**Date:** 2026-08-21

---

## 1. What Phase 5 had to guarantee

Phase 4 produced staging rows; Phase 5 decides which of them become live catalog
content. The plan's constraint is that a reviewer may **copy** an extractor row
but may never **type** a cap or a rate read off a PDF. Wrong or missing values
must be fixed by re-running Phase 4 on that provision.

That constraint is enforced by the code, not by discipline. The review CLI
(`scripts/relief_interview_phase5_review.py`) splits every field into two sets:

| Reviewer may set | Copied verbatim from staging |
|---|---|
| `compare_group_id`, `display_name`, `question_prompt`, `sort_order`, `input_kind`, `auto_applied`, `engine_binding` | `cap_amount`, `unit`, `effective_from`, `lower`, `upper`, `rate_percent`, `value`, `section_ref`, `quote`, `source_doc_id` |

There is no CLI flag, and no code path in promotion, that writes a value from
anywhere but a staging row. `verify` re-checks this after the fact.

The one deliberate exception is `act_name`, explained in §5.

---

## 2. The CLI

```powershell
$env:PYTHONPATH = "backend/comp-adaptive-tax;$PWD"
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase5_review.py <command>
```

| Command | Purpose |
|---|---|
| `status` | Counts by decision state; warns about orphaned decisions |
| `list [--kind --status --doc --section --orphans]` | Staging rows with their decision |
| `show <row_id>` | One row in full, with gate verdicts and provenance |
| `groups` | How reliefs currently line up across Acts |
| `approve <row_id>...` | Approve, optionally setting presentation metadata |
| `reject <row_id>... --reason` | Reject |
| `flag <row_id>... --reason` | Mark `needs_manual_verification` |
| `clear-flag --ya <ya> --note` | Record a human spot-check of that year's rates |
| `prune` | Archive decisions whose staging row a re-extraction replaced |
| `promote [--dry-run] [--force]` | Rebuild all year files from the ledger |
| `verify` | Audit promoted files against staging and the ledger |

Decisions live in `models/adaptive-tax/relief-interview/review/decisions.json`.
Promotion is a pure function of that ledger plus staging, so the year files can
always be regenerated and never need hand-editing.

**Row ids.** A row's id is a hash of its source document, section, kind, values
and normalised quote. Re-extracting a provision keeps ids for rows whose text is
unchanged and mints new ones where it changed, so a decision can never silently
carry over to a different quote. Decisions left behind by a re-extraction are
reported by `status` and archived by `prune` (the audit trail is kept under
`superseded_decisions`).

---

## 3. Gaps found during review, and how they were closed

Review immediately exposed that the two headline demo values were not in the
catalogs. Per the plan, none of them were typed in — each was recovered by
re-running Phase 4 on the affected provision after fixing the cause.

**Personal relief 1.2M and 1.8M were missing.** Both amounts were inside their
focus windows, so this was a Pass 1 recall failure rather than a windowing one.
An amending Act states a relief change as a bare amount and a date with the word
"relief" nowhere nearby — `"(v) Rs. 1,800,000, for each year of assessment
commencing on or after April 1, 2025"` — and the model was not treating that as
a relief. The Pass 1 prompt now names that pattern explicitly and requires one
row per item in a restated list, each with its own `effective_from`. That
recovered the full personal-relief history in one pass.

**Five of Act 10/2021's rate bands failed the quote gate.** All five failed the
same way: the model prefixed the table's column header to each body row, and
since one header sat above many rows, only the first band's header-prefixed
quote was contiguous. Instructing the model not to do it did not work. The fix
was structural — the table renderer now prints each body row under its own copy
of the header, so quoting the header together with one row is a genuine
contiguous substring of that table. Act 10/2021's First Schedule went from 3 of
9 rows included to 9 of 9, which is what gave 2020/21 and 2021/22 a correct rate
ladder instead of falling back to the 2017 ladder.

After both fixes the whole corpus was re-extracted so every row comes from one
pipeline version. The Phase 4 accuracy gate still **passes**: 2024/25 and
2025/26 reproduce their ontology packs, and all five discovered ladders are now
complete (previously three of five).

---

## 4. Decisions taken

92 staging rows: **79 approved**, **1 flagged**, **2 rejected**, **10 blocked by
the Phase 4 quote gate** (never eligible for approval).

**Reliefs.** The reviewer's substantive job was assigning a canonical
`compare_group_id`, because the extractor numbers groups per section — personal
relief was group `4` in the base Act and group `1` in two amending Acts, so
nothing lined up across years. Nine canonical groups were assigned.

Rejections, with reasons recorded in the ledger:

- Act 45/2022's restatement of the pre-2020 500,000 baseline — the base Act
  already carries that value, and keeping both puts two rows on one effective date.
- Act 2/2025's personal relief amendment as captured a second time under the
  First Schedule — a duplicate that cites the wrong schedule.

Flagged `needs_manual_verification`: solar panel relief (Act 10/2021). Its
600,000 cap is quoted correctly, but its effective date is inferred from sibling
items in the same amendment rather than stated in the quote. It stays visible in
the interview with a badge, as the plan requires.

**Rates and rules.** All gate-passed bands and rules were approved. Promotion
decides what each year actually uses: it groups bands into ladders by source Act
and effective date, keeps only ladders that start at zero, have no gaps and end
open-ended, and gives each year the latest ladder effective on or before 1 April
of that year.

---

## 5. One deliberate override: `act_name`

Asked to name the Act, the model answered "Inland Revenue Act, No. 24 of 2017"
for rows from six of the seven PDFs, because an amending Act's text is written
in terms of the principal enactment it amends. Left alone, the UI receipt for
the 1.8M relief would have credited the 2017 Act.

Promotion therefore sets `act_name` from the corpus manifest title for the PDF
that was actually read — document identity that Phase 1 already confirmed
against disk — and keeps the model's answer as `provenance.act_name_extracted`.
No tax value is affected; `section_ref`, `quote` and `source_doc_id` remain
exactly as extracted.

---

## 6. Result

### Personal relief across the confirmed years

| YA | Cap (LKR) | Source Act | Effective from |
|---|---|---|---|
| 2018/19 | 500,000 | Act No. 24 of 2017 | undated baseline |
| 2019/20 | 500,000 | Act No. 24 of 2017 | undated baseline |
| 2020/21 | 3,000,000 | Amendment Act No. 45 of 2022 | 2020-01-01 |
| 2021/22 | 3,000,000 | Amendment Act No. 45 of 2022 | 2020-01-01 |
| 2022/23 | 2,250,000 | Amendment Act No. 45 of 2022 | 2022-04-01 |
| 2023/24 | 1,200,000 | Amendment Act No. 45 of 2022 | 2023-04-01 |
| 2024/25 | 1,200,000 | Amendment Act No. 45 of 2022 | 2023-04-01 |
| 2025/26 | 1,800,000 | Amendment Act No. 02 of 2025 | 2025-04-01 |

This is the plan's viva pair — 1.2M against 1.8M on the same facts — reproduced
from Act text alone with a quote behind every number.

### Per-year catalogs

| YA | Relief entries | Rate bands | Rules | Ladder source | Rates flagged |
|---|---|---|---|---|---|
| 2018/19 | 8 | 6 | 15 | Act No. 24 of 2017 | yes |
| 2019/20 | 8 | 6 | 15 | Act No. 24 of 2017 | yes |
| 2020/21 | 9 | 3 | 15 | Amendment Act No. 10 of 2021 | yes |
| 2021/22 | 9 | 3 | 21 | Amendment Act No. 10 of 2021 | yes |
| 2022/23 | 9 | 3 | 23 | Amendment Act No. 45 of 2022 | yes |
| 2023/24 | 9 | 6 | 25 | Amendment Act No. 45 of 2022 | yes |
| 2024/25 | 9 | 6 | 28 | Amendment Act No. 45 of 2022 | yes |
| 2025/26 | 9 | 5 | 28 | Amendment Act No. 02 of 2025 | yes |

2018/19 and 2019/20 have eight entries rather than nine because solar panel
relief does not exist before 2020 — a real year-over-year difference the
interview can show, not a gap.

### Rates remain flagged

Every `rates/{ya}.json` carries `needs_manual_verification: true`. The Phase 4
accuracy gate is a machine check against ontology packs, not the human
spot-check the plan asks for, so it does not clear the flag. To clear a year
after checking it against the Act:

```powershell
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase5_review.py `
  clear-flag --ya 2024_25 --note "spot-checked all six bands against Act 45/2022 First Schedule"
.\.venv-backend\Scripts\python.exe scripts/relief_interview_phase5_review.py promote --force
```

---

## 7. Immutability

Each promoted file carries a `content_sha256` over its own contents. `verify`
recomputes it, and `promote` refuses to overwrite a file whose hash no longer
matches — a hand edit is detected rather than silently replaced. Confirmed:
all 16 files hash-consistent, and an edited copy fails the check.

`verify` also re-reads every promoted entry back to its staging row and compares
`cap_amount`, `section_ref`, `quote` and `source_doc_id`. Current result:

```
promoted entries checked against staging: 70
no drift: every promoted value, quote and citation matches its staging row
```

---

## 8. Known gaps

- **Fifth Schedule paragraph 1 qualifying-payment categories** (donation caps)
  are not in the catalogs. The base Act's Fifth Schedule window is being read for
  paragraph 2 reliefs; three re-extraction attempts did not recover paragraph 1.
  Missing stays missing.
- **Expenditure relief of 1,200,000** (Act 10/2021, health and vocational
  expenditure — distinct from personal relief) remains blocked by the quote gate
  across three re-extractions. It is visible in staging as blocked and was never
  promoted.
- **10 staging rows are gate-blocked** overall and are structurally ineligible
  for approval; `approve` refuses them and prints the re-extract command.
- **Rules are carried as `special_formulas`** with full provenance but are not
  yet interpreted; the Phase 8 engine will decide which of them bind.

---

## 9. Files

| Path | Contents |
|---|---|
| `scripts/relief_interview_phase5_review.py` | Review and promotion CLI |
| `models/adaptive-tax/relief-interview/review/decisions.json` | Decision ledger, promotion history, superseded decisions |
| `models/adaptive-tax/relief-interview/approved/{ya}.json` | 8 live relief catalogs |
| `models/adaptive-tax/relief-interview/rates/{ya}.json` | 8 live rate files |
| `models/adaptive-tax/relief-interview/extracted/*__*.json` | Phase 4 staging (unchanged by promotion) |

API check: `GET /api/v1/relief-interview/approved` returns all eight years with
`phase1_empty_skeleton: false` and non-empty entries.

**Cost.** Phase 5 re-extraction used 165 additional gpt-4o calls, roughly $1.15,
across the targeted fixes and two full corpus re-runs.
