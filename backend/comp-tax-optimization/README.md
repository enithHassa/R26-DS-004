# Component 2 — Tax Strategy Optimization (Function 1)

**Port:** `8002` (override with `COMP_OPTIMIZATION_PORT` in `.env`). **Gateway:** `http://localhost:8000/api/v1/optimization/...` when `COMP_OPTIMIZATION_URL` points at this service.

| Where | Example |
| ----- | ------- |
| Direct API + Swagger | `http://127.0.0.1:8002/docs` |
| Compliance POST | `http://127.0.0.1:8002/api/v1/compliance/check` |
| Via gateway | `http://127.0.0.1:8000/api/v1/optimization/compliance/check` |

Rule-backed compliance is served from this package. Run from the **repository root** with `PYTHONPATH=.` so `backend.shared` resolves.

## Local API

```bash
PYTHONPATH=. uvicorn tax_opt_b_app.main:app \
  --app-dir backend/comp-tax-optimization \
  --reload --port 8002
```

- Swagger: http://localhost:8002/docs  
- Health: http://localhost:8002/health  
- Compliance: `POST http://localhost:8002/api/v1/compliance/check` (OpenAPI tag: **tax-opt-b-compliance**)

### curl (direct — port 8002)

With the service running, a passing example:

```bash
curl.exe -s -X POST "http://127.0.0.1:8002/api/v1/compliance/check" ^
  -H "Content-Type: application/json" ^
  -d "{\"profile\":{\"tax_year\":\"2024_25\",\"employment_type\":\"employee\",\"dependents\":0,\"annual_gross_income\":\"2400000\",\"estimated_annual_taxable_income\":\"1800000\"},\"strategy\":{\"claims\":[{\"relief_code\":\"life_insurance_premium\",\"claimed_amount_annual\":\"50000\"}]}}"
```

(Bash: use `\` line continuations instead of `^`, or a single-line `-d`.)

### curl (via gateway — port 8000)

Start **both** optimization (8002) and the API gateway (8000). Same JSON body:

```bash
curl.exe -s -X POST "http://127.0.0.1:8000/api/v1/optimization/compliance/check" ^
  -H "Content-Type: application/json" ^
  -d "{\"profile\":{\"tax_year\":\"2024_25\",\"employment_type\":\"employee\",\"dependents\":0,\"annual_gross_income\":\"2400000\",\"estimated_annual_taxable_income\":\"1800000\"},\"strategy\":{\"claims\":[{\"relief_code\":\"life_insurance_premium\",\"claimed_amount_annual\":\"50000\"}]}}"
```

`COMP_OPTIMIZATION_URL` in `.env` must point at the running optimization service (default `http://localhost:8002`).

Rules file (default): `models/tax-optimization/rules/it22064486_sl_tax_mvp.yaml`  
Override with `COMP_OPTIMIZATION_RULES_PATH` in `.env`.

The MVP pack uses **`thresholds`** (personal relief, `apit_slabs`, `deductions` caps/rates) plus a declarative **`rules`** list (`type`, `rule_id`, `description`, `reference`, and type-specific fields such as `cap_field`). Function 1 evaluates claims against `deduction_cap`, `charitable_donation_cap`, and `retirement_contribution_cap` rules; slabs are documented for later full tax computation.

At runtime the YAML is validated and parsed into a **`TaxOptBRulePack`** (immutable dataclasses in `tax_opt_b_rules_loader.py`). The compliance engine only reads that pack — no disk I/O during `evaluate_compliance`. In tests, build a pack with **`parse_tax_opt_b_rules_dict(...)`** and pass it to **`evaluate_compliance`** without HTTP.

**FR5 (explainability):** responses may embed a template-based explanation bundle (`include_explanations`) with trace refs to rules and scenarios — not LLM output; policy stays in YAML. Short thesis note: [`docs/component-b-fr5-explainability.md`](../../docs/component-b-fr5-explainability.md).

## Tests

```bash
PYTHONPATH=. pytest backend/comp-tax-optimization
```

Golden compliance: `tests/test_tax_opt_b_compliance_golden.py`. Loader validation: `tests/test_tax_opt_b_rules_loader.py`. (See `app/tests/README.md` for why these are not under `app/tests/`.)
