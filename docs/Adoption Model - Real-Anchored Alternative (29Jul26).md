# Adoption Model — A Real-Data-Anchored Alternative

## Why the previous answer won't work here

If your panel has already rejected "we used synthetic/simulated data because real data isn't accessible" once, saying a more sophisticated version of the same sentence again will likely get the same reaction — the issue isn't the wording, it's that the underlying evidence is still zero real data. You need the model to be **anchored to something real**, even if it's not individual taxpayer records.

Good news: you don't need individual-level private data to fix this. You need **published, legally public statistics** that describe real financial behaviour in Sri Lanka (or comparable markets), used to *calibrate* your simulation instead of inventing its parameters from theory alone. That's a real methodological upgrade, not a rebrand.

## The core idea

Instead of: *"We simulated adoption behaviour based on theory"* (rejected)

Say and do: *"We calibrated our adoption behaviour model against real, publicly available statistics on financial product uptake and savings behaviour in Sri Lanka, so our simulated adoption rates match observed real-world patterns, even though we don't have individual-level taxpayer records."*

This is a genuinely different (and stronger) claim, because it's checkable — you can point to a real source for a real number.

## Where to get real, legal, public numbers

You will not get "did person X adopt tax strategy Y" — that's the private data you correctly can't access. But you *can* get real aggregate statistics that describe similar behaviour, for example:

- **Central Bank of Sri Lanka** annual reports / Financial System Stability Reviews — household savings rates, EPF/ETF participation rates, insurance penetration rates.
- **Department of Census and Statistics, Sri Lanka** — Household Income and Expenditure Survey (HIES) — real income distributions, savings patterns, debt levels by income bracket.
- **World Bank Global Findex Database** — financial inclusion statistics for Sri Lanka: % of adults with savings accounts, % using formal credit, % saving for old age, broken down by income group. This is one of the most useful sources for adoption-style percentages.
- **IRD Annual Performance Reports** (if published) — aggregate statistics on how many taxpayers claim specific reliefs/deductions, if available — this would be the single most directly relevant number if you can find it.
- **Insurance Regulatory Commission of Sri Lanka** — life insurance penetration rates (relevant since insurance premiums are a real deduction category in your profile).

Even 3–5 solid real statistics (e.g. "X% of Sri Lankan formal-sector employees hold EPF/ETF savings," "Y% of adults save for retirement," "insurance penetration is Z%") are enough to anchor your simulation credibly.

## How to use these numbers concretely

1. **Pick your top 4–6 strategies** (the ones your catalogue already generates).
2. **For each, find or estimate the closest real statistic** describing how many people in Sri Lanka actually do something similar (e.g., for a "claim EPF-linked relief" strategy, use the real EPF participation rate by income bracket from HIES/Central Bank data).
3. **Calibrate your simulator so its overall adoption rate, by income bracket, roughly matches these real percentages** — instead of picking behavioural weights arbitrarily. Your synthetic simulator (from the earlier plan) still uses behavioural factors like risk tolerance and liquidity, but now the *overall level* it produces is checked against a real number, not invented.
4. **Explicitly cite the source for each calibration point** in your report and slides — a table like:

| Strategy type | Real-world statistic used | Source | How it calibrated the model |
|---|---|---|---|
| EPF/ETF-linked relief | ~X% of formal employees have EPF | Central Bank / HIES | Baseline adoption rate for this strategy category set to match X% |
| Insurance premium relief | Insurance penetration ~Y% | Insurance Regulatory Commission | Baseline adoption weighted down for lower-income brackets accordingly |
| ... | ... | ... | ... |

## What to say to the panel now

> "We don't have access to individual taxpayer adoption records, which is a legal privacy constraint — but instead of relying purely on theoretical assumptions, we calibrated our adoption model against real, published national statistics — [name 2–3 actual sources you used] — so that our model's overall adoption patterns are grounded in real observed financial behaviour in Sri Lanka, not just assumptions. Individual predictions are still necessarily model-based, but the model's baseline behaviour is evidence-anchored."

This directly answers their earlier "domain knowledge" feedback too — pulling in Central Bank/Census/Findex data is exactly the kind of domain grounding they're asking for, and it's a stronger, more specific answer than the previous one.

## If you can't find a real statistic for a specific strategy

Be honest about which parts are calibrated and which are still assumption-based — don't imply everything is anchored if only part is. Say something like: "We anchored the strategies where public data exists (X, Y); for strategy Z, no comparable public statistic was available, so we used the behavioural-theory approach as a fallback, which we note as a limitation." Partial grounding, clearly labelled, is far more credible than either "no data" or an overclaim.

## Realistic effort for 3 weeks

- Finding 3–5 usable public statistics: a few hours of searching Central Bank / Census / World Bank Findex publications (these are public PDFs/dashboards, no access barrier).
- Adjusting your simulator's baseline numbers to match them: small code change to the behaviour simulator from the earlier plan.
- Building the source-citation table: under an hour once statistics are found.

This fits inside Week 1 of your existing PP2 plan and directly strengthens the "domain knowledge" answer they're expecting alongside it.

## One-line summary

Don't just describe your synthetic behaviour better — anchor its baseline numbers to real, publicly available Sri Lankan financial statistics (Central Bank, Census HIES, World Bank Findex, insurance regulator), cite the sources explicitly, and be upfront about which parts are grounded versus still assumption-based.
