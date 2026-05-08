# Component B: FR5 explainability (thesis alignment)

**FR5** user-facing narratives in this repository are **template-filled, deterministic explanations** built from engine outputs (compliance violations, `applied_relief`, tax slab walk, compare rankings). They are **not** produced by an LLM or other ML: OpenAPI and provenance mark them as template-based; bundles carry optional **trace refs** (e.g. `rule_id`, `relief:…`, `slab:…`, `compare:…`, `preset:…`) for defensible linkage to the active **YAML rules pack** and evaluator behaviour.

Authoritative policy and caps remain encoded in **`models/tax-optimization/rules/*.yaml`** and evaluated by the deterministic compliance and tax modules; FR5 only narrates what those components already computed.

**Related:** [Income basis (Option A)](component-b-income-basis.md).

## Human-readable but still deterministic

Template text uses short **tier blurbs** (`summary` vs `detailed`), **display labels** for MVP relief codes (see [`tax_opt_b_explanation_copy.py`](../backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_explanation_copy.py)), and conversational phrasing in **`summary`** while **`detailed`** keeps claimed/cap/allowed lines and per-band slabs for traceability.

## Optional future: LLM paraphrase (out of band)

FR5 bundles in this repo remain **non-generative**. If you later want softer prose for demos or accessibility, add a **separate** optional integration (e.g. a dedicated endpoint or client-side call) that takes the structured bundle or raw compute JSON as input and returns paraphrased text with explicit provenance such as `engine: llm_optional` and a disclosure that output is **not** used for compliance/tax decisions. Do not fold LLM output into `evaluate_compliance` or `compute_apit_liability`; keep the template bundle as the auditable source of truth.
