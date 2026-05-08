# Research architecture: declarative Sri Lankan tax rule engine (Component B)

This document evolves the MVP toward a **modular, explainable, versioned** YAML rule system **without breaking** [`it22064486_sl_tax_mvp.yaml`](../../models/tax-optimization/rules/it22064486_sl_tax_mvp.yaml). Strategy: **pack manifests + schema versioning + adapter layer** so `evaluate_compliance` keeps consuming a stable `TaxOptBRulePack` while new YAML features roll in.

**External law PDFs** (store locally; cite by id in YAML): map each rule’s `law_reference.citation_key` to your library, e.g. `IR_Act_10_2021_E`, `IR_Act_04_2023_E`, `IR_Act_45_2022_E`, `IR_Act_02_2025_E`, `IR_Act_24_2017_E`, `IR_Act_14_2023_E`, `IRA_Consolidated_2025_Changes`, `IR_Guide_Inland_Revenue_Act`. Do not commit large PDFs to git; keep paths in a local `research/law-library/manifest.json` if needed.

---

## PART 1 — Recommended folder structure

Target root: `models/tax-optimization/`

```text
models/tax-optimization/
├── README.md                          # How packs are built, assessed_year, env vars
├── rules/
│   ├── packs/                         # Composable “distributions” (what the API loads)
│   │   ├── mvp/
│   │   │   └── pack.manifest.yaml     # Points at core + year slice + no optional modules
│   │   └── research-dev/
│   │       └── pack.manifest.yaml
│   ├── core/                          # Cross-year invariants (currency, schema ids)
│   │   └── schema_profile_v1.yaml     # Optional: global defaults (not evaluator logic)
│   ├── years/                         # Assessment-year slices (thresholds, slabs for that year)
│   │   ├── 2024_25/
│   │   │   ├── thresholds.yaml
│   │   │   ├── slabs.yaml
│   │   │   └── relief_caps.yaml
│   │   └── 2025_26/                   # Future; empty or stub until researched
│   │       └── ...
│   ├── rules/                         # Declarative rule bodies (by category)
│   │   ├── meta/
│   │   │   ├── tax_year_match.yaml
│   │   │   └── unknown_relief_code.yaml
│   │   ├── deductions/
│   │   │   ├── life_insurance_cap.yaml
│   │   │   └── ...
│   │   ├── exemptions/               # Reserved for future Act provisions
│   │   └── optimization_hints/       # Non-normative hints for presets / ranking (optional)
│   ├── optimization/                 # Strategy templates (max relief, conservative, compare presets)
│   │   └── presets_mvp.yaml
│   ├── explainability/               # Template ids + metadata referenced by FR5 / future engine
│   │   └── templates_index.yaml
│   ├── schemas/                      # JSON Schema or custom schema docs for YAML authors
│   │   ├── rule_record_v2.schema.json
│   │   └── pack_manifest_v1.schema.json
│   ├── validators/                   # Optional: policy checks (lint) separate from runtime
│   │   └── README.md
│   ├── examples/                     # Authoring examples, not loaded in prod
│   │   └── example_rule_v2.yaml
│   └── legacy/                       # Frozen MVP single-file packs (backward compat)
│       └── it22064486_sl_tax_mvp.yaml   # Current file can MOVE here OR stay at rules root via symlink
├── scripts/                          # Optional: `build_pack.py` merges layouts into one dict for loader
└── _archive/                         # Deprecated assessment years (optional)
```

**MVP compatibility (incremental step 0):** keep the existing file where `COMP_OPTIMIZATION_RULES_PATH` points today. **Step 1** adds `pack.manifest.yaml` that *either* embeds the same content or uses `includes: [legacy/it22064486_sl_tax_mvp.yaml]`. The loader detects `schema_version` / top-level keys and normalizes to `TaxOptBRulePack`.

---

## PART 2 — Scalable YAML rule design

### 2.1 Pack manifest (composition + versioning)

