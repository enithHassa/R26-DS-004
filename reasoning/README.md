# Reasoning Workspace

Think-Twice and symbolic validation rule artifacts for legal compliance checks.

## Phase 5 — Symbolic rule engine (MVP)

- **`symbolic_rules_v1.json`** — personal relief schedule, max marginal rate, forbidden phrases, advisory disclaimer.
- **`backend/comp-language-model/app/services/symbolic_engine.py`** — validates generated advisory text.
- **`backend/comp-language-model/app/services/think_twice.py`** — replaces failing drafts with a safe fallback.

Run unit tests:

```powershell
$env:PYTHONPATH = "backend/comp-language-model;$PWD"
pytest backend/comp-language-model/app/tests/test_phase5_phase6.py -q
```