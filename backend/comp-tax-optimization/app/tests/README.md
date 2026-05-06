# Why tests are not under `app/tests/`

Your plan referenced `backend/comp-tax-optimization/app/tests/`. The repository instead keeps pytest files under:

`backend/comp-tax-optimization/tests/`

Reason: the API gateway also uses a path ending in `app/tests/`. When both trees exist, pytest can register two different files as the same module name (`app.tests.*`), which breaks a combined run such as:

`PYTHONPATH=. pytest backend/comp-tax-optimization backend/api-gateway`

Golden and loader tests live next to the component as:

- `tests/test_tax_opt_b_compliance_golden.py`
- `tests/test_tax_opt_b_rules_loader.py`
