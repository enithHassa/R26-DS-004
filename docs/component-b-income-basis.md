# Component B: income basis (Option A)

This note is **thesis-ready**: you may copy or lightly paraphrase it in a methodology chapter when describing how the MVP fixes the income measure used for progressive tax and for percentage caps that depend on “income.”

## Two ways the profile is populated

**Structured financial intake** (`TaxOptBFinancialInputsV1`, mapped to `TaxOptBProfileV1`) implements **Option A**: there is **no separate estimated taxable field** on that path. Gross is the sum of salary, business, and other annual amounts; donation-cap and slab logic use that **gross-only** basis once personal relief and allowed deductions are applied in the engine. The schema documents this explicitly:

```52:57:backend/comp-tax-optimization/tax_opt_b_app/tax_opt_b_schemas_financial_inputs_v1.py
class TaxOptBFinancialInputsV1(BaseModel):
    """Sectioned financial questionnaire aligned with dissertation Step 1.

    Income basis for slabs and donation % caps is **gross only** (salary + business + other);
    there is no separate estimated taxable field (Option A).
    """
```

The mapper sets `estimated_annual_taxable_income=None` so the runtime profile never carries a taxable override on structured intake.

**Direct profile / compute-tax and the transactions snapshot path** may set `estimated_annual_taxable_income` when the caller or upstream snapshot supplies it (e.g. manual JSON body or income snapshot from Component 1). That optional field switches the **pre–personal-relief income basis** used for slabs (and aligns with the same choice for cap bases documented on the profile).

## Single rule for “income basis before personal relief”

Computation uses one helper: taxable if set, else gross.

```45:48:backend/comp-tax-optimization/tax_opt_b_app/services/tax_opt_b_tax_computation.py
def income_basis_before_personal_relief(profile: TaxOptBProfileV1) -> Decimal:
    if profile.estimated_annual_taxable_income is not None:
        return profile.estimated_annual_taxable_income
    return profile.annual_gross_income
```

The module docstring above this function states the same contract: structured intake leaves `estimated_annual_taxable_income` unset so the basis is gross only; other paths may set it.

## Disclaimer (methodology and repo)

**Authoritative behaviour in this repository is the versioned rules pack (YAML) plus the deterministic evaluator and calculator**—not a statement of law or filing position. For a dissertation, state clearly that thresholds, slabs, and reliefs must be verified against current Inland Revenue materials and statute; this implementation is a **research / MVP** traceability scaffold.

**See also:** [FR5 explainability](component-b-fr5-explainability.md) — template narratives + trace refs; no ML; rules remain YAML-driven.
