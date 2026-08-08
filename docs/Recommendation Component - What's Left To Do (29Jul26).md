# What To Change / Complete To Reach a Final Version

This is a practical to-do list for your "Personalized Recommendation & Predictive Impact Modeling Engine" component, based on comparing what's built against what a strong final submission needs. Read alongside **"Recommendation Component Current State (29Jul26).md"**.

Nothing here means "start over" — the core system works. This is about tightening honesty, proving the model actually works, and polishing presentation.

## Priority 1 — Fix the "grading with the answer key" problem

**The issue:** Right now, both the ranking model's training labels *and* the labels used to check if it's doing a good job come from the same rule-based formula. That's like a teacher writing the exam questions from the answer sheet the student already has — of course the score looks perfect (~99.9%).

**What to do:**
- Create a separate, independent way of deciding "what's actually the best strategy for this synthetic person" — ideally something that isn't just the same eligibility rule reused. For example: add some randomness or an alternative expert-style scoring logic for a held-out test set, so the model is tested against something it didn't train on.
- Re-run evaluation with this independent check and report the *real* accuracy — even if it's lower, a lower-but-honest number is far more credible to examiners than a suspicious 99.9%.
- In your final report, explicitly explain this limitation and what you did about it. Examiners respond well to "we noticed this issue and addressed it" — it shows understanding, not just running code.

## Priority 2 — Be explicit about the adoption model being a proxy

**The issue:** The "adoption probability" model doesn't actually learn from real people adopting strategies — it's currently mostly re-deriving eligibility rules.

**What to do (pick based on time available):**
- **Minimum (documentation only):** Clearly relabel this in your dashboard/report as "Eligibility-Weighted Adoption Proxy" rather than implying it's learned behaviour. Add one paragraph in your report methodology explaining why (no real data available — consistent with your proposal's own justification).
- **Better (some extra modelling work):** Add a synthetic "behavioural" layer — simulate plausible adoption behaviour using believable rules (e.g., people with low liquid savings are less likely to adopt investment-locking strategies; risk-averse people are less likely to adopt high-risk strategies) that's independent of the eligibility engine, then train the adoption classifier on *that* instead. This gets you closer to the spirit of your proposal (behaviour-aware prediction) without needing real data.

## Priority 3 — Clean up git history housekeeping

**The issue:** One commit accidentally included a Python virtual environment folder and an unrelated teammate's dashboard scaffold, bundled in with your real component work.

**What to do:**
- Remove the accidentally-committed virtual environment files from version control and add them to `.gitignore` if not already there.
- This is a small, low-risk cleanup — but a supervisor glancing at your commit history will notice a 300-file commit and wonder what happened. A quick fix now avoids an awkward question later.

## Priority 4 — Validate the whole thing end-to-end, at least once, "as a user would"

**The issue:** There's no clear evidence anyone has walked through the full flow (create profile → generate strategies → get ranked recommendations → view impact simulation → compare) as a real user would, start to finish.

**What to do:**
- Run through the complete flow yourself in the actual UI (not just isolated backend tests), using 2–3 different synthetic "personas" (e.g., a young employee, a retiree, a business owner) that represent very different financial situations.
- Check that the recommendations make sense — do the top-ranked strategies look sensible for that persona? Does the impact chart look plausible?
- Screenshot or write up this walkthrough for your final report/demo — examiners want to see the system working live, not just described in text.

## Priority 5 — Decide how much to say about "not real data"

**The issue:** Everything (data, adoption behaviour, evaluation) is built on synthetic data. This is already justified in your proposal (privacy constraints), so it's not a problem — but it needs consistent framing throughout your report.

**What to do:**
- In every section where you report a number (accuracy, tax savings improvement, ranking quality), add a short caveat: "measured on synthetic data; not yet validated against real taxpayers."
- Consider adding a short "Threats to Validity" or "Limitations" subsection near your evaluation chapter — this is standard academic practice and shows maturity rather than weakening your work.

## Priority 6 — Polish, if time remains

These aren't urgent, but would strengthen the final version:
- Double-check the explanation feature (the "why was this recommended" panel) gives genuinely different explanations for different strategies/users, rather than generic text.
- Make sure the multi-objective scoring weights (tax savings vs. adoption vs. risk) are justified somewhere in your report — even a simple sentence like "we weighted tax savings highest because it's the primary user goal" is enough; examiners will likely ask why these particular weights were chosen.
- If time allows, a short sensitivity check: show what happens to the top-ranked recommendation if you change the scoring weights — this demonstrates you understand your own system, not just that it runs.

## Suggested order of work (if time is limited)

1. Priority 1 (fix evaluation leakage) — most likely to be questioned in a viva/demo.
2. Priority 5 (consistent limitations framing) — cheap, high credibility payoff.
3. Priority 4 (end-to-end walkthrough) — you need this for your demo anyway.
4. Priority 2 (adoption proxy — at least the documentation-only version) — cheap and important for honesty.
5. Priority 3 (git cleanup) — quick, low risk.
6. Priority 6 (polish) — only if time remains.

## One-line summary

Your system is functionally complete — the main remaining work is proving it's *actually* good (not just self-graded) and being clear and upfront about where synthetic data and proxy labels stand in for things you couldn't measure directly.
