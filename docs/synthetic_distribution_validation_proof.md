# Synthetic vs reference — distribution validation proof

This report is **machine-generated** from `scripts/validate_synthetic_profiles_distribution.py`.
It supports the claim that the synthetic cohort matches the **marginal distributions** of the
reference cohort on tested financial and demographic fields (not row-by-row identity).

## Datasets compared

- **Reference (actual / audit-matched):** `data/synthetic/reference_matched_anonymized/profiles_reference_matched_anonymized.csv`
- **Synthetic:** `data/synthetic/profiles_corrected_tax (1).csv`
- **Rows:** reference = 25,000, synthetic = 25,000

## Methods

- **Two-sample Kolmogorov–Smirnov (KS)** on continuous variables: tests whether two empirical CDFs differ.
  With very large *N*, KS *p*-values often go below 0.01 even when the **KS statistic (D)** is small —
  i.e. distributions are visually close but not identical. Interpret **D** as practical closeness.
- **Subsampled KS (N≤4000 per arm, stratified random):** reduces overpowering;
  see `ks_continuous_subsampled` in the JSON.
- **Chi-square** on categorical margins (sparse categories merged to `_other_`).
- **Jensen–Shannon divergence** (base 2) on `income_sources_json` *signature* (sorted kinds).

## KS — continuous variables (full sample)

| Variable | D (KS stat) | p-value | Pass p>0.01 |
|----------|------------|---------|-------------|
| `gross_monthly_income_lkr` | 0.014520 | 0.01017881544459934 | yes |
| `monthly_expenses_lkr` | 0.014560 | 0.009886792303797557 | no |
| `monthly_debt_service_lkr` | 0.025320 | 2.148565392612492e-07 | no |
| `liquid_savings_lkr` | 0.011080 | 0.09222473884403115 | yes |
| `existing_investments_lkr` | 0.043560 | 4.770057619201754e-21 | no |
| `total_debt_lkr` | 0.025080 | 2.9079270454163113e-07 | no |
| `baseline_tax_liability_lkr` | 0.030080 | 2.928912149577241e-10 | no |
| `effective_tax_rate` | 0.000000 | 1.0 | yes |
| `gross_annual_taxable_income_lkr` | 0.014520 | 0.01017881544459934 | yes |

## KS — continuous variables (subsample ≤4000 each)

| Variable | D | p-value | Pass p>0.01 |
|----------|---|---------|-------------|
| `gross_monthly_income_lkr` | 0.023500 | 0.2193466228114725 | yes |
| `monthly_expenses_lkr` | 0.026000 | 0.13383891038649265 | yes |
| `monthly_debt_service_lkr` | 0.033250 | 0.024008035370044718 | yes |
| `liquid_savings_lkr` | 0.024500 | 0.18113086517407834 | yes |
| `existing_investments_lkr` | 0.043000 | 0.0012257425821568782 | no |
| `total_debt_lkr` | 0.037000 | 0.008367349551940797 | no |
| `baseline_tax_liability_lkr` | 0.033750 | 0.020996499909956026 | yes |
| `effective_tax_rate` | 0.011000 | 0.9689029039633784 | yes |
| `gross_annual_taxable_income_lkr` | 0.023500 | 0.2193466228114725 | yes |

### Practical closeness (full-sample KS *D*)

- Max KS *D* across tested continuous variables: **0.04356000000000004**
  (Rule of thumb: *D* < 0.05 often reads as “very similar” in applications; your thesis can cite Romano, 2004;
  or show overlaid ECDF plots in an appendix.)

## Chi-square — categorical margins

| Variable | χ² | dof | p-value |
|----------|----|-----|---------|
| `gender` | 2.478258145616142e-28 | 1 | 0.9999999999999875 |
| `province` | 2.3182564774168283e-28 | 3 | 1.0 |
| `marital_status` | 0.0 | 2 | 1.0 |
| `occupation` | 2.0808266462562797e-28 | 2 | 1.0 |
| `archetype` | 0.0 | 5 | 1.0 |
| `age_band` | 8.882500429887836e-29 | 10 | 1.0 |

## Income composition (Jensen–Shannon)

- JS(H) = **0.0** (vocab size 3)

## Quantile alignment (selected continuous variables)

Median and tail quantiles of reference vs synthetic (relative error vs |reference| at each quantile).

### `gross_monthly_income_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 1.29e+05 | 1.296e+05 | 0.004653 |
| 0.25 | 2.125e+05 | 2.098e+05 | 0.01296 |
| 0.5 | 2.788e+05 | 2.795e+05 | 0.002434 |
| 0.75 | 3.816e+05 | 3.811e+05 | 0.001091 |
| 0.95 | 6.148e+05 | 6.1e+05 | 0.007784 |

