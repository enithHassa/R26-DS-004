# Personalized Recommendation & Predictive Impact Modeling Engine
### Current Architecture & How the Component Works
**Component 3**

---

## 1. Purpose of the Component

Component 3 is a Sri Lankan personal-tax decision-support system. Given a taxpayer's financial profile, it generates candidate tax-saving strategies, ranks and explains them, and simulates their long-run financial impact so that a user can make an informed, evidence-grounded adoption decision.

The component owns four responsibilities end-to-end:

1. **Financial profile management** — capturing and deriving a taxpayer's financial position.
2. **Strategy recommendation** — ranking eligible tax strategies for a given profile using learning-to-rank and retrieval-based methods.
3. **Adoption-likelihood estimation** — estimating how likely a taxpayer is to adopt a given recommended strategy.
4. **Predictive impact modelling** — simulating, via Monte Carlo methods, the multi-year financial outcome of adopting a strategy versus not.

The component is deliberately split across three physical locations that are wired together at runtime:

| Location | Role |
|---|---|
| `backend/comp-personalized-recommendation/` | Live FastAPI service (routers, schemas, DB models, services) |
| `models/personalized-recommendation/` | Offline ML/rules/simulation package (rules engine, strategy catalogue, ranking and adoption models, Monte Carlo engine, explainability) |
| `frontend/src/features/personalized-recommendation/` | Decision-support dashboard UI |

**A note on precision (important for the research write-up):** not everything in this component is machine-learned. The ranking model and the adoption-likelihood model are trained ML artefacts (LightGBM/LambdaMART and a scikit-learn-compatible classifier, respectively). The tax-rule computations, the strategy catalogue evaluation, and — critically — the **Predictive Impact Modeling Engine itself** are rule-based/stochastic simulation over deterministic tax logic, not trained models. This distinction should be preserved in the paper rather than describing every part uniformly as "AI-driven."

---

## 2. Core Architectural Idea

| Layer | Main responsibility | Current technology |
|---|---|---|
| Financial Profile Store | Holds taxpayer demographic and financial data, plus a synthetic monthly history. | PostgreSQL (SQLAlchemy ORM) |
| Tax Rules & Strategy Catalogue | Encodes Sri Lankan 2024/25 tax rules and a catalogue of tax strategies with eligibility conditions. | YAML rule files + pure Python rule engine |
| Ranking Engine | Learning-to-rank of eligible strategies for a given profile. | LightGBM (LambdaMART), scikit-learn feature pipeline |
| Adoption-Likelihood Model | Estimates probability that a taxpayer adopts a recommended strategy. | Gradient-boosted classifier (LightGBM), `predict_proba` |
| Retrieval (RAG prototype) | Retrieves and ranks strategies by textual similarity to the profile. | TF-IDF vectorisation + cosine similarity (scikit-learn) |
| Hybrid Recommender | Blends the ranking score and the retrieval score into one recommendation. | Weighted linear combination |
| Predictive Impact Modeling Engine | Simulates multi-year financial trajectories under baseline vs. strategy scenarios. | Monte Carlo simulation (NumPy) over the deterministic tax rules engine |
| Explainability | Attributes the ranking score to input features. | SHAP |
| Decision Support Dashboard | Presents profiles, recommendations, adoption evidence, explanations, and impact simulations. | React 19 + TypeScript, Recharts |

As with Component 2's design philosophy, the boundary here is explicit: the **rule engine, not any model, is the sole authority on tax arithmetic**. Machine-learned components rank, estimate likelihood, retrieve, and explain — they do not compute tax.

---

## 3. Where the Component Sits

- **Frontend:** profile creation/edit, ranked recommendations (LambdaMART-only, RAG-only, or hybrid views), adoption-evidence panel, SHAP explanation panel, impact-simulation page, strategy comparison page, and separate auditor/taxpayer login and portal screens.
- **Gateway:** `/api/v1/recommendation/**` proxies to this component; the gateway also polls this component's `/health` endpoint as part of its own readiness check.
- **Service:** runs on port 8003, package rooted at `backend/comp-personalized-recommendation/app`, entry point `main.py`.
- No outbound calls from this component to Components 1, 2, 4, or 5 were found in the code inspected; integration with the wider system currently runs one-directional, from the gateway inward. *(This should be re-verified before being stated definitively in the final paper, as not every file was exhaustively searched for outbound calls.)*