```yaml
# models/tax-optimization/rules/packs/mvp/pack.manifest.yaml
pack_id: sl_tax_mvp_2024_25
schema_version: "2"                    # manifest schema; runtime may still emit v1 RulePack until adapter upgraded
assessment_year: "2024_25"
currency: LKR
effective_from: "2024-04-01"         # ISO; optional for research cuts
effective_to: null                    # null = open-ended
deprecated: false
replaces_pack_id: null

includes:
  - path: ../../years/2024_25/thresholds.yaml
  - path: ../../years/2024_25/slabs.yaml
  - path: ../../rules/deductions/life_insurance_cap.yaml
  # ... or, during migration:
  # - path: ../../legacy/it22064486_sl_tax_mvp.yaml

sources:
  - act_id: IR_Act_10_2021_E
    note: "Primary Act slice for personal relief / schedule alignment (verify)."
```

### 2.2 Rule record v2 (rich metadata; evaluator uses a **core subset**)

Fields you asked for map naturally to optional blocks. **Do not require all keys for MVP adaptation** — use defaults.

```yaml
# models/tax-optimization/rules/rules/deductions/example_life_insurance_v2.yaml
rules:
  - id: it22064486_optb_cap_life_ins_001          # stable id (audit)
    name: "Life insurance premium annual cap"
    category: "deduction"
    subcategory: "insurance"
    description: "Annual life insurance premium claimed must not exceed the statutory cap."
    law_reference:
      citation_key: IR_Act_14_2023_E              # maps to your PDF library index
      section_hint: "Schedule / APIT deductions (research — fill from statute)"
    effective_from: "2024-04-01"
    effective_to: null
    priority: 100                               # lower = earlier in narrative sort; tie-break only
    dependencies: []                            # rule ids that must pass first (future)
    deprecated: false

    # What the current engine already understands:
    evaluator:
      engine: component_b_v1                      # dispatches to existing rule_type
      type: deduction_cap
      relief_code: life_insurance_premium
      cap_field: life_insurance_premium_cap_annual
      message: "Life insurance premium claimed exceeds the MVP annual cap."

    # Eligibility (future): expression DSL or structured predicates
    eligibility: null

    # Validation (lint-time): e.g. cap_field must exist in thresholds
    validation:
      requires_threshold_keys: [life_insurance_premium_cap_annual]

    optimization:
      preset_tags: [max_relief, statutory_cap]
      rank_weight: 1.0

    explainability:
      template_id: cap_exceeded_v1
      on_pass_summary: "Within the annual limit for {label}."
      on_fail_summary: "Claimed LKR {claimed} exceeds cap LKR {cap} for {label}."
      trace_fields: [rule_id, relief_code, cap_field]

    frontend:
      relief_code: life_insurance_premium
      label_en: "Life insurance premiums"
      form_section: "deductions"
```

### 2.3 Example: tax slabs (thresholds slice)

```yaml
# models/tax-optimization/rules/years/2024_25/slabs.yaml
apit_slabs:
  - upper: 500_000
    rate: 0.06
    law_reference: { citation_key: IR_Guide_Inland_Revenue_Act, section_hint: "Progressive APIT bands (verify)" }
  - upper: null
    rate: 0.36
```

### 2.4 Example: relief / deduction (same as today + metadata)

Reuse current `charitable_donation_cap` / `retirement_contribution_cap` shapes under `evaluator:` with `type` mirroring existing `rule_type` strings.

### 2.5 Example: “exemption” (placeholder for future Act rules)

```yaml
rules:
  - id: ex_sample_reserved_001
    name: "Reserved exemption slot"
    category: "exemption"
    evaluator:
      engine: component_b_v1
      type: not_implemented
    explainability:
      template_id: reserved_v1
```

### 2.6 Example: validation-only rule (lint)

```yaml
rules:
  - id: lint_thresholds_keys_001
    category: "validation"
    evaluator:
      engine: lint_only
      type: thresholds_key_set
      must_define: [personal_relief_annual]
```

---

## PART 3 — Python architecture (clean, incremental)

Keep **three layers**:

