# Fifth Schedule ¶1 completion — Checkpoint notes

## Checkpoint 1 (staged)

Base Act (`ird-ira-2017-base`) after Pass 1 prompt fix:

| Row | Cap | source_doc_id | quote_ok_full_doc | included |
|---|---|---|---|---|
| (iia) individual charity | 75000 | ird-ira-2017-base | true | true |
| (iib) entity charity | 500000 | ird-ira-2017-base | true | true |
| 1(b)(i)–(x) each | uncapped | ird-ira-2017-base | true | true |

Contiguous (iia)/(iib) quotes confirmed (no mid-quote skip). 1(c) not extracted. Amending Acts: 2022-45 / 2026-11 paraphrase rows gate-failed (expected); no per-donee restatement with caps in-corpus.

### Entity binding product decision

- Engine distinct entity-donation component? **No.** Only `qp_approved_charitable` in [`qp_categories.py`](../../backend/comp-adaptive-tax/adaptive_tax_app/services/qp_categories.py) (individual Fifth Sch 1(a) ceiling).
- Stance chosen: **Placeholder (temporary)** — `binding: none` for `donations_approved_charitable_entity`. Interview collects the amount and shows an informational notice; calculate does not apply it. Follow-up: add an engine component if entity calc support is required.

## Checkpoint 2 (promoted)

| Metric | Expected | Actual |
|---|---|---|
| `approved/2018_19.json` entry_count | 19 (= 9 + 1 entity + 9 `qp_donee_*`) | **19** |
| Gap | 0 | **0** — no gap |

All nine `qp_donee_*` present on YA 2018/19–2025/26. `(iii)/(iv)` collapsed to one group `qp_donee_university_hei`. Verify: clean (184 entries, no drift).

Sec 52(4): `is_sec52_4_eligible` true only for `qp_government_sri_lanka` / `qp_government_fund` when `assessment_year == "2025_26"` — maps to donee groups (i) and (v). UI CF hint on those checklist rows for YA 2025/26.

Compare: optgroup + subsection table “¶1(b) listed public donees” required and implemented.