---

## 4. Data Model

### 4.1 Financial Profile

`FinancialProfile` is the central entity. It captures demographic fields (full name, date of birth, gender, district, marital status, occupation, dependents), employment fields (employment type, employer sector, years employed, gross monthly income, annual bonus), balance-sheet fields (liquid savings, existing investments, total debt, EPF/ETF balances, vehicle and property value), protection and liability fields (health insurance, life insurance premium, home loan interest, donations), and planning preferences (risk tolerance, investment horizon, retirement age target). It also stores a JSON `income_sources` breakdown, the applicable tax year, and a JSON `eligibility_overrides` field allowing a user or auditor to manually pin or clear a specific eligibility flag.

The residency status, nationality, employment type, employer sector, annual bonus, vehicle value, property value, and retirement age target fields are a recent extension to the profile schema, introduced together with matching enumerations for residency status (resident, non-resident, dual), employment type (permanent, contract, part-time, freelance, unemployed), and employer sector (private, public, NGO, self-employed). This extension flows through the ORM model, the API schema, and the frontend profile form and type definitions consistently.

### 4.2 Derived Features

A `DerivedFeatures` object is computed on demand (not stored) from a profile, combining the profile's raw fields with the tax-rules engine. It includes annual taxable income, allowable deductions, taxable income after deductions, baseline tax liability, effective tax rate, monthly disposable income, savings rate, debt-to-income ratio, liquidity ratio, and a set of boolean eligibility flags (e.g. above tax threshold, has disposable income, has employer provident fund contribution, has health/life insurance, has a home loan, retirement-eligible, has dependents, has a liquidity buffer, has donations, has ETF/other investments, has a long investment horizon, high debt-to-income, has a vehicle, has property). Eligibility flags can be individually overridden by the user.

### 4.3 Synthetic History

Because a profile represents only a single current snapshot, the system generates a synthetic monthly financial history (currently 36 months by default) to support trend visualisation and the adoption-evidence panel. This history is produced by a deterministic, seeded stochastic generator — not observed data — and is explicitly documented as synthetic, clearly-labelled demo data rather than a claim of real financial records.

### 4.4 Recommendations and Feedback

A `Recommendation` groups a set of `RecommendationItem` rows for a profile (one row per ranked strategy), each carrying its rank, estimated annual savings, adoption probability, risk score, confidence, and structured score/explanation payloads. `RecommendationFeedback` records whether a user accepted or dismissed a recommendation, with an optional reason and rating, forming the basis for any future retraining of the adoption model on real (rather than proxy) adoption behaviour.

### 4.5 Tax Strategy Catalogue

`TaxStrategy` is a catalogue table (code, name, category, description, legal reference, eligibility bounds on income/age/liquidity, risk profile, effort score). It is populated lazily from a YAML catalogue the first time a strategy is recommended, rather than via a seed migration.

### 4.6 Database Tables

Tables owned by this component: `users`, `financial_profiles`, `profile_history_snapshots`, `recommendations`, `recommendation_items`, `recommendation_feedback`, `behavioural_answers`, `tax_strategies`, built up across a sequence of Alembic migrations. A recent migration extending `financial_profiles` with the fields described in §4.1 was authored to chain from the prior head only, because a parallel migration head (used by another component) relies on JSONB columns incompatible with the SQLite development database — leaving two unmerged Alembic heads as a known, documented outstanding item.

---

## 5. Tax Rules Engine

Before any recommendation or simulation runs, the system computes a taxpayer's actual liability using a deterministic rule engine over Sri Lanka's 2024/25 tax rules, expressed in YAML. This engine applies allowable deductions (life and health insurance, home loan interest, donations) to gross taxable income, then computes the resulting tax liability. This engine is reused identically by: profile feature derivation, the strategy catalogue's eligibility evaluator, and the Predictive Impact Modeling Engine's year-by-year simulation. Centralising the tax arithmetic in one deterministic component — rather than inside any of the learned models — mirrors the architectural boundary used elsewhere in the system (cf. Component 2): **AI ranks and estimates; it does not calculate tax.**