| Layer | Responsibility | Modules (suggested) |
|--------|----------------|---------------------|
| **I/O & normalization** | Read manifest / merged YAML → canonical dict | `tax_opt_b_pack_io.py`, `tax_opt_b_pack_merge.py` |
| **Validation** | Structural schema + policy lint | `tax_opt_b_rules_schema_validate.py`, `tax_opt_b_rules_policy_lint.py` |
| **Runtime model** | Immutable `TaxOptBRulePack` + dispatch | Existing [`tax_opt_b_rules_loader.py`](../../backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_rules_loader.py), [`tax_opt_b_compliance_engine.py`](../../backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_compliance_engine.py) |

**Suggested new types (research-facing):**

```text
backend/comp-tax-optimization/tax_opt_b_app/
├── rules/
│   ├── __init__.py
│   ├── manifest.py           # PackManifest dataclass; resolve includes
│   ├── merge.py              # Deep-merge included YAML → one dict
│   ├── normalize.py          # v2 rule record → v1 TaxOptBRuleSpec (adapter)
│   ├── validate_schema.py    # jsonschema optional
│   └── lint.py               # Cross-rule checks (duplicate ids, missing caps)
├── evaluation/
│   ├── compliance_engine.py  # (future) move from services/ when stable
│   └── dispatch.py           # map evaluator.type → handler
├── optimization/
│   └── presets.py            # already: financial strategy presets; later OR-Tools / CP-SAT optional
└── explain/
    ├── template_registry.py  # load explainability/templates_index.yaml
    └── renderers.py          # merge YAML template + context (extends current TemplateExplanationProviderV1)
```

**Interfaces (Protocol-style):**

```python
# rules/protocols.py (skeleton)
from typing import Protocol, Any, Mapping
from pathlib import Path

class RulePackSource(Protocol):
    def load_raw(self) -> Mapping[str, Any]: ...

class RulePackNormalizer(Protocol):
    def to_canonical_v1(self, raw: Mapping[str, Any]) -> Mapping[str, Any]: ...

class RulePolicyLinter(Protocol):
    def lint(self, canonical: Mapping[str, Any]) -> list[str]: ...  # messages; empty => ok
```

**Backward compatibility:** `load_tax_opt_b_rules(path)` becomes:

1. If file is `pack.manifest.yaml` → merge includes → normalize to current dict shape → existing parser.
2. Else → existing `parse_tax_opt_b_rules_dict` unchanged.

---

## PART 4 — Explainability engine (YAML-driven)

**Principle:** Explanations are **derivatives** of `(rule_metadata, evaluation_trace, applied_relief)` — never the source of compliance truth.

1. **`explainability/templates_index.yaml`** maps `template_id` → default strings + allowed placeholders.
2. At evaluation time, build a **`RuleTrace`** object: `rule_id`, `passed`, `claimed`, `cap`, `allowed`, `violation_code`.
3. **`TemplateRenderer.render(template_id, trace, locale="en")`** returns bullets; falls back to current `TemplateExplanationProviderV1` text if template missing.

**Failure reasons:** use stable codes in YAML, e.g. `CAP_EXCEEDED`, `INELIGIBLE_EMPLOYMENT_TYPE` (future).

**Optimization suggestions:** `optimization.preset_tags` + separate `suggestions` table in YAML (non-binding) consumed only by UI / research demos.

---

## PART 5 — Versioning & effective dates

| Mechanism | Purpose |
|-----------|---------|
| `assessment_year` | Primary slice key (already in MVP). |
| `effective_from` / `effective_to` | Law timeline; loader rejects packs for `profile.tax_year` outside range (optional strict mode). |
| `deprecated: true` | Lint warns; runtime may still load for replay studies. |
| `replaces_pack_id` | Audit chain for dissertation. |
| **Overrides** | Second include file with same `id` → manifest `precedence: [overrides.yaml, base.yaml]` (merge last wins). |
| **Multi-year calculations** | Run engine **once per assessment_year pack**; compare results in FR6-style table (already pattern in compare API). |

---

## PART 6 — Optimization support

**Declarative in YAML (non-normative):**

