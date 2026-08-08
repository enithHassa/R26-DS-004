# Personalized Recommendation & Predictive Impact Modeling Engine — Explained from Scratch

This is a plain-English walkthrough of your component (R26-DS-004), written as if you know nothing about it yet. It follows your project proposal document.

## 1. What problem are we solving?

In Sri Lanka, salaried people pay income tax (mostly via APIT, deducted automatically from salary) but must still file an annual tax return with the Inland Revenue Department (IRD).

Most people don't know how to legally reduce their tax bill, because:
- Tax rules are complicated (deductions, exemptions, investment reliefs).
- Existing tools (IRD portal, tax calculators) only calculate tax — they don't tell you *what to do* to pay less.
- Even where advice exists, it's generic ("invest in X to get a deduction") and ignores whether *you specifically* can or would actually do that.

**Confidence: high** — this is stated directly and repeatedly in the proposal's background section.

## 2. Why generic tax advice fails

Two taxpayers with the same income can have very different lives:
- One has spare cash and is comfortable locking money into a long-term investment for a tax break.
- Another lives pay cheque to pay cheque and cannot realistically do that, even if it's "technically optimal."

A traditional advisory tool would recommend the same "best" strategy to both people — and the second person would simply never follow it. The proposal calls this the gap between a *theoretically optimal* strategy and a *practically adopted* one.

## 3. What your component actually does

Your component — the **Personalized Recommendation & Predictive Impact Modeling Engine** — is the "brain" that:
1. Looks at a person's financial situation.
2. Generates several possible tax-saving strategies.
3. Predicts whether that specific person would actually follow through on each strategy.
4. Ranks the strategies from most to least suitable for that person.
5. Estimates what each strategy would do to their finances years into the future.

In short: instead of one generic answer, the user gets a **personally ranked shortlist**, each with a plain-English "here's what this means for your future" projection.

## 4. The four building blocks

### 4.1 User Financial Profile Module
Collects the raw inputs about the person:
- Income sources, salary history
- Eligible tax deductions
- Investment preferences
- Risk tolerance (cautious vs. willing to take risks)

Think of this as building a structured "financial fingerprint" of the user — this feeds everything else.

### 4.2 Tax Strategy Generation Module
Takes that fingerprint and, using Sri Lankan tax rules, generates a list of *candidate* strategies the person could use — e.g. claiming a specific deduction, shifting how income is allocated, using a tax-exempt investment. This is rule-based (built from actual tax law), not yet personalized — it just produces the *menu of options*.

### 4.3 Recommendation Ranking Engine (your core focus, alongside 4.4)
This is where personalization happens. It takes the menu of candidate strategies and puts them in order of "best fit for this person," using a machine learning approach called **learning-to-rank** (specifically, an algorithm called **LambdaMART**).

It ranks strategies by combining:
- Expected tax savings (how much money it saves)
- **Adoption probability** — will this person actually do it? (see below)
- Financial feasibility (can they afford it / does it fit their liquidity?)
- Risk level

### 4.4 Predictive Impact Modeling Engine (the other core focus — flagged in the proposal as the "primary research component")
This estimates what adopting a strategy would mean for the person's finances *years from now*, not just this year. It does this using:
- A **salary forecast model** — projecting how their income might grow.
- **Monte Carlo simulation** — running many randomized "what if" scenarios (e.g., varying salary growth, investment returns) to see a range of possible future outcomes, rather than a single guess. This is how the system produces statements like "there's a good chance this strategy saves you X over 5 years, with some risk of Y."

### 4.5 Decision Support Dashboard
The user-facing screen that shows the ranked strategies, their predicted savings, and confidence levels, in a way a non-expert can understand.

## 5. The "adoption probability model" — a key idea

This is arguably the most novel part of your component. It's a separate small ML model whose only job is: *given this person's income, financial flexibility, behavioural patterns, and risk tolerance, how likely are they to actually adopt this particular strategy?*

That probability score then gets folded into the ranking (4.3), so a strategy that saves slightly less tax but that the person will actually do can outrank a "perfect on paper" strategy they'll ignore.

## 6. The multi-objective scoring function

Rather than ranking purely by "which strategy saves the most tax," the system combines multiple factors into one score:

```
Score = f(Tax Savings, Adoption Probability, Risk Level)
```

This is why it's called "multi-objective" — it's balancing several competing goals at once, not optimising for a single number.

## 7. Why this hasn't been done before (the research gap)

The proposal argues that existing systems typically do only one of these things, never all combined:
- Tax portals: file/calculate tax, no recommendations at all.
- Academic tax-compliance ML research: focuses on catching fraud/non-compliance, not helping the taxpayer.
- Recommendation systems (learning-to-rank): common in e-commerce, rare in tax.
- Financial forecasting (Monte Carlo): common in investing, rare in tax advisory.

Your project's novelty is stitching all four together into one taxpayer-facing engine.

**Confidence: medium** — this is the proposal's own novelty claim; it hasn't been independently verified against the full literature by me.

## 8. What data will be used

Because real taxpayer financial data is private and legally restricted, the whole system will be built and tested on **synthetic (simulated) data** — fake but realistic financial profiles and behaviour patterns generated for the purpose of training/testing the models. No real personal data is used.

## 9. How success will be measured

The proposal lists these evaluation angles:
- **Recommendation accuracy** — are the suggested strategies actually correct/valid?
- **Prediction accuracy** — how good is the adoption-probability model?
- **Expected tax savings** — compared to a plain rule-based calculator, does this system find more savings?
- **Ranking quality** (NDCG / MAP — standard metrics for "did the best options end up near the top of the list?")
- **Simulation reliability** — do the Monte Carlo financial projections hold up?

## 10. Tools you'll actually be using

| Purpose | Tool |
|---|---|
| Language | Python |
| ML models | Scikit-learn, TensorFlow, PyTorch |
| Data handling | Pandas, NumPy |
| Backend API | FastAPI |
| Database | MongoDB / PostgreSQL |
| Dashboard | React / Streamlit |
| Experiments | Jupyter Notebook |

## 11. One-sentence summary

Your component takes a person's finances, generates possible legal tax-saving moves, predicts which ones they'd realistically follow through on, ranks them accordingly, and shows them — with future-looking projections — what each choice would mean for their money down the road.

---
*Source: Project Proposal Report, R26-DS-004, Pihillegedara S.N.M — IT22238580, March 2026.*
