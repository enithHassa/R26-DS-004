# Rule packs

YAML rule files consumed by the rules engine in Phase 3. The authoritative
Phase 1 deliverable here is `sl_tax_2024_25.yaml`, referenced by
`ComponentSettings.COMP_RECOMMENDATION_RULES_PATH`.

Each rule pack encodes:

- tax brackets and slab rates (from the Inland Revenue Act)
- relief and deduction strategies (with eligibility predicates)
- legal references for each strategy

Rule packs are versioned by filename (`sl_tax_YYYY_YY.yaml`) so past years
remain reproducible for backtesting.