- `optimization.presets_mvp.yaml`: defines preset ids, tags, `build: max_statutory_caps` (your current Python preset logic can read this later).
- **`rank_weight`**, **`preset_tags`**: feed **ranking** after deterministic tax compute (already FR6).
- **Recommendation generation:** Phase 1 = rules-based ranking over enumerated strategies; Phase 2 = constraint programming over discrete relief set (OR-Tools) — keep behind `OPT_ENGINE=discrete_search` flag.

**ML compatibility (later):** export **feature rows** from each evaluation: `(pack_id, profile_hash, strategy_vector, outcome, violations)` to parquet — **never** train on unstated law; use ML for **scenario suggestion** only, with hard compliance gate.

---

## PART 7 — Implementation roadmap (safest order)

| Step | Action | Risk |
|------|--------|------|
| **0** | Document-only: add this file + folder skeleton **without** moving MVP YAML. | None |
| **1** | Add `packs/mvp/pack.manifest.yaml` that **only** `includes:` the current single YAML path; implement merge in Python; **feature-flag** `USE_PACK_MANIFEST=0` default off. | Low |
| **2** | With flag on in dev: merge output must **byte-identical** (or pytest diff) to current parsed pack. | Low |
| **3** | Split **one** rule into `rules/deductions/*.yaml`; merge tests prove parity. | Low |
| **4** | Add `jsonschema` validation for manifest + optional v2 rule envelope; fail CI on invalid YAML. | Medium |
| **5** | Extend `TaxOptBRuleSpec` with optional `metadata: dict` ignored by evaluator until used by explainability. | Low |
| **6** | Wire `explainability.template_id` into FR5 provider (lookup first, fallback to hardcoded). | Medium |
| **7** | Versioned `years/YYYY_yy/*` thresholds; multiple packs for comparative studies. | Medium |
| **8** | Frontend: generate `TAX_OPT_B_MVP_RELIEF_CODES` from pack `allowed_relief_codes` at build time (optional script). | Low |

**Keep from MVP:** `evaluate_compliance`, `TaxOptBRulePack`, threshold keys, `rule_type` dispatch, golden tests.

**Create first:** `pack.manifest.yaml`, `merge.py`, parity test, then one extracted rule file.

---

## PART 8 — Research positioning (terminology)

| Plain term | Academic / engineering framing |
|------------|--------------------------------|
| YAML packs | **Declarative knowledge layer** / **policy-as-data** |
| Loader + validator | **Knowledge compilation pipeline** with **schema validation** and **consistency checking** |
| Compliance engine | **Deterministic rule executor** over a **closed-world** interpretation of statute excerpts |
| Explainability | **Template-based rational reconstruction** (traceable to sources), distinct from **generative narrative** |
| Versioning | **Temporal heterogeneity** in tax law → **effective-dated rule bundles** |
| Optimization | **Constrained strategy enumeration** with **auditable ranking**; ML optional as **policy amortization** or **recommendation heuristic** under guardrails |

**Contribution wording (example):** *“We present a versioned, declarative encoding pipeline for Sri Lankan APIT-style reliefs with deterministic evaluation and template-based explanations, enabling reproducible cross-year comparison and optimization scenario analysis without conflating machine learning with legal interpretation.”*

**Strengths to emphasize:** reproducibility, audit trails (`rule_id`, citations), separation of **law encoding** vs **solver**, testable golden cases.

---

## PART 9 — Deliverables checklist (implementation-oriented)

- [ ] Create empty dirs under `models/tax-optimization/rules/` per Part 1 (no behaviour change).
- [ ] Add `research_declarative_engine_architecture.md` (this file) to thesis appendix reference list.
- [ ] Implement `merge.py` + manifest `includes` with parity test against current YAML.
- [ ] Add JSON Schema files under `schemas/` for `pack.manifest` and v2 rule envelope.
- [ ] Gradually relocate rules from monolith → `rules/rules/**/*.yaml`.
- [ ] Point `law_reference.citation_key` at your local PDF index (IR Acts you listed).
- [ ] Extend FR5 to resolve `template_id` from `explainability/templates_index.yaml`.

This path preserves **today’s behaviour** while giving you a **research-grade** trajectory toward modular packs, effective dating, and optimization scaffolding without a big-bang rewrite.