### `monthly_expenses_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 9.9e+04 | 9.672e+04 | 0.02299 |
| 0.25 | 1.308e+05 | 1.299e+05 | 0.007325 |
| 0.5 | 1.759e+05 | 1.751e+05 | 0.004439 |
| 0.75 | 2.384e+05 | 2.403e+05 | 0.007686 |
| 0.95 | 3.982e+05 | 3.964e+05 | 0.004509 |

### `monthly_debt_service_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 0 | 0 | 0 |
| 0.25 | 0 | 0 | 0 |
| 0.5 | 1.146e+04 | 1.075e+04 | 0.06152 |
| 0.75 | 2.982e+04 | 2.83e+04 | 0.05068 |
| 0.95 | 9.033e+04 | 7.968e+04 | 0.1178 |

### `liquid_savings_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 1.451e+05 | 1.435e+05 | 0.0108 |
| 0.25 | 3.064e+05 | 3e+05 | 0.02092 |
| 0.5 | 4.886e+05 | 4.855e+05 | 0.006378 |
| 0.75 | 6.854e+05 | 6.949e+05 | 0.01393 |
| 0.95 | 1.131e+06 | 1.143e+06 | 0.01106 |

### `existing_investments_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 6.77e+04 | 6.077e+04 | 0.1024 |
| 0.25 | 2.897e+05 | 2.758e+05 | 0.04813 |
| 0.5 | 6.496e+05 | 6.101e+05 | 0.06073 |
| 0.75 | 1.111e+06 | 1.041e+06 | 0.06263 |
| 0.95 | 2.134e+06 | 1.975e+06 | 0.07454 |

### `total_debt_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 0 | 0 | 0 |
| 0.25 | 0 | 0 | 0 |
| 0.5 | 9.764e+05 | 9.297e+05 | 0.04775 |
| 0.75 | 2.578e+06 | 2.444e+06 | 0.05174 |
| 0.95 | 7.748e+06 | 6.781e+06 | 0.1248 |

### `baseline_tax_liability_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 1.241e+04 | 1.138e+04 | 0.0823 |
| 0.25 | 1.733e+05 | 1.649e+05 | 0.0486 |
| 0.5 | 4.442e+05 | 4.181e+05 | 0.05864 |
| 0.75 | 9.075e+05 | 8.51e+05 | 0.06231 |
| 0.95 | 2.047e+06 | 1.828e+06 | 0.1068 |

### `effective_tax_rate`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 0.007261 | 0.007261 | 0 |
| 0.25 | 0.06432 | 0.06432 | 0 |
| 0.5 | 0.1247 | 0.1247 | 0 |
| 0.75 | 0.1863 | 0.1863 | 0 |
| 0.95 | 0.2519 | 0.2519 | 0 |

### `gross_annual_taxable_income_lkr`
| q | reference | synthetic | rel abs diff / |ref| |
|---|-----------|-----------|------------------------|
| 0.05 | 1.548e+06 | 1.556e+06 | 0.004653 |
| 0.25 | 2.55e+06 | 2.517e+06 | 0.01296 |
| 0.5 | 3.346e+06 | 3.354e+06 | 0.002434 |
| 0.75 | 4.579e+06 | 4.574e+06 | 0.001091 |
| 0.95 | 7.377e+06 | 7.32e+06 | 0.007784 |

## Automated heuristic gates (tune in script)

- KS *p* > 0.01 (all continuous, full *N*): **False**
- KS *p* > 0.01 (subsampled, if run): **False**
- KS *D* < 0.05 (all, practical closeness): **True**
- Chi-square *p* > 0.01: **True**
- JS(H) < 0.12 on income signatures: **True**

## Interpretation (auto-generated)

- Categorical margins (gender, province, marital status, occupation, archetype, age band) are statistically indistinguishable from the reference under the chi-square setup used here.
- Income-source *kind* signatures match the reference distribution in Jensen–Shannon terms.
- All tested continuous variables have KS *D* < 0.05 (max *D* = 0.0436), which supports **practical** distributional similarity despite large-*N* sensitivity of the KS *p*-value.
- Strict KS *p* > 0.01 is **not** met for every continuous margin at full sample size: with 25k+ rows, tiny CDF differences are often flagged as “significant.” Pair this table with quantiles above and optional ECDF plots in an appendix.

## Machine-readable output

See companion JSON (same run): `distribution_validation_proof.json` next to this file or path passed as `--report-json`.