---

## 6. Strategy Generation and Eligibility

A catalogue of tax strategies (defined in YAML, with eligibility rule expressions, legal references, and required documentation per strategy) is evaluated against a profile's derived features to determine feasibility. This evaluation is rule-based — it checks a strategy's stated eligibility conditions (income bounds, age bounds, liquidity bounds, risk profile) against the profile — and produces a feasibility verdict per strategy, independent of any ranking model.

The dedicated `POST /api/v1/strategies/generate` endpoint is currently a stub (returns HTTP 501, deferred to a later work package); the underlying rule-based evaluator is, however, already used internally by the ranking, RAG, and hybrid recommendation services described below.

---

## 7. Recommendation Ranking Engine

Eligible strategies are scored for a given profile using a **LightGBM LambdaMART** learning-to-rank model, invoked via its `.predict()` interface over a pairwise profile × strategy feature table. The resulting ranked list is returned via `POST /api/v1/recommendations`, and per-recommendation feedback (accept/dismiss/rating) is captured via `POST /api/v1/recommendations/feedback` to support future retraining.

## 8. Adoption-Likelihood Estimation

A separate gradient-boosted classifier estimates the probability that a taxpayer will adopt a given recommended strategy, exposed through scikit-learn's `predict_proba` interface. **This model is currently trained on a proxy label** — derived largely from rule-based eligibility rather than observed adoption outcomes — because no real adoption-behaviour data yet exists. The `RecommendationFeedback` table is the intended mechanism for eventually replacing this proxy with real behavioural labels. This caveat should be stated explicitly in the paper rather than presented as validated real-world adoption prediction.

## 9. Retrieval-Augmented Recommendation (RAG Prototype)

A retrieval prototype builds a TF-IDF vector index (unigrams and bigrams) over the strategy catalogue's textual content (name, category, description, eligibility conditions, formula reference, required documents), converts a profile into a text query, and ranks strategies by cosine similarity. This is retrieval only — the "explanation" text produced alongside a retrieved result is template-based formatting of the retrieved data, not a generative model call. Exposed via `POST /api/v1/rag`.

## 10. Hybrid Recommender

The hybrid recommender combines the LambdaMART ranking score and the RAG cosine-similarity score into a single blended score:

```
hybrid_score = λ × lambdamart_score_normalised + (1 − λ) × rag_similarity_score
```

with a default weighting of λ = 0.7 (ranking) and 1 − λ = 0.3 (retrieval), applied only to strategies that pass the rule-based eligibility filter. Exposed via `POST /api/v1/hybrid`.

## 11. Explainability

Ranking decisions are explained using **SHAP**, producing per-feature attributions (top and bottom contributing reasons, with direction) for a specific profile × strategy pair, exposed via `POST /api/v1/recommendations/explain`. This explains the *ranking model's* score; it is a distinct feature from the Predictive Impact Modeling Engine and does not re-run any simulation.

---

## 12. Predictive Impact Modeling Engine — How It Actually Works

This is the component most directly analogous to Component 2's "calculation engine" in terms of centrality, and it is important to describe it precisely: it is a **Monte Carlo stochastic simulation over the deterministic tax rules engine**, not a trained machine-learning model.

### 12.1 What It Simulates

Given a profile, an optional strategy, and a set of simulation parameters, the engine simulates a configurable number of independent multi-year financial trajectories ("paths") — by default on the order of thousands of paths over a default ten-year horizon, both bounded within user-configurable ranges. For each simulated path and year:

1. A random salary-growth rate is drawn (Gaussian, with configurable mean and a bounded/clipped range) and applied to income.
2. Annual tax is recomputed for that year and path by calling the deterministic tax rules engine — using either the baseline deduction profile or the strategy's deduction profile, with strategy adoption in a given path gated by a random draw against a configurable adoption-success probability.
3. Expenses are inflated by a compounding inflation factor.
4. Disposable income and non-negative savings are computed for the year.
5. A random investment-return rate is drawn (Gaussian, bounded/clipped) and compounded to update net worth.

### 12.2 What It Produces

