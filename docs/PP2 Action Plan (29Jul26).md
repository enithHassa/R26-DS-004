# PP2 Action Plan — 3 Weeks to Completed Version

This combines your panel's Progress Presentation 1 (PP1) feedback with the technical gaps identified earlier, into one prioritized plan for Progress Presentation 2 (PP2).

## What the panel actually said (decoded)

> "Improve communication. Need to show how the output exactly [relates] to the user's profile. How were the features for user profile selected? Need to get the required domain knowledge."

Breaking this into three distinct concerns:

1. **Traceability gap**: When the panel saw a recommendation come out, they couldn't see *why* — which specific profile inputs (income, risk tolerance, savings, etc.) led to that specific ranked output. The system may be doing this internally, but you didn't demonstrate the connection clearly.
2. **Feature justification gap**: You picked specific fields for the user profile (income, expenses, EPF/ETF balance, risk tolerance, etc.) — the panel wants to know *why these fields and not others*, and what evidence or reasoning backs that choice.
3. **Domain knowledge gap**: This is the most serious one. The panel is signalling that your explanations sounded like "I built an ML pipeline" rather than "I understand Sri Lankan tax planning and financial advisory well enough to justify what this system does." You need to visibly ground the project in real tax rules, real financial planning practice, and ideally some expert input — not just synthetic data and models.

This is a communication and justification problem more than a coding problem — a supervisor/panel needs to see *understanding*, not just working software.

## How this connects to what's already built

Good news: you don't need to build new functionality to answer most of this — you need to **expose and explain what your system is already doing**, and **document the reasoning behind decisions that were made informally**. This is compatible with the technical priorities already identified (see "Recommendation Component - What's Left To Do" doc) — in fact, doing them properly will also answer the panel's questions.

## 3-Week Plan

### Week 1 — Domain grounding + feature justification (answers panel points 2 & 3)

This is the most important week. Do this before touching more code.

- **Re-read your own sources.** Your proposal already cites the Inland Revenue Act No. 24 of 2017, IRD filing guides, and APIT guidelines [1]-[4]. Go back to these (or the current 2024/25 IRD guides) and for *each* field in your user profile, write one sentence: "This field exists because tax rule/relief X depends on it." If a field can't be justified this way, either justify it differently (e.g. "used for adoption behaviour modelling, not tax calculation") or consider dropping it.
- **Build a simple feature justification table.** Columns: Feature name → Why it's needed → Which tax rule or strategy it affects → Source (which IRD rule/section, or "behavioural assumption"). This single table will directly answer "how were the features selected" in front of the panel.
- **Get at least some real domain input if at all possible.** Options, in order of value:
  - Ask your supervisor (Dr. Lakmini) or co-supervisor (Ms. Adya) directly whether they know a tax consultant or accountant you could do a short 20–30 minute informal chat with, even just to sanity-check your strategy catalogue and feature list.
  - If no expert access is possible, at minimum cross-check your strategy catalogue (`rules/strategy_catalog.yaml`) line-by-line against the actual IRD guide text, and note in your report exactly which clauses/sections back each strategy. This shows rigour even without an interview.
- **Write this up as a short section** ("Domain Grounding of Profile Features and Tax Strategies") to include in your report and to speak from during PP2 — this is your direct answer to feedback point 3.

### Week 2 — Traceability: make the input→output link visible (answers panel point 1)

- **Add/strengthen an explanation view** that, for a given recommendation, shows in plain language: "You were recommended Strategy X because: your risk tolerance is Y, your liquid savings is Z, your income puts you in tax bracket W, and this strategy's eligibility/feasibility check passed for these reasons." If your explanation panel already exists (it does, per the current-state review), the job here is to make sure it's actually *specific* per user/strategy, not generic boilerplate — check this carefully.
- **Prepare a live or recorded walkthrough** for PP2: pick one synthetic persona (e.g. a mid-career employee with moderate savings), show their profile, show the generated strategies, show the ranked list, and — critically — narrate *why* the top strategy ranks where it does, pointing at specific profile values. This single demo directly answers feedback point 1 in the most convincing way possible: showing, not just telling.
- **Consider a simple "feature importance" or "reasoning trace" visual** — even something as simple as a bar showing which factors (tax savings / adoption probability / risk / feasibility) contributed most to a given strategy's score would visibly demonstrate the input-to-output connection.

### Week 3 — Tighten the technical honesty issues + rehearse

This week, fold in the previously identified technical priorities (from "What's Left To Do"), focused on what's most likely to come up given this feedback:

- **Fix or clearly caveat the evaluation leakage issue** (ranking model tested against labels derived from the same rule it trained on). Given the panel is already scrutinising your rigour, this is likely to come up if you show accuracy numbers — be ready with an honest explanation and, ideally, a fixed version.
- **Relabel the adoption model honestly** as an eligibility-based proxy (documentation-only fix is enough if time is short) — ties directly into "domain knowledge," since it shows you understand the difference between a real behavioural model and a rule-derived stand-in.
- **Do the full end-to-end walkthrough** (already planned in Week 2) using at least 2–3 different personas so you're not caught off guard by a panel question about a different type of user.
- **Rehearse the presentation itself.** Given "improve communication" was explicit feedback, plan the PP2 talk structure in advance:
  1. One-sentence problem statement (why generic tax advice fails)
  2. One slide: profile features + why each was chosen (Week 1 table)
  3. Live/recorded demo: one persona, full flow, narrated (Week 2 output)
  4. One slide: honest limitations (synthetic data, adoption proxy, evaluation caveat)
  5. Stop there — don't over-explain the ML internals unless asked.

## Suggested weekly checklist

- [ ] Week 1: Feature justification table completed, cross-checked against IRD sources
- [ ] Week 1: At least attempted contact with supervisor/co-supervisor about domain expert access
- [ ] Week 1: Short "Domain Grounding" write-up drafted
- [ ] Week 2: Explanation panel verified to give specific, non-generic reasoning per recommendation
- [ ] Week 2: One full persona walkthrough demo prepared (live or recorded)
- [ ] Week 2: Simple visual showing what drove a recommendation's score
- [ ] Week 3: Evaluation leakage issue fixed or clearly caveated
- [ ] Week 3: Adoption model relabelled/documented as proxy
- [ ] Week 3: 2–3 persona walkthroughs tested for robustness
- [ ] Week 3: Presentation structure rehearsed, timed, and kept tight

## One-line summary

The panel isn't asking you to rebuild the system — they're asking you to *prove you understand it and the tax domain behind it*, and to *show* the input-to-output connection instead of describing it abstractly. Spend Week 1 on domain justification, Week 2 on making the reasoning visible, and Week 3 on tightening honesty gaps and rehearsing a tight, evidence-led presentation.
