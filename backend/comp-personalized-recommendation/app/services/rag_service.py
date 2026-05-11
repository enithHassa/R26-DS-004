"""RAG-based strategy retrieval using TF-IDF vector similarity.

Retrieval-Augmented Generation (RAG) pipeline:
  1. Index  — strategy catalog documents are vectorised with TF-IDF at startup.
  2. Retrieve — user profile is converted to a query string; cosine similarity
                selects the most semantically relevant strategies.
  3. Generate — plain-English explanation is assembled from the retrieved
                strategy document and the user's actual financial figures.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from app.config import component_settings
from app.services.profile_service import ProfileNotFoundError, compute_derived_features, get_profile
from uuid import UUID


# ---------------------------------------------------------------------------
# Strategy document builder
# ---------------------------------------------------------------------------

def _strategy_catalog_path() -> Path:
    return component_settings.COMP_RECOMMENDATION_RULES_PATH.parent / "strategy_catalog.yaml"


def _load_strategies() -> list[dict]:
    path = _strategy_catalog_path()
    with open(path, encoding="utf-8") as f:
        catalog = yaml.safe_load(f)
    return catalog.get("strategies", [])


def _strategy_to_document(s: dict) -> str:
    """Convert a strategy YAML entry into a rich text document for TF-IDF indexing."""
    parts = [
        s.get("name", ""),
        s.get("category", "").replace("_", " "),
        s.get("description", "").strip(),
    ]

    rules = s.get("eligibility_rules", {})
    for rule_list in rules.values():
        if isinstance(rule_list, list):
            for item in rule_list:
                if isinstance(item, dict):
                    if "expr" in item:
                        parts.append(item["expr"])
                    for v in item.values():
                        if isinstance(v, list):
                            for sub in v:
                                if isinstance(sub, dict) and "expr" in sub:
                                    parts.append(sub["expr"])

    formula = s.get("estimation_method", {}).get("formula_ref", "")
    parts.append(formula.strip())

    constraints = s.get("constraints", {})
    for doc in constraints.get("required_docs", []):
        parts.append(doc.replace("_", " "))

    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# TF-IDF vector store (built once per process)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _build_vector_store() -> tuple[TfidfVectorizer, Any, list[dict]]:
    strategies = _load_strategies()
    docs = [_strategy_to_document(s) for s in strategies]
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    matrix = vectorizer.fit_transform(docs)
    return vectorizer, matrix, strategies


# ---------------------------------------------------------------------------
# Profile → query text
# ---------------------------------------------------------------------------

def _age_band(age_years: int) -> str:
    bands = [(24, "18-24"), (29, "25-29"), (34, "30-34"), (39, "35-39"),
             (44, "40-44"), (49, "45-49"), (54, "50-54"), (59, "55-59"),
             (64, "60-64"), (70, "65-70")]
    for upper, label in bands:
        if age_years <= upper:
            return label
    return "70+"


def _profile_to_query(ctx: dict) -> str:
    occ = ctx.get("occupation", "")
    age = _age_band(int(ctx.get("age_years", 30)))
    risk = ctx.get("risk_tolerance", "medium")
    gmi = float(ctx.get("gross_monthly_income_lkr", 0))
    epf = float(ctx.get("epf_balance_lkr", 0))
    dti = float(ctx.get("debt_to_income", 0))
    sr = float(ctx.get("savings_rate", 0))
    life_ins = float(ctx.get("life_insurance_premium_annual_lkr", 0))
    home_loan = float(ctx.get("home_loan_interest_annual_lkr", 0))
    donations = float(ctx.get("donations_annual_lkr", 0))
    has_hi = ctx.get("has_health_insurance", False)
    yrs = int(ctx.get("years_employed", 0))
    annual_income = float(ctx.get("annual_income", gmi * 12))

    tokens = [
        f"occupation {occ}",
        f"age band {age}",
        f"risk tolerance {risk}",
        "annual income tax deduction",
    ]

    if occ == "employee":
        tokens += ["employee salary APIT withholding EPF retirement"]
    if occ in ("business_owner", "professional", "self_employed"):
        tokens += ["business expense deduction self employed professional income"]
    if life_ins > 0 or has_hi:
        tokens += ["insurance premium health life deduction relief"]
    if epf > 0:
        tokens += ["EPF voluntary top-up retirement contribution qualifying payment"]
    if yrs >= 5 and epf > 0:
        tokens += ["terminal benefit gratuity EPF retirement planning exit"]
    if home_loan > 0:
        tokens += ["home loan interest relief housing mortgage deduction"]
    if donations > 0:
        tokens += ["charitable donation deduction approved organisation"]
    if dti > 0.65 or sr < 0.05:
        tokens += ["cashflow debt stress liquidity stabilisation savings rate low"]
    if annual_income > 0:
        tokens += ["tax savings deduction taxable income IRD act"]

    return " ".join(tokens)


# ---------------------------------------------------------------------------
# Explanation generator
# ---------------------------------------------------------------------------

_IRD_REFS: dict[str, str] = {
    "S001_health_life_premium_optimisation": (
        "IRA No. 24 of 2017 (as amended by No. 45 of 2022 & No. 14 of 2023), s.53 "
        "— qualifying payments: health & life insurance premiums"
    ),
    "S002_retirement_contribution_topup": (
        "IRA No. 24 of 2017 (as amended by No. 10 of 2021 & No. 45 of 2022), s.53 "
        "— qualifying payments: approved retirement contributions"
    ),
    "S003_charity_optimisation": (
        "IRA No. 24 of 2017 (as amended by No. 4 of 2023), s.53 "
        "— qualifying payments: approved charitable donations"
    ),
    "S004_rent_relief_capture": (
        "IRA No. 24 of 2017 (as amended by No. 45 of 2022), s.53 "
        "— qualifying payments: residential rent relief"
    ),
    "S005_home_loan_interest_optimisation": (
        "IRA No. 24 of 2017 (as amended by No. 10 of 2021 & No. 45 of 2022), s.53 "
        "— qualifying payments: home loan interest deduction"
    ),
    "S006_cashflow_stabilise_before_deductions": (
        "IRA No. 24 of 2017 (as amended by No. 45 of 2022), s.53 & s.59 "
        "— feasibility guardrail: liquidity & debt-service thresholds"
    ),
    "S007_employment_withholding_reconciliation": (
        "IRA No. 24 of 2017 (as amended by No. 10 of 2021 & No. 14 of 2023), s.83 "
        "— APIT withholding reconciliation for salaried employees"
    ),
    "S008_epf_voluntary_topup": (
        "IRA No. 24 of 2017 (as amended by No. 45 of 2022), s.53 "
        "— qualifying payments: voluntary EPF contributions beyond mandatory 8%"
    ),
    "S009_business_expense_deduction": (
        "IRA No. 24 of 2017 (as amended by No. 10 of 2021 & No. 4 of 2023), ss.17–18 "
        "— allowable deductions: business expenses for self-employed & business owners"
    ),
    "S010_terminal_benefit_planning": (
        "IRA No. 24 of 2017 (as amended by No. 45 of 2022 & No. 14 of 2023), s.6 "
        "— exempt amounts: EPF/ETF terminal benefits & employer gratuity"
    ),
}


def _generate_explanation(s: dict, ctx: dict, score: float) -> str:
    sid = s.get("strategy_id", "")
    name = s.get("name", "")
    occ = ctx.get("occupation", "")
    gmi = float(ctx.get("gross_monthly_income_lkr", 0))
    annual = float(ctx.get("annual_income", gmi * 12))
    epf = float(ctx.get("epf_balance_lkr", 0))
    yrs = int(ctx.get("years_employed", 0))
    life_ins = float(ctx.get("life_insurance_premium_annual_lkr", 0))
    home_loan = float(ctx.get("home_loan_interest_annual_lkr", 0))
    dti = float(ctx.get("debt_to_income", 0))
    sr = float(ctx.get("savings_rate", 0))

    if "S001" in sid:
        return (
            f"Your profile shows a life insurance premium of LKR {life_ins:,.0f}/year. "
            "By ensuring this is fully claimed within the statutory deduction cap, "
            "you can reduce your taxable income and lower your annual tax bill."
        )
    if "S002" in sid:
        return (
            f"With an annual income of LKR {annual:,.0f}, increasing your retirement "
            "contributions up to the allowable cap reduces your taxable income directly, "
            "building long-term savings while cutting your current tax liability."
        )
    if "S003" in sid:
        return (
            f"Your annual income of LKR {annual:,.0f} qualifies you for a charitable "
            "donation deduction under IRD rules. Timing and sizing your donations "
            "optimally can reduce your taxable income without harming your monthly cashflow."
        )
    if "S004" in sid:
        return (
            "You are paying rent and have no home loan, making you eligible for statutory "
            "rental relief. Claiming this deduction reduces your assessable income "
            "directly — a simple, high-confidence tax saving."
        )
    if "S005" in sid:
        return (
            f"You are paying LKR {home_loan:,.0f}/year in home loan interest. "
            "Claiming this as a deduction up to the statutory cap reduces your "
            "taxable income and lowers your annual tax liability."
        )
    if "S006" in sid:
        return (
            f"Your debt-to-income ratio is {dti:.0%} and savings rate is {sr:.0%}. "
            "Before adding new deductible commitments, stabilising cashflow and "
            "rebuilding liquidity will improve your eligibility for other strategies."
        )
    if "S007" in sid:
        return (
            f"As a salaried employee earning LKR {gmi:,.0f}/month, your employer "
            "withholds APIT monthly. Reconciling this against your actual annual tax "
            "liability may reveal a refund or prevent an unexpected year-end top-up."
        )
    if "S008" in sid:
        return (
            f"You have LKR {epf:,.0f} in your EPF fund and have been employed for "
            f"{yrs} years. Voluntarily increasing your EPF contributions qualifies "
            "as a deductible qualifying payment under IRA s.53, reducing taxable income."
        )
    if "S009" in sid:
        return (
            f"As a {occ.replace('_', ' ')}, you can claim all allowable business "
            "expenses under IRA ss.17–18. Properly documenting and claiming these "
            "reduces your assessable income and can significantly lower your tax bill."
        )
    if "S010" in sid:
        return (
            f"With {yrs} years of employment and LKR {epf:,.0f} in EPF, you may "
            "be approaching eligibility for terminal benefit exemptions under IRA s.6. "
            "Strategic exit timing can maximise the tax-exempt portion of your payout."
        )
    return f"The '{name}' strategy is relevant to your financial profile based on semantic similarity."


def _generate_detailed_explanation(s: dict, ctx: dict) -> dict[str, str]:
    """Return a structured detailed explanation with multiple labelled sections."""
    sid = s.get("strategy_id", "")
    occ = ctx.get("occupation", "unknown").replace("_", " ")
    gmi = float(ctx.get("gross_monthly_income_lkr", 0))
    annual = float(ctx.get("annual_income", gmi * 12))
    epf = float(ctx.get("epf_balance_lkr", 0))
    yrs = int(ctx.get("years_employed", 0))
    life_ins = float(ctx.get("life_insurance_premium_annual_lkr", 0))
    home_loan = float(ctx.get("home_loan_interest_annual_lkr", 0))
    donations = float(ctx.get("donations_annual_lkr", 0))
    dti = float(ctx.get("debt_to_income", 0))
    sr = float(ctx.get("savings_rate", 0))
    has_hi = ctx.get("has_health_insurance", False)
    risk = ctx.get("risk_tolerance", "medium")

    if "S001" in sid:
        return {
            "what_it_means": (
                "This strategy involves claiming your health and life insurance premiums as a "
                "qualifying payment deduction under the Inland Revenue Act. The IRD allows you to "
                "deduct these premiums from your gross taxable income, directly reducing the amount "
                "of income you are taxed on."
            ),
            "why_you_qualify": (
                f"Your profile shows a life insurance premium of LKR {life_ins:,.0f}/year"
                + (", and you also have active health insurance coverage" if has_hi else "")
                + f". Your annual income of LKR {annual:,.0f} and occupation as {occ} make you "
                "fully eligible to claim this deduction under s.53."
            ),
            "what_to_do": (
                "1. Collect all insurance premium receipts for the current tax year.\n"
                "2. Verify the total against the statutory cap (check the latest IRD circular for the cap amount).\n"
                "3. Include the deductible amount in your qualifying payments section when filing your return.\n"
                "4. If your employer handles APIT, inform them so the withholding is adjusted accordingly."
            ),
            "potential_benefit": (
                f"If your premium of LKR {life_ins:,.0f}/year is fully within the cap, the tax "
                "saving depends on your marginal tax rate. For example, at a 24% marginal rate, "
                f"LKR {life_ins:,.0f} in deductions saves approximately LKR {life_ins * 0.24:,.0f} "
                "in annual tax."
            ),
            "risk_level": "Low — this is a straightforward, well-established deduction with high IRD compliance confidence.",
        }

    if "S002" in sid:
        return {
            "what_it_means": (
                "Increasing your retirement contributions (e.g. to an approved pension or provident "
                "fund) beyond your current level reduces your taxable income under s.53 qualifying "
                "payments. The IRD sets an annual cap — contributions up to that cap are fully deductible."
            ),
            "why_you_qualify": (
                f"Your annual income of LKR {annual:,.0f} and debt-to-income ratio of {dti:.0%} "
                "indicate you have capacity to increase contributions. You are also below the "
                "retirement age threshold, keeping you eligible under s.53."
            ),
            "what_to_do": (
                "1. Check your current annual retirement contribution amount.\n"
                "2. Identify the gap between your current contribution and the statutory cap.\n"
                "3. Arrange to increase your contribution through your employer or directly.\n"
                "4. Retain contribution proof (receipt or fund statement) for your tax filing."
            ),
            "potential_benefit": (
                "Every additional LKR contributed up to the cap reduces taxable income by that amount. "
                f"At your income level of LKR {annual:,.0f}/year, a marginal rate of 24% means each "
                "LKR 100,000 of additional qualifying contributions saves approximately LKR 24,000 in tax."
            ),
            "risk_level": f"Low to Medium — depends on your current cashflow. With a savings rate of {sr:.0%}, assess affordability before increasing contributions.",
        }

    if "S003" in sid:
        return {
            "what_it_means": (
                "Charitable donations made to IRD-approved organisations qualify as deductible "
                "qualifying payments under s.53. The deduction is capped at a percentage of your "
                "taxable income. Timing and sizing your donations correctly maximises the deduction "
                "without exceeding the cap."
            ),
            "why_you_qualify": (
                f"Your annual income of LKR {annual:,.0f} gives you a meaningful donation deduction "
                "cap. Your current donations of LKR "
                + (f"{donations:,.0f}/year may have room to grow within the cap." if donations > 0
                   else "0/year — you have not yet used this deduction at all, leaving the full cap available.")
            ),
            "what_to_do": (
                "1. Identify IRD-approved charitable organisations you wish to support.\n"
                "2. Calculate the deduction cap (a percentage of your taxable income — refer to the latest IRD guide).\n"
                "3. Plan donations before the tax year end to maximise the current year deduction.\n"
                "4. Collect official receipts from each organisation for your records."
            ),
            "potential_benefit": (
                "If you donate up to the full allowable cap, the tax saving equals cap amount × your "
                f"marginal tax rate. At LKR {annual:,.0f} annual income, this can be a meaningful "
                "annual saving while also supporting a cause you care about."
            ),
            "risk_level": "Low — purely voluntary and reversible year to year. No financial risk if kept within the cap.",
        }

    if "S004" in sid:
        return {
            "what_it_means": (
                "If you are paying rent for residential accommodation and do not have a home loan, "
                "you may be eligible for a statutory rental relief deduction under s.53. A percentage "
                "of rent paid (up to an annual cap) can be deducted from your taxable income."
            ),
            "why_you_qualify": (
                "Your profile shows you are paying rent and have no home loan interest, satisfying "
                "both eligibility conditions. This is a high-confidence deduction with straightforward "
                "documentation requirements."
            ),
            "what_to_do": (
                "1. Ensure you have a formal rental agreement in your name.\n"
                "2. Collect all monthly payment receipts or bank transfer records.\n"
                "3. Calculate your eligible deduction (rent paid × relief percentage, up to the cap).\n"
                "4. Include in your qualifying payments when filing your income tax return."
            ),
            "potential_benefit": (
                "Rental relief is a direct deduction from taxable income. The saving depends on "
                "your rent amount, the relief percentage, and your marginal tax rate. This is one "
                "of the simpler, higher-confidence deductions available."
            ),
            "risk_level": "Low — high confidence deduction, well documented by rental agreement and receipts.",
        }

    if "S005" in sid:
        return {
            "what_it_means": (
                "Interest paid on a qualifying home loan can be deducted from your taxable income "
                "up to a statutory annual cap under s.53. This reduces the income you are taxed on, "
                "partially offsetting the cost of your mortgage."
            ),
            "why_you_qualify": (
                f"You are paying LKR {home_loan:,.0f}/year in home loan interest. As a {occ}, "
                "you meet the occupation eligibility criteria. Provided your loan is for a qualifying "
                "residential property, you can claim this deduction."
            ),
            "what_to_do": (
                "1. Obtain your annual home loan interest certificate from your bank.\n"
                "2. Check the statutory cap — only the interest portion (not principal) is deductible.\n"
                "3. Include the deductible interest amount in your qualifying payments on your return.\n"
                "4. Ensure the property is residential and in your name or jointly held."
            ),
            "potential_benefit": (
                f"With LKR {home_loan:,.0f}/year in interest, and assuming a 24% marginal rate, "
                f"the potential annual tax saving is approximately LKR {min(home_loan, 600000) * 0.24:,.0f} "
                "(subject to the statutory cap)."
            ),
            "risk_level": "Low — this is a well-established deduction. Risk is only if the property does not qualify as residential.",
        }

    if "S006" in sid:
        return {
            "what_it_means": (
                "This is a protective strategy rather than a direct tax saving. When your debt burden "
                "is high or your savings rate is low, taking on additional deductible commitments "
                "(like insurance or donations) can strain your finances. Stabilising cashflow first "
                "puts you in a better position to adopt other strategies safely."
            ),
            "why_you_qualify": (
                f"Your current debt-to-income ratio is {dti:.0%} and savings rate is {sr:.0%}. "
                + ("Your DTI exceeds the 65% guardrail threshold. " if dti > 0.65 else "")
                + ("Your savings rate is below the 5% minimum buffer. " if sr < 0.05 else "")
                + "Addressing these first improves your long-term financial resilience."
            ),
            "what_to_do": (
                "1. Focus on reducing your highest-interest debt first (debt avalanche method).\n"
                "2. Build an emergency fund of at least 1–2 months of expenses in liquid savings.\n"
                "3. Avoid taking on new financial commitments until your DTI drops below 55%.\n"
                "4. Once stabilised, revisit the deduction-based strategies (S001, S002, S003, S005)."
            ),
            "potential_benefit": (
                "While this strategy has no direct immediate tax saving, it unlocks eligibility for "
                "higher-value strategies in the next tax year, creating greater long-term tax efficiency."
            ),
            "risk_level": "Low risk to adopt — the risk is in NOT adopting it and overextending financially.",
        }

    if "S007" in sid:
        return {
            "what_it_means": (
                "As a salaried employee, your employer deducts APIT (Advanced Personal Income Tax) "
                "from your monthly salary. However, the monthly withholding is an estimate. At year "
                "end, if your actual tax liability is lower than what was withheld, you are entitled "
                "to a refund. If it is higher, you owe a top-up. This strategy involves reconciling "
                "both figures."
            ),
            "why_you_qualify": (
                f"You are a salaried employee earning LKR {gmi:,.0f}/month (LKR {annual:,.0f}/year). "
                "APIT withholding applies to you. Any changes in income, deductions, or allowances "
                "during the year can create a gap between withheld tax and actual liability."
            ),
            "what_to_do": (
                "1. Collect your monthly pay slips for the full tax year.\n"
                "2. Request an APIT withholding statement from your employer.\n"
                "3. Calculate your actual tax liability using the IRD tax tables.\n"
                "4. If over-withheld, file a return to claim your refund. If under-withheld, prepare a top-up payment.\n"
                "5. Inform your employer of any deductible payments so they can adjust future withholding."
            ),
            "potential_benefit": (
                "If your actual liability is less than withheld (common after qualifying deductions), "
                "you can recover the overpaid tax as a refund — effectively an interest-free loan "
                "returned to you."
            ),
            "risk_level": "Low — this is a compliance check, not a new commitment. It can only result in a refund or a managed top-up.",
        }

    if "S008" in sid:
        return {
            "what_it_means": (
                "Beyond the mandatory 8% employee EPF contribution, you can voluntarily contribute "
                "additional amounts. These voluntary contributions qualify as deductible qualifying "
                "payments under IRA s.53, reducing your taxable income while simultaneously growing "
                "your retirement fund."
            ),
            "why_you_qualify": (
                f"You have LKR {epf:,.0f} in your EPF fund, have been employed for {yrs} years, "
                f"and your debt-to-income ratio of {dti:.0%} is within the eligible threshold of 65%. "
                "You are also below retirement age, keeping you fully eligible."
            ),
            "what_to_do": (
                "1. Contact your employer's HR or payroll department to arrange voluntary EPF top-up.\n"
                "2. Determine the additional contribution amount — balance tax benefit vs monthly cashflow impact.\n"
                "3. Obtain your EPF membership certificate and employer EPF statement.\n"
                "4. Claim the voluntary contribution amount as a qualifying payment in your tax return."
            ),
            "potential_benefit": (
                f"With LKR {epf:,.0f} already in EPF and {yrs} years of employment, increasing "
                "contributions now compounds significantly by retirement. Additionally, each LKR 100,000 "
                "in qualifying voluntary contributions saves approximately LKR 24,000 in tax at a 24% "
                "marginal rate — a dual benefit of tax saving and retirement growth."
            ),
            "risk_level": "Low to Medium — reduces monthly take-home pay but builds long-term retirement security.",
        }

    if "S009" in sid:
        return {
            "what_it_means": (
                "As a self-employed person, professional, or business owner, you can deduct all "
                "allowable business expenses from your gross business income under IRA ss.17–18. "
                "This includes costs directly incurred in generating your business income — office "
                "expenses, professional fees, travel, equipment depreciation, and more."
            ),
            "why_you_qualify": (
                f"Your occupation is {occ}, which falls under the eligible categories for business "
                f"expense deductions. With an annual income of LKR {annual:,.0f}, systematically "
                "claiming all allowable expenses can meaningfully reduce your assessable income."
            ),
            "what_to_do": (
                "1. Maintain organised records of all business-related expenses throughout the year.\n"
                "2. Categorise expenses: direct costs, overhead, depreciation, professional fees.\n"
                "3. Ensure expenses are wholly and exclusively incurred for your business.\n"
                "4. Prepare a business expense schedule and attach to your income tax return.\n"
                "5. Consult a tax professional to identify any sector-specific allowable deductions."
            ),
            "potential_benefit": (
                f"The tax saving depends on your total claimable expenses. For a {occ}, allowable "
                "business expenses typically range from 20–40% of gross business income depending on "
                "sector. Each LKR 100,000 of claimable expenses saves approximately LKR 24,000 in "
                "tax at a 24% marginal rate."
            ),
            "risk_level": "Medium — requires good record-keeping. Risk of IRD audit if expenses are not well documented.",
        }

    if "S010" in sid:
        return {
            "what_it_means": (
                "When you retire or resign after a qualifying period, your terminal benefits — EPF "
                "lump sum, ETF payout, and employer gratuity — may be partially or fully exempt from "
                "income tax under IRA s.6. The exempt amount depends on years of service and the "
                "statutory thresholds in force at the time of exit."
            ),
            "why_you_qualify": (
                f"You have {yrs} years of employment and LKR {epf:,.0f} in EPF, "
                + ("which exceeds the LKR 500,000 threshold for advanced planning eligibility. " if epf >= 500000 else "")
                + "This means your terminal payout is likely significant and strategic exit timing "
                "can maximise the tax-exempt portion."
            ),
            "what_to_do": (
                "1. Request your EPF and ETF statements to know your current accumulated balance.\n"
                "2. Obtain an employment letter confirming your years of service.\n"
                "3. Model two or three potential exit dates to see which maximises exempt amounts.\n"
                "4. Consult a tax advisor to understand how the statutory thresholds apply to your specific situation.\n"
                "5. Align your exit timing with the tax year to optimise the exempt portion."
            ),
            "potential_benefit": (
                f"With LKR {epf:,.0f} in EPF and {yrs} years of service, your terminal payout "
                "could be substantial. Proper planning can shift a significant portion of this payout "
                "into the exempt bracket, potentially saving tens to hundreds of thousands of LKR "
                "in terminal tax — a one-time but high-value optimisation."
            ),
            "risk_level": "Medium — low risk if well planned, but exit timing is irreversible. Consult a professional before acting.",
        }

    return {
        "what_it_means": "This strategy was retrieved based on semantic similarity to your financial profile.",
        "why_you_qualify": "Your profile features matched the strategy document in the knowledge base.",
        "what_to_do": "Review the strategy description and consult a tax professional for personalised guidance.",
        "potential_benefit": "Benefit depends on your specific financial figures.",
        "risk_level": "Consult a tax professional to assess risk for your situation.",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class RagResult:
    def __init__(
        self,
        strategy_id: str,
        name: str,
        category: str,
        description: str,
        similarity_score: float,
        ird_reference: str,
        required_docs: list[str],
        why_relevant: str,
        detailed_explanation: dict[str, str],
    ) -> None:
        self.strategy_id = strategy_id
        self.name = name
        self.category = category
        self.description = description
        self.similarity_score = similarity_score
        self.ird_reference = ird_reference
        self.required_docs = required_docs
        self.why_relevant = why_relevant
        self.detailed_explanation = detailed_explanation


def rag_query(db: Session, *, profile_id: str, top_k: int = 5) -> tuple[list[RagResult], str]:
    """Retrieve top-K strategies for a profile using TF-IDF cosine similarity.

    Returns (results, query_text).
    """
    profile = get_profile(db, UUID(profile_id))
    if profile is None:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")

    derived = compute_derived_features(profile)
    ctx: dict = {
        "occupation": str(profile.occupation),
        "risk_tolerance": str(profile.risk_tolerance),
        "gross_monthly_income_lkr": float(profile.gross_monthly_income),
        "annual_income": float(derived.gross_annual_taxable_income),
        "epf_balance_lkr": float(profile.epf_balance),
        "years_employed": int(profile.years_employed),
        "life_insurance_premium_annual_lkr": float(profile.life_insurance_premium_annual),
        "home_loan_interest_annual_lkr": float(profile.home_loan_interest_annual),
        "donations_annual_lkr": float(profile.donations_annual),
        "has_health_insurance": bool(profile.health_insurance),
        "debt_to_income": float(derived.debt_to_income),
        "savings_rate": float(derived.savings_rate),
        "age_years": int(derived.age_years),
    }

    query_text = _profile_to_query(ctx)
    vectorizer, matrix, strategies = _build_vector_store()

    query_vec = vectorizer.transform([query_text])
    scores = cosine_similarity(query_vec, matrix).flatten()

    top_indices = scores.argsort()[::-1][:top_k]

    results: list[RagResult] = []
    for idx in top_indices:
        s = strategies[idx]
        sid = s.get("strategy_id", "")
        results.append(
            RagResult(
                strategy_id=sid,
                name=s.get("name", ""),
                category=s.get("category", "").replace("_", " "),
                description=s.get("description", "").strip(),
                similarity_score=round(float(scores[idx]), 4),
                ird_reference=_IRD_REFS.get(sid, "IRA No. 24 of 2017"),
                required_docs=s.get("constraints", {}).get("required_docs", []),
                why_relevant=_generate_explanation(s, ctx, float(scores[idx])),
                detailed_explanation=_generate_detailed_explanation(s, ctx),
            )
        )

    return results, query_text
