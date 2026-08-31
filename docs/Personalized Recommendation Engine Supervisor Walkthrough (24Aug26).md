# Personalised Recommendation and Predictive Impact Modelling Engine — Supervisor Walkthrough

A plain-English, step-by-step account of what has been built for Component 3, written to be talked through in a supervision meeting rather than read as a technical spec.

---

## 1. What this component is for

This component takes a taxpayer's financial profile and answers three questions for them:

1. **"Which tax strategies suit me?"** — a ranked, personalised list of strategies.
2. **"Would I actually use one of these?"** — an estimate of how likely the taxpayer is to adopt each strategy.
3. **"What would happen if I did?"** — a forward-looking simulation of the financial impact over time.

Throughout, the component is deliberately kept out of the business of calculating tax itself. A separate, deterministic rules engine owns all tax arithmetic. The machine learning parts only rank, estimate likelihood, retrieve relevant material, and explain — they never compute a tax figure themselves. This separation matters because it means the numbers shown to a user are always traceable back to a fixed rule, not a model's guess.

---

## 2. The building blocks, in the order data flows through them

### Step 1 — A taxpayer creates an account and fills in a financial profile

- Sign-up captures personal details only (name, contact details, date of birth, etc.) — no financial information yet.
- On first login, the taxpayer completes a financial intake form covering income, expenses, savings, debt, insurance, EPF/ETF balances, dependents, risk tolerance, and similar fields.
- This is stored as a `FinancialProfile` record, one per taxpayer, and is the single source of truth for everything downstream.

### Step 2 — A few short behavioural questions refine the profile

- The taxpayer is asked eight short questions (e.g. comfort with risk, investment horizon, past tax-filing history).
- Only two of these — risk comfort and investment horizon — currently feed back into the profile and change future recommendations. The other six are recorded but not yet used in scoring. This is a deliberate, documented limitation rather than an oversight — the groundwork is there to use them later.

### Step 3 — The profile is turned into "derived features"

Before any ranking or modelling happens, the profile is converted into a richer, standardised set of numbers and yes/no flags — for example:

- Annual taxable income, baseline tax liability, effective tax rate (all calculated by the deterministic rules engine, not a model).
- Disposable income, savings rate, debt-to-income ratio, liquidity ratio.
- Sixteen eligibility flags such as "above the tax-free threshold", "has a home loan", "has a liquidity buffer of 3+ months' expenses", "is retirement-eligible".

An auditor can also manually override any one of these flags for a given profile (for example, to correct a case the automatic logic gets wrong), and that override is respected on every future calculation for that profile.

### Step 4 — Strategies are ranked for that specific person

- A **LightGBM LambdaMART model** — a learning-to-rank algorithm, the same family used in search-engine result ranking — scores every candidate tax strategy for a given profile and puts them in order of relevance.
- Separately, a **gradient-boosted classifier** estimates the probability that the taxpayer would actually adopt each strategy, not just that it's relevant to them.
- A **retrieval step** (TF-IDF text similarity, i.e. matching profile characteristics against strategy descriptions by word overlap) pulls in relevant supporting material, independent of the ranking model.
- These three signals are then blended — the ranking score and retrieval score are combined with fixed weights (70% ranking, 30% retrieval) — to produce the final "hybrid" recommendation list shown to the user. A simpler, rules-only fallback exists for cases where the models can't be used.

### Step 5 — "Would this actually work for me?" — the adoption evidence check

This is a nice piece of honesty built into the product: rather than just trusting the adoption-likelihood percentage from Step 4, the system independently checks whether the taxpayer's own financial history is *consistent* with that number.

- Since real multi-year financial history isn't available for most profiles, a synthetic (but deterministic and reproducible) monthly history is generated per profile, working backwards from their current snapshot using plausible growth and decay assumptions.
- A separate piece of logic then compares recent trends in income, savings rate, and debt against the model's stated confidence, and produces a plain verdict — "strong", "moderate", or "weak" — shown alongside the recommendation.
- Critically, this trend check does **not** feed back into or change the adoption probability. It is kept visibly separate, so a user can see "the model says X, and here's whether the evidence agrees with X" rather than one number pretending to be more certain than it is.

### Step 6 — "What would this look like over time?" — the impact simulation

- Once a taxpayer picks a strategy, a **Monte Carlo simulation** projects their finances forward (by default over a 10-year horizon, running 1,000 simulated paths) using adjustable assumptions for salary growth, inflation, and investment return, all built on top of the same deterministic tax rules engine — not a separate guess.
- The output includes expected tax savings, expected net worth, the probability of a net financial gain, a downside (P10) estimate, and fan charts showing the full spread of outcomes rather than a single misleadingly precise number.
- The interface is explicit with the user about what this is *not* claiming: it is not a certainty, the assumptions are user-adjustable rather than guaranteed, and a wide gap between best-case and worst-case outcomes reflects genuine uncertainty rather than a flaw in the tool.

