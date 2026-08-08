# How and Why the User Profile Features Were Selected

This is your answer to the panel's question: *"How were the features for the user profile selected, and why these ones?"*

## The short answer to give the panel

> "Each field in the user profile was selected because it's required by one of three sources: (1) it's a variable that Sri Lankan tax law actually uses to determine eligibility for a specific relief or deduction, (2) it's a factor needed to judge whether a strategy is financially feasible for that person, or (3) it's a behavioural factor that established financial-behaviour research links to whether someone would actually adopt a recommendation. Nothing in the profile was added arbitrarily — every field maps to a specific downstream use in the strategy generation, feasibility check, or adoption model."

This turns the answer from "we picked things that seemed relevant" into "we followed a repeatable method," which is exactly what a panel wants to hear.

## The three-source method (explain this process, not just the list)

### Source 1 — Legal necessity (from the Inland Revenue Act & IRD guides)
Method: go through every deduction/relief/exemption in the Inland Revenue Act No. 24 of 2017 and the IRD's annual filing/APIT guides, and ask "what information does the IRD need to know about a person to determine if this relief applies to them?" Each answer becomes a required profile field.

Examples:
- Life insurance premium relief → requires `life_insurance_premium_annual_lkr`
- EPF/ETF-linked considerations → requires `epf_balance_lkr`, `etf_balance_lkr`
- Charitable donation relief → requires `donations_annual_lkr`
- Housing loan interest relief → requires `home_loan_interest_annual_lkr`
- Income tax bracket/liability itself → requires `gross_monthly_income_lkr`, `income_sources_json`, `occupation` (since tax treatment differs by income source type — employment vs. business vs. investment income)

### Source 2 — Financial feasibility (can this person actually do this, not just qualify for it)
Method: for each strategy category, ask "even if someone is legally eligible, what financial condition would make this actually workable for them versus impossible or risky?" This produces the feasibility-related fields.

Examples:
- `liquid_savings_lkr`, `monthly_expenses_lkr`, `monthly_debt_service_lkr`, `total_debt_lkr`, `debt_to_income` → needed to judge whether locking money into a longer-term saving/investment strategy is realistic, or whether someone is already financially stretched.
- `disposable_income_monthly_lkr`, `savings_rate` → derived indicators of how much spare capacity someone actually has each month.

### Source 3 — Behavioural adoption factors (grounded in financial-behaviour literature)
Method: your proposal itself (and cited sources [5],[6]) argue that adoption of a financial strategy depends on more than eligibility — it depends on personal risk tolerance, time horizon, and stability. This is also supported by broader behavioural-economics research (e.g. prospect theory — people weigh potential losses/lock-in risk more heavily than equivalent gains) and technology/strategy-adoption literature (adoption depends on perceived fit with a person's existing habits, not just theoretical benefit).

Examples:
- `risk_tolerance` → directly determines whether a person would accept any strategy involving investment risk.
- `investment_horizon_years` → determines whether long-lock-in strategies (e.g. long-term investment-linked relief) are realistic for this person.
- `years_employed`, `age_years`, `dependents`, `marital_status` → stability/life-stage indicators used in behavioural-economics literature as proxies for financial caution and planning horizon (e.g. someone with dependents and short employment tenure behaves more conservatively than a long-tenured single earner with no dependents, even at the same income level).

## Full feature justification table

| Feature | Why it's in the profile | Source of justification |
|---|---|---|
| `gross_monthly_income_lkr` | Determines tax bracket and eligibility thresholds | Legal (Inland Revenue Act, APIT guidelines) |
| `income_sources_json` | Different income types (employment/business/investment) are taxed differently | Legal (Inland Revenue Act) |
| `occupation` | Determines applicable relief category (e.g. business vs. employee reliefs differ) | Legal (IRD guides) |
| `dependents` | Some reliefs/considerations vary with dependents; also a behavioural stability indicator | Legal + Behavioural |
| `marital_status`, `age_years`, `years_employed` | Life-stage/stability indicators affecting risk capacity and planning horizon | Behavioural (financial planning literature) |
| `monthly_expenses_lkr`, `monthly_debt_service_lkr`, `total_debt_lkr`, `debt_to_income` | Determines whether a strategy is financially feasible, not just legal | Feasibility |
| `liquid_savings_lkr`, `disposable_income_monthly_lkr`, `savings_rate` | Determines spare financial capacity to adopt a strategy | Feasibility |
| `existing_investments_lkr` | Determines whether investment-linked reliefs are already partly utilised | Legal + Feasibility |
| `epf_balance_lkr`, `etf_balance_lkr` | Directly tied to EPF/ETF-linked relief eligibility | Legal |
| `health_insurance`, `life_insurance_premium_annual_lkr` | Directly tied to insurance premium relief | Legal |
| `home_loan_interest_annual_lkr` | Directly tied to housing loan interest relief | Legal |
| `donations_annual_lkr` | Directly tied to charitable donation relief | Legal |
| `risk_tolerance` | Determines whether risk-bearing strategies would be adopted | Behavioural |
| `investment_horizon_years` | Determines whether long-lock-in strategies are realistic | Behavioural |
| `district` | Used for demographic realism in the synthetic dataset (not a tax/behavioural driver) | Data realism, not decision-relevant — flag this honestly (see below) |

## One honest caveat to mention proactively

A couple of fields (like `district`, `gender`, `full_name`) exist mainly to make the *synthetic dataset* demographically realistic (so the 25,000 generated profiles resemble a real population spread across Sri Lanka), rather than because they directly drive a tax rule or behavioural prediction. It's worth saying this plainly if asked — e.g., "district and gender were included for realistic synthetic population generation; they are not currently used as inputs to the ranking or adoption models." This kind of honesty (labelling which fields are decision-relevant versus dataset-realism-only) is exactly the sort of rigour the panel is looking for, and it's better to volunteer it than have them find it.

## How to present this at PP2

1. State the method first (the three sources), not the list first — this shows process before content.
2. Show the table (or a condensed version of it) as one slide.
3. Proactively mention the district/demographic-only fields caveat before they ask — it pre-empts a "why is this here" gotcha question and demonstrates self-awareness.
4. If pressed on a specific field, you now have a one-sentence justification ready for every single one.

## One-line summary

Every feature was selected because it's required by one of three sources: it drives a specific IRD tax rule, it determines financial feasibility, or it's a behavioural factor grounded in financial-planning/behavioural-economics literature — and a few fields exist purely for realistic synthetic data generation, which you should state upfront rather than have discovered.
