# Predictive Impact Modeling Engine — Explained Simply

This explains the **Predictive Impact** page (`/impact`, the auditor-facing "Financial Impact" screen) for someone with no tax background. It describes what the page actually does today, based on the current code — nothing here is a future promise.

## In one sentence

You pick a person's financial profile and (optionally) one tax-saving strategy, and the tool plays out thousands of "possible futures" for that person's money over the next several years, then shows you the range of outcomes — not a single guess, but a realistic spread of what could happen.

## Why not just calculate one answer?

Nobody knows exactly how much someone's salary will grow, how high inflation will run, or how investments will perform over the next 10–20 years. Rather than pretending to know, this tool:

1. Makes reasonable assumptions about *how much these things typically vary* (e.g. "salary tends to grow around 6% a year, give or take").
2. Runs the whole scenario forward **many times** (each "run" is called a **path**), each time letting those uncertain numbers land slightly differently — like rolling dice thousands of times.
3. Looks at all those runs together to answer: "In the middle of the pack, what usually happens? In a bad run, how bad does it get? In a good run, how good does it get?"

This technique is called a **Monte Carlo simulation** — the name comes from a casino, because it's fundamentally about many random rolls.

## The setup you choose, in plain terms

| Control on screen | What it means, plainly |
|---|---|
| **Profile** | Whose finances you're simulating (income, expenses, savings, debts, etc.) |
| **Strategy (optional)** | A specific tax-saving move to test — e.g. topping up a retirement fund. Leave blank to see the "do nothing" baseline only |
| **Horizon (years)** | How many years into the future to look — 5, 10, 15, or 20 |
| **Monte Carlo paths** | How many "possible futures" to simulate — more paths = a smoother, more reliable spread of outcomes, but takes a little longer to compute |
| **Salary growth (mean)** | The assumed *typical* yearly pay rise — the simulation still varies this randomly path to path, this just sets the average it varies around |
| **Inflation (mean)** | The assumed *typical* yearly rise in the cost of living |
| **Investment return (mean)** | The assumed *typical* yearly growth on savings/investments |
| **Adoption success probability** | How likely it is the person actually follows through on the strategy every year (life gets in the way sometimes) |

## What comes back, in plain terms

**The four summary numbers** (same ones explained on the taxpayer-facing side, in auditor form here):
- **Expected total tax savings** — the average extra money kept, strategy vs doing nothing.
- **Expected net worth (at the end of the horizon)** — average total savings and investments after N years.
- **Probability of net gain** — out of all the simulated futures, in what share of them did the strategy actually leave the person better off than doing nothing?
- **Value at risk (P10)** — a "how bad could it realistically get" number: in the worst 10% of simulated futures, this is roughly how much worse off the person is.

**The charts:**
- **Net worth fan chart** and **Tax liability fan chart** — for each future year, shows three lines: the middle-of-the-road outcome (**P50**, median), and the boundaries of the realistic range (**P10** = pessimistic edge, **P90** = optimistic edge). The shaded band between them is "here's where most outcomes land."
- **Tax liability over time** — a simpler line comparing the *typical* (median) yearly tax bill with vs without the strategy.
- **Net worth at horizon (distribution)** — a bar chart snapshot of just the final year, showing the P10/P50/P90 net worth side by side so you can see the spread at a glance.
- **Year-by-year table** — the actual median numbers per year (salary, tax, savings, net worth), baseline vs with-strategy.

**"Why the model ranked this strategy" (Explain panel):** a separate, related feature — it doesn't run the simulation again, but explains *why the recommendation engine* scored this strategy the way it did, by showing which factors about the profile pushed the score up or down (using a technique called SHAP — think of it as "the model's reasoning, broken into contributing factors").

## What this tool is *not* claiming

- It isn't predicting the future with certainty — it's showing a realistic range based on the assumptions you set.
- The "mean" growth/inflation/return numbers are assumptions you control, not guaranteed facts — changing them changes every result.
- A wider gap between P10 and P90 means more uncertainty, not a mistake — some financial situations are just more volatile than others.

## Quick glossary

| Term | Plain meaning |
|---|---|
| Path | One full simulated run from now to the end of the horizon |
| Median (P50) | The middle result — half the simulated futures did better, half did worse |
| P10 | The pessimistic edge — only 10% of futures were worse than this |
| P90 | The optimistic edge — only 10% of futures were better than this |
| Baseline | What happens if the person does nothing differently |
| Strategy path | What happens if the person adopts the chosen strategy |
| Horizon | How many years ahead you're looking |
