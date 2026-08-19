# Phase 6.9 viva figures (markdown export)

Generated from run `phase6_9_2026_08_11_101701` (2026-08-11T10:17:01.192659+00:00).

Use these blocks in Chapter 4 or paste screenshots from the Coverage UI.

## Figure 1 — Section-grain legal coverage bars

| Section | Covered | Bar | % |
|---------|---------|-----|---|
| Section 5 — Employment | 18/18 | `########################` | 100.0% |
| Section 6 — Business | 2/2 | `########################` | 100.0% |
| Section 7 — Investment | 15/15 | `########################` | 100.0% |
| Section 8 — Other income | 3/3 | `########################` | 100.0% |
| Section 52 — Qualifying payments & donations | 12/14 | `#####################---` | 85.7% |
| Section 89 — Tax credits | 1/1 | `########################` | 100.0% |
| First Schedule — Progressive rates | 1/1 | `########################` | 100.0% |
| Third Schedule — Personal relief | 1/1 | `########################` | 100.0% |

## Figure 2 — Catalog confidence distribution

| Tier | Count | % | Bar |
|------|-------|---|-----|
| high | 49 | 90.7% | `######################--` |
| medium | 5 | 9.3% | `##----------------------` |
| low | 0 | 0.0% | `------------------------` |
| pending | 0 | 0.0% | `------------------------` |

## Figure 3 — Unsupported rule queue (Act 11/2026 novelty demo)

**Queue size:** 2 pending handler(s)

_Act No. 11 of 2026 enables Sec 52(4) carry-forward (qp_brought_forward, supported). Unsupported queue holds rules awaiting handlers (e.g. qp_bank_merger)._

**Supported (Act No. 11 of 2026):**
- `qp_brought_forward` — Qualifying Payment Brought Forward (Sec 52(4)) (`ird-amend-2026-11`, supported)

**Unsupported (awaiting handler):**
- `relief_fifth_sch_2f_expenditure` — Section 52 — Fifth Schedule 2(f) Expenditure Relief (Sunset) — **Pending**
- `qp_bank_merger` — Section 52 — Financial Institution Merger Acquisition Cost (Fifth Sch 1(e)) — **Pending**

## Figure 4 — Version strip screenshot checklist

- [ ] Calculator result: Calculated Using strip visible
- [ ] Report page: sticky Calculated Using strip
- [ ] Strip shows act_version_label + catalog_version + rule_pack_version
- [ ] YA switch changes rule_pack_version label

**YA 2024/25 stamps:**
- `act_version`: ird-consolidated-2025
- `act_version_label`: 2025 Consolidated
- `catalog_version`: v1
- `rule_pack_version`: 2024_25.current
- `knowledge_graph_version`: v5-calc-ontology
- `extraction_version`: bootstrap-other-income-catalog-v1

**YA 2025/26 stamps:**
- `act_version`: ird-consolidated-2025
- `act_version_label`: 2025 Consolidated
- `catalog_version`: v1
- `rule_pack_version`: 2025_26.current
- `knowledge_graph_version`: v5-calc-ontology
- `extraction_version`: bootstrap-other-income-catalog-v1
