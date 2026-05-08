# Rules pack ↔ legal traceability (MVP)

This document links each numeric or rule row in [`models/tax-optimization/rules/it22064486_sl_tax_mvp.yaml`](../../models/tax-optimization/rules/it22064486_sl_tax_mvp.yaml) to **intended** Sri Lankan sources (Inland Revenue Act, amendments, APIT circulars, guides).  

**You (the author)** should replace generic notes with **exact** section numbers, Gazette numbers, and circular titles from your PDF library (e.g. IR Act No. 24 of 2017 and later amendment acts, 2024/25 APIT materials).  

**Status**

| Status | Meaning |
|--------|---------|
| **verified** | Cross-checked against an authoritative source you cite in the row. |
| **MVP assumption** | Encoded for research/MVP; not yet verified or intentionally simplified. |
| **deferred** | Behaviour noted in YAML but not fully implemented (formula, timing, etc.). |

---

## Traceability table

| yaml_path_or_rule_id | yaml_value_summary | legal_citation | status | notes |
|----------------------|-------------------|----------------|--------|-------|
| `thresholds.personal_relief_annual` | 1,200,000 LKR | *Author: cite personal relief threshold in IR Act / consolidated amendments and any APIT circular that restates the annual amount for the assessment year.* | MVP assumption | Must match year in force for `assessment_year` (pack label `2024_25`). |
| `thresholds.apit_slabs[0]` | Band width 500,000; rate 6% | *Author: cite APIT progressive schedule (first bracket) for individuals.* | MVP assumption | YAML uses **band width**, not cumulative thresholds; confirm statutory wording matches engine semantics. |
| `thresholds.apit_slabs[1]` | Band width 500,000; rate 18% | *Author: same schedule, second bracket.* | MVP assumption | |
| `thresholds.apit_slabs[2]` | Band width 500,000; rate 24% | *Author: same schedule, third bracket.* | MVP assumption | |
| `thresholds.apit_slabs[3]` | Band width 500,000; rate 30% | *Author: same schedule, fourth bracket.* | MVP assumption | |
| `thresholds.apit_slabs[4]` | Remainder; rate 36% | *Author: same schedule, top marginal rate / remainder band.* | MVP assumption | Code treats `upper: null` as taxing all remaining taxable income at this rate. |
| `thresholds.deductions.life_insurance_premium_cap_annual` | 100,000 LKR | *Author: APIT deduction schedule — life insurance (annual cap).* | MVP assumption | |
| `thresholds.deductions.health_insurance_premium_cap_annual` | 75,000 LKR | *Author: APIT deduction schedule — health insurance.* | MVP assumption | |
| `thresholds.deductions.home_loan_interest_cap_annual` | 600,000 LKR | *Author: housing loan interest relief / conditions in Act or circular.* | MVP assumption | |
| `thresholds.deductions.rent_relief_cap_annual` | 300,000 LKR | *Author: rent relief provisions (often subject to formula and eligibility).* | MVP assumption | Pack applies **cap only**; full formula deferred (see dedicated row below). |
| `thresholds.deductions.rent_relief_pct` | 0.25 (25%) | *Author: rent relief — percentage component of statutory formula.* | deferred | **Not applied** in MVP evaluator beyond cap; align when implementing full rent formula. |
| `thresholds.deductions.charitable_donations_cap_pct_of_taxable` | 0.33 (33%) | *Author: donations cap as % of taxable (or statutory income) basis.* | MVP assumption | Engine uses estimated taxable when set, else gross (see rule message text); confirm IR wording. |
| `thresholds.deductions.retirement_contribution_cap_pct_of_income` | 0.15 (15%) | *Author: approved pension / EPF-style limits for APIT.* | MVP assumption | Engine uses `min(% of gross, annual ceiling)`. |
| `thresholds.deductions.retirement_contribution_cap_annual` | 600,000 LKR | *Author: same regime, annual ceiling.* | MVP assumption | |
| *(deferred)* **Full rent relief formula** | *(not in YAML as executable formula)* | *Author: cite full rent relief test and calculation from Act/circulars.* | deferred | YAML and `deduction_cap` rule use **annual cap only**; `rent_relief_pct` reserved. |
| `it22064486_optb_year_001` | `tax_year_match` | *Product rule:* assessment year alignment with bundle. | MVP assumption | Not a statutory section; dissertation should state this is **rules-engine scoping**. |
| `it22064486_optb_unknown_relief_001` | `unknown_relief_code` | *Product rule:* claim codes must match allow-list. | MVP assumption | Mirrors policy of “only scheduled reliefs”; cite allow-list source in thesis. |
| `it22064486_optb_cap_life_ins_001` | `deduction_cap` / life | *Cross-ref:* same as `life_insurance_premium_cap_annual` row. | MVP assumption | |
| `it22064486_optb_cap_health_ins_001` | `deduction_cap` / health | *Cross-ref:* `health_insurance_premium_cap_annual`. | MVP assumption | |
| `it22064486_optb_cap_home_loan_001` | `deduction_cap` / home loan | *Cross-ref:* `home_loan_interest_cap_annual`. | MVP assumption | |
| `it22064486_optb_cap_rent_relief_001` | `deduction_cap` / rent | *Cross-ref:* `rent_relief_cap_annual`; full law deferred. | MVP assumption | |
| `it22064486_optb_cap_donations_001` | `charitable_donation_cap` | *Cross-ref:* `charitable_donations_cap_pct_of_taxable` and basis definition in Act/circular. | MVP assumption | |
| `it22064486_optb_cap_retirement_001` | `retirement_contribution_cap` | *Cross-ref:* `%` and annual cap fields. | MVP assumption | |

---

## Suggested PDFs (your workspace / library)

Map rows above to materials you already collected, for example:

- IR Act No. 24 of 2017 (as amended) — core income tax framework.
- Amendment / Gazette materials (e.g. 2021, 2023, 2025 packs) — updated rates, thresholds, reliefs.
- APIT / advance tax circulars for the assessment year — slabs, personal relief, deduction schedules.
- IR “Guide” publications — non-authoritative but useful cross-checks.

**Deliverable:** fill `legal_citation` and move mature rows from **MVP assumption** to **verified** only when you have a specific section, schedule, or circular paragraph reference.

---

## Related code

- Rules loader: [`backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_rules_loader.py`](../../backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_rules_loader.py)
- Compliance engine: [`backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_compliance_engine.py`](../../backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_compliance_engine.py)
- Tax computation (slabs): [`backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_tax_computation.py`](../../backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_tax_computation.py)
