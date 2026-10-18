# OE Engine — Cohen's kappa protocol

Validate **Optimization and Explainable Engine** relief recommendations against an independent expert (auditor / supervisor), separate from calculate accuracy tests.

## What kappa answers

> Does the OE Engine’s claim / do-not-claim advice agree with an expert beyond chance?

- **System:** OE interview suggest-claims or applied relief decisions  
- **Expert:** same cases labeled without seeing the system score

## Label scheme

| Label | Meaning |
|-------|---------|
| `claim` | Advise / apply this relief for the taxpayer YA |
| `do_not_claim` | Skip / do not apply |

Unit of agreement: `(profile_id, assessment_year, compare_group_id)`.

## Synthetic 40-taxpayer demo (no real PII)

Because real labeled expert data is not available yet, use the proxy set:

- **File:** `fixtures/kappa_40_taxpayers.csv`
- **40 taxpayers** × **4 relief decisions** = **160 pairs** for YA `2025_26`
- Disagreements are **patterned** (not random), e.g.:
  - film production claimed below the Act 5M minimum (system claims, expert rejects)
  - solar over-claim without invoice
  - cinema small outlay vs genuine new cinema
  - senior-citizen age eligibility mismatch
  - expert spotting a missed solar / donation claim

Regenerate:

```powershell
.\.venv-backend\Scripts\python.exe models/opt-explain-engine/evaluation/generate_kappa_40_taxpayers.py
```

Score:

```powershell
.\.venv-backend\Scripts\python.exe scripts/run_oe_engine_kappa.py `
  --csv models/opt-explain-engine/evaluation/fixtures/kappa_40_taxpayers.csv `
  --out-json reports/oe_engine_kappa.json
```

## Panel wording

> We validate OE Engine relief recommendations with Cohen’s kappa against independent expert claim decisions on the same (taxpayer, YA, relief) cases. With real expert labels unavailable for privacy reasons, we report κ on a synthetic 40-taxpayer proxy set that encodes known OE failure modes (e.g. film minimum spend), and we will replace it with auditor labels when available.

## Real expert labels later

Copy `fixtures/kappa_labels_template.csv`, fill `system_label` from OE and `expert_label` from an auditor, then re-run the same CLI.