### Step 7 — Explaining the "why"

- A SHAP-based explanation layer accompanies recommendations, showing which features of the profile pushed a given strategy up or down the ranking — so the recommendation isn't a black box.

---

## 3. How the models are trained

A single training script (`train_phase4_ranking_adoption.py`) produces both the ranking model and the adoption model from one dataset of synthetic (and, where available, real) profiles matched against a catalogue of strategies.

- **Labels** are sourced in a clear priority order: real recorded outcomes if they exist (from actual user feedback captured in the system), otherwise predictions from an older legacy model if supplied, otherwise a rule-based eligibility flag as a last resort. This means the model quality is designed to improve automatically as real usage data accumulates, without needing a rebuild of the pipeline.
- Each profile is converted into the same standardised feature set described in Step 3, so the features used at training time and at request time are guaranteed to match.
- The ranking model and the adoption model are both LightGBM-based, trained with fixed, documented hyperparameters, and the training run produces a versioned bundle of artefacts (model files, feature metadata, a manifest, and a version string) so any deployed model can be traced back to exactly how it was produced.

---

## 4. What the taxpayer and auditor actually see (the dashboard)

The frontend takes the user through a clear sequence of screens:

1. **Sign up / log in** — separate flows for taxpayers and for an auditor role.
2. **Financial intake / profile management** — taxpayers fill in their profile; auditors can create, view, and edit any profile.
3. **Recommendations** — three views over the same underlying strategies: ranking-only, hybrid (ranking + retrieval blended), and retrieval-only, so the different approaches can be compared side by side.
4. **Adoption evidence** — the trend-consistency verdict from Step 5, shown as charts and a plain-language narrative.
5. **Explain** — the SHAP-based reasoning behind a recommendation.
6. **Impact** — the Monte Carlo simulation screen, with adjustable assumptions and the fan-chart outputs.
7. **Compare** — side-by-side comparison of multiple strategies.

---

## 5. What is deliberately marked as a limitation, not hidden

Being upfront about these points is part of the design, and worth stating clearly in a supervision discussion:

- **Authentication is prototype-grade.** Passwords are currently stored in plain text and there is a single hardcoded auditor account. This was a conscious sequencing decision — a "security phase" was planned for later — and is documented in the code itself, not something to claim as production-ready.
- **The adoption model's training labels are a proxy**, not confirmed real-world behaviour, wherever real feedback data isn't yet available. The training script is explicit about which of the three label sources was used for a given run.
- **There is a suspected circularity** in the ranking model's offline evaluation: because both the training labels and the evaluation labels are ultimately derived from the same rule engine, the "near-ceiling" evaluation scores may be flattering rather than a genuine measure of real-world performance. This is flagged, not resolved, in the project's own documentation.
- **Six of the eight behavioural questions do not yet influence recommendations** — they are captured for potential future use.
- **Financial history used for the evidence check is synthetic**, generated deterministically from each profile's current snapshot rather than being genuine multi-year records, because real longitudinal data isn't available.
- A **database migration branching gap** exists (two migration "heads" haven't been merged) — a known, unaddressed technical debt item rather than an active bug.

---

## 6. One-paragraph summary for the supervisor

> The component takes a taxpayer's financial profile, converts it into a standard set of features using a shared deterministic tax-rules engine, then ranks candidate tax strategies with a learning-to-rank model, estimates how likely the taxpayer is to adopt each one with a separate classifier, and blends that with a simple text-retrieval step for a final hybrid recommendation. Before showing a strategy as "workable", the system independently checks whether the taxpayer's own financial trend supports the model's confidence, and keeps that check visibly separate from the model's own number. Taxpayers can then run a Monte Carlo simulation to see a realistic range of outcomes over time, rather than one falsely precise figure, and every ranking decision can be explained via SHAP. All tax arithmetic is handled by one deterministic rules engine, kept deliberately separate from the machine learning components, so results remain traceable. Known limitations — proxy training labels, prototype authentication, and a suspected evaluation circularity — are documented rather than concealed.

---

*Confidence note (for internal use, not for the supervisor deck): all claims above are drawn directly from reading the relevant source files (models, migrations, routers, services, the training script) and cross-checked against the two existing project docs, which describe the same architecture consistently. No performance figures (accuracy, precision, etc.) are quoted anywhere in this document because none were found recorded in the codebase — stating a number here would be fabrication.*