- A **median (P50) projection** of salary, tax, savings, and net worth per year, for both the baseline scenario and, where a strategy is supplied, the strategy scenario.
- **Uncertainty bands** (10th, 50th, and 90th percentile) computed across all simulated paths per year.
- Summary statistics: expected total tax savings, expected net worth, standard deviation of savings, a 10th-percentile value-at-risk on net gain, and the probability that adopting the strategy yields a higher net worth than the baseline.

Exposed via `POST /api/v1/impact/simulate` (single scenario) and `POST /api/v1/impact/compare` (multiple strategies against the same profile and horizon).

### 12.3 What It Is Not

It does not predict a single certain future; the mean parameters (salary growth, inflation, investment return, adoption-success probability) are user-adjustable assumptions, not guaranteed facts, and a wide gap between the 10th and 90th percentile bands reflects genuine modelled uncertainty rather than a defect. It is also distinct from the SHAP explanation panel, which explains the *ranking* model rather than the simulation.

---

## 13. Multi-Objective Scoring

Where a learning-to-rank score is unavailable, a fallback weighted-sum scoring formula combines estimated tax savings, adoption probability, feasibility, and a risk penalty into a single score, using configurable weights. This fallback exists specifically for cases where the trained ranking artefact cannot be used; the primary ranking path uses the LambdaMART model described in §7.

---

## 14. Decision Support Dashboard (Frontend)

The frontend (React 19 + TypeScript, TailwindCSS, Recharts) provides the following user-facing flow: profile creation/editing → viewing ranked recommendations (via the LambdaMART-only, RAG-only, or hybrid view) → reviewing an adoption-evidence panel (built from the synthetic history and derived features) → reviewing a SHAP-based explanation of a chosen recommendation → running and reviewing a Monte Carlo impact simulation (net-worth and tax-liability fan charts, year-by-year tables, summary cards) → comparing strategies against one another. Separate login and portal pages exist for an auditor role and for taxpayer users, matching the two authentication paths on the backend.

---

## 15. Synthetic Data Validation

Because the profile dataset used for development and offline model training/evaluation is synthetic, a statistical validation was carried out comparing a synthetic profile dataset against a separately constructed reference/audit-matched dataset, using two-sample Kolmogorov–Smirnov tests on continuous variables, chi-square tests on categorical margins, Jensen–Shannon divergence on income-composition signatures, and quantile-alignment comparison.

The validation's own stated conclusion is that it supports **marginal distributional similarity**, not row-level identity: full-sample KS p-values for some continuous variables fall below a strict significance threshold (an expected effect of testing at very large sample sizes), but the KS test statistic itself remains small across all tested continuous variables, and categorical margins pass their chi-square tests. This distinction — distributional plausibility rather than proof of real-world accuracy — should be preserved precisely in any paper claim about the synthetic data's validity, since no comparison against genuinely observed taxpayer records was performed.

---

## 16. Honesty Notes for the Research Write-Up

Two caveats surfaced directly in the component's own working documentation are important to carry into the paper rather than omit:

1. The adoption-likelihood model is trained on a proxy label derived largely from rule-based eligibility, not on observed real-world adoption behaviour, because no such behavioural dataset currently exists. The recommendation-feedback mechanism is the intended path to closing this gap.
2. Offline evaluation of the ranking model has previously shown near-ceiling performance, which is suspected to reflect a degree of circularity — the evaluation labels and the training labels are both derived from the same underlying rule engine, rather than from an independent ground truth. This should be flagged as a limitation rather than reported as a validated real-world accuracy figure.

No specific numeric accuracy, precision, or evaluation figures are reported in this document, as no verified figures were available in the codebase at the time of writing; any such figures used in the final paper should be sourced directly from the underlying evaluation artefacts and cited with their provenance.

---

## 17. Recent Changes (as of this document's date)

The following changes were present in the working tree at the time this document was prepared and should be reflected in any architecture description: extension of the financial profile with residency, nationality, employment type/sector, annual bonus, vehicle value, property value, and retirement age target fields (with corresponding enumerations); inclusion of annual bonus income in annual taxable income, monthly disposable income, and savings-rate calculations; two new eligibility flags for vehicle and property ownership; and an increase in the default synthetic history window from 24 to 36 months. These changes are reflected consistently across the backend models/schemas/services and the corresponding frontend types and forms.
