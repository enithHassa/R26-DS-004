# Completing the Adoption Probability Model Without Real Data

## The core problem, restated simply

Right now, your "adoption probability" model doesn't predict adoption — it mostly re-predicts *eligibility* (whether a strategy is technically available to someone), because eligibility is the only label available. That's not a real behavioural model yet.

You can't get real taxpayer adoption records (privacy-restricted — already justified in your proposal). But **"no real data" is not something you need to confess as a limitation and stop there** — it's a well-known constraint in this kind of research, and there's a standard, respectable way to handle it: **build an independent, literature-grounded synthetic behaviour simulator**, and train your adoption model on *that* instead of on eligibility. This is different from what you have now because it introduces genuine behavioural reasoning that doesn't just echo the rule engine.

This is not an excuse — it's a method. Here's how to do it and how to present it.

## Why this is legitimate (what to say to the panel)

Tell the panel this, directly: *"Since real adoption data isn't accessible due to privacy restrictions, we modelled adoption behaviour using established behavioural-economics and technology-adoption theory, simulated it independently of the eligibility engine, and trained/evaluated our classifier against that simulated ground truth."*

This is a recognised technique called **synthetic behavioural simulation** (sometimes called agent-based or rule-grounded synthetic labelling), commonly used in fintech/tax research precisely because real adoption data is sensitive. Panels respect this far more than an unexplained gap, because it shows you understood the problem and engineered around it deliberately.

You can lean on real, citable theory to justify *why* your simulated behaviour looks the way it does:
- **Theory of Planned Behaviour / Technology Acceptance Model** — adoption depends on perceived ease/benefit and personal capacity, not just eligibility.
- **Prospect theory (Kahneman & Tversky)** — people weigh potential losses more heavily than equivalent gains, which explains why risk-averse people under-adopt strategies with any risk, even small ones.
- **Diffusion of Innovation theory** — adoption likelihood varies by how much a strategy resembles what a person already does (a strategy close to their current financial habits is more likely adopted than a completely new behaviour).
- Your own proposal already cites general literature on financial behaviour affecting tax strategy adoption ([5], [6]) — use these as anchors too.

## Concrete build plan

### Step 1 — Design an independent "true adoption" simulator
Write a new module (e.g. `models/personalized-recommendation/adoption/behavior_simulator.py`) that computes a *simulated adoption probability* for each (user, strategy) pair using behavioural logic that is **separate from the eligibility/feasibility rule engine**. Example logic (illustrative, not final):

- Base adoption tendency reduced by **risk mismatch**: if strategy risk level > user's stated risk tolerance, apply a penalty.
- Reduced by **liquidity mismatch**: if strategy requires locking funds and user's liquid savings / debt-to-income ratio is poor, apply a penalty.
- Increased by **familiarity**: if the strategy type is similar to something already in the user's profile (e.g. already has EPF/ETF, already donates), boost adoption likelihood.
- Increased by **simplicity bias**: strategies requiring fewer steps/forms get a mild boost (reflecting real behavioural friction).
- Add **random noise** (e.g. a small Gaussian jitter) to each score before converting to a binary "adopted / not adopted" label — real behaviour is never perfectly predictable, and pure determinism would just recreate the current leakage problem in a new form.

This gives you a synthetic-but-independent label — grounded in behavioural reasoning, not just re-deriving eligibility, and not identical to your ranking engine's logic.

### Step 2 — Regenerate training data using this simulator
Re-run your synthetic profile generation pipeline, but now attach the *simulated adoption outcome* from Step 1 as the label, instead of the eligibility flag or distilled legacy-model output currently used in `scripts/train_phase4_ranking_adoption.py`.

### Step 3 — Retrain the adoption classifier on the new labels
Same model type you already have (LightGBM classifier / MultiOutputClassifier) — just swap the label source. Re-save the artifact.

### Step 4 — Hold out a validation set the model never sees during training
Evaluate the retrained model against this held-out set. Report real precision/recall/AUC — expect these to be *lower* than your old ~99% number, and that's fine, even good: it shows the model is learning genuine structure instead of memorising a rule it was given.

### Step 5 — Document the theory-to-code mapping
Make a short table: Behavioural factor → Theory/citation → How it's implemented in `behavior_simulator.py`. This is your direct evidence for the panel that this isn't guesswork.

## What to literally say if a panel member pushes back

If asked "but this is still fake data, isn't it?" — a strong, honest answer is:

> "Yes — because real taxpayer adoption records aren't accessible for privacy reasons, which is a known and accepted constraint in this research area. Rather than leaving that as an unaddressed gap, we simulated adoption behaviour using established behavioural-economics theory, independently of our rule engine, so the model has to learn genuine behavioural patterns rather than just memorising eligibility. We evaluated it on data it never saw during training, and we're transparent in our report that this is a simulated, not observed, ground truth — a standard approach in an area where real data is legally restricted."

This response does three things panels want to see: acknowledges the limitation, explains the deliberate methodological choice, and shows awareness that it's still not equivalent to real data. That combination reads as maturity, not weakness.

## Time estimate

This fits comfortably inside the "Week 1–2" work already planned in your PP2 Action Plan — the behaviour simulator itself is a few hundred lines of rule logic (similar complexity to what you've already built in `strategy_gen/evaluator.py`), and retraining reuses your existing training script with a different label source.

## One-line summary

Replace the eligibility-based adoption proxy with an independent, behaviourally-grounded synthetic simulator, train and evaluate the classifier against that instead, and present it to the panel as a deliberate, literature-backed method for handling a real data-access constraint — not as a shortcut you're hiding.
