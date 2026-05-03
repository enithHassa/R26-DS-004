"""Synthetic taxpayer profile generator for Phase 1 (WP3).

Generates a deterministic, reproducible parquet dataset of N synthetic
financial profiles aligned with ``app.schemas.profile.FinancialProfileBase``
plus derived tax-engine fields. Distributions are loosely calibrated to
Sri Lankan demographics + APIT FY 2024/25 brackets — enough to train the
adoption / LambdaMART models offline. Real numbers can be swapped in
later by editing the YAML rule pack and the archetype mixture below.

Outputs columns documented in
``data/synthetic/profiles_data_card.md`` (auto-written next to the parquet).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from rules.engine import TaxRules, apply_deductions, compute_annual_tax, load_tax_rules

# ---------------------------------------------------------------------------
# Reference distributions (Sri Lanka)
# ---------------------------------------------------------------------------

# 25 administrative districts; weights very roughly reflect Census 2012 share
# of formal-sector / taxable population. Tweak with real IRD data later.
_DISTRICTS: tuple[tuple[str, float], ...] = (
    ("Colombo", 0.30),
    ("Gampaha", 0.18),
    ("Kalutara", 0.05),
    ("Kandy", 0.07),
    ("Matale", 0.015),
    ("Nuwara Eliya", 0.015),
    ("Galle", 0.04),
    ("Matara", 0.025),
    ("Hambantota", 0.015),
    ("Jaffna", 0.025),
    ("Kilinochchi", 0.005),
    ("Mannar", 0.004),
    ("Vavuniya", 0.005),
    ("Mullaitivu", 0.003),
    ("Batticaloa", 0.015),
    ("Ampara", 0.015),
    ("Trincomalee", 0.012),
    ("Kurunegala", 0.04),
    ("Puttalam", 0.018),
    ("Anuradhapura", 0.02),
    ("Polonnaruwa", 0.012),
    ("Badulla", 0.022),
    ("Moneragala", 0.008),
    ("Ratnapura", 0.025),
    ("Kegalle", 0.018),
)

# Sinhala / Tamil / Burgher first + last name pools. Curated, not exhaustive.
_FIRST_NAMES_M: tuple[str, ...] = (
    "Nuwan", "Dilhan", "Kasun", "Ruwan", "Sahan", "Tharindu", "Lahiru", "Praveen",
    "Sanjeewa", "Rohan", "Dhanushka", "Ishan", "Charith", "Asitha", "Shehan",
    "Mahinda", "Vimukthi", "Kavindu", "Janaka", "Pubudu", "Ravindu", "Saman",
    "Arun", "Vishva", "Suresh", "Rajan", "Nimal", "Kumar", "Priyantha",
)
_FIRST_NAMES_F: tuple[str, ...] = (
    "Nadeesha", "Dilini", "Tharushi", "Hashini", "Anushka", "Sandali", "Madushi",
    "Kavindi", "Ishara", "Charmi", "Pavithra", "Sachini", "Amali", "Nethmi",
    "Chandima", "Kumudu", "Niluka", "Shashika", "Roshani", "Yasodha", "Ruvini",
    "Priyanka", "Vidya", "Anjali", "Lakshmi",
)
_LAST_NAMES: tuple[str, ...] = (
    "Perera", "Silva", "Fernando", "Gunawardena", "Wickramasinghe", "Jayasuriya",
    "Bandara", "Rathnayake", "Senanayake", "Pieris", "De Silva", "Karunaratne",
    "Wijesinghe", "Ekanayake", "Dissanayake", "Rajapaksa", "Liyanage",
    "Hettiarachchi", "Wijewardena", "Peiris", "Kularatne", "Sirisena",
    "Mendis", "Wijetunge", "Pathirana", "Goonetilleke",
)

# Archetype mixture — drives joint distribution over income, occupation, age,
# liquidity, and risk tolerance.
@dataclass(frozen=True)
class Archetype:
    name: str
    weight: float
    occupation: str
    age_range: tuple[int, int]
    log_income_mu: float          # mean of log(monthly_income_LKR)
    log_income_sigma: float
    expense_ratio_range: tuple[float, float]   # fraction of income spent
    liquidity_months_range: tuple[float, float]  # months of expense in cash
    debt_prob: float
    risk_tolerance_weights: tuple[float, float, float]  # low/med/high
    horizon_range: tuple[int, int]
    has_employer_provident: bool


_ARCHETYPES: tuple[Archetype, ...] = (
    Archetype(
        name="young_employee",
        weight=0.20,
        occupation="employee",
        age_range=(22, 30),
        log_income_mu=11.55,        # ~ LKR 104k median monthly
        log_income_sigma=0.40,
        expense_ratio_range=(0.55, 0.85),
        liquidity_months_range=(0.5, 4.0),
        debt_prob=0.25,
        risk_tolerance_weights=(0.20, 0.55, 0.25),
        horizon_range=(5, 25),
        has_employer_provident=True,
    ),
    Archetype(
        name="mid_employee",
        weight=0.22,
        occupation="employee",
        age_range=(30, 45),
        log_income_mu=12.20,        # ~ LKR 200k
        log_income_sigma=0.50,
        expense_ratio_range=(0.45, 0.80),
        liquidity_months_range=(1.0, 8.0),
        debt_prob=0.45,
        risk_tolerance_weights=(0.30, 0.50, 0.20),
        horizon_range=(5, 25),
        has_employer_provident=True,
    ),
    Archetype(
        name="senior_employee",
        weight=0.10,
        occupation="employee",
        age_range=(45, 60),
        log_income_mu=12.80,        # ~ LKR 360k
        log_income_sigma=0.55,
        expense_ratio_range=(0.40, 0.75),
        liquidity_months_range=(2.0, 12.0),
        debt_prob=0.35,
        risk_tolerance_weights=(0.45, 0.40, 0.15),
        horizon_range=(3, 15),
        has_employer_provident=True,
    ),
    Archetype(
        name="self_employed_professional",
        weight=0.12,
        occupation="professional",
        age_range=(28, 55),
        log_income_mu=12.50,        # ~ LKR 270k
        log_income_sigma=0.65,
        expense_ratio_range=(0.40, 0.80),
        liquidity_months_range=(1.5, 12.0),
        debt_prob=0.30,
        risk_tolerance_weights=(0.25, 0.45, 0.30),
        horizon_range=(5, 25),
        has_employer_provident=False,
    ),
    Archetype(
        name="business_owner",
        weight=0.13,
        occupation="business_owner",
        age_range=(28, 60),
        log_income_mu=13.10,        # ~ LKR 490k with very heavy tail
        log_income_sigma=0.85,
        expense_ratio_range=(0.30, 0.75),
        liquidity_months_range=(2.0, 18.0),
        debt_prob=0.55,
        risk_tolerance_weights=(0.15, 0.45, 0.40),
        horizon_range=(5, 30),
        has_employer_provident=False,
    ),
    Archetype(
        name="self_employed_freelancer",
        weight=0.10,
        occupation="self_employed",
        age_range=(22, 45),
        log_income_mu=11.80,        # ~ LKR 134k
        log_income_sigma=0.65,
        expense_ratio_range=(0.50, 0.90),
        liquidity_months_range=(0.5, 6.0),
        debt_prob=0.30,
        risk_tolerance_weights=(0.30, 0.50, 0.20),
        horizon_range=(3, 20),
        has_employer_provident=False,
    ),
    Archetype(
        name="investor",
        weight=0.08,
        occupation="investor",
        age_range=(35, 65),
        log_income_mu=13.30,        # high passive income
        log_income_sigma=0.70,
        expense_ratio_range=(0.30, 0.70),
        liquidity_months_range=(3.0, 24.0),
        debt_prob=0.30,
        risk_tolerance_weights=(0.20, 0.40, 0.40),
        horizon_range=(5, 30),
        has_employer_provident=False,
    ),
    Archetype(
        name="retiree",
        weight=0.05,
        occupation="other",
        age_range=(60, 70),
        log_income_mu=11.60,        # mostly pension + investment income
        log_income_sigma=0.45,
        expense_ratio_range=(0.50, 0.90),
        liquidity_months_range=(3.0, 24.0),
        debt_prob=0.10,
        risk_tolerance_weights=(0.65, 0.30, 0.05),
        horizon_range=(1, 10),
        has_employer_provident=False,
    ),
)

# Snapshot date used to compute age and DOB.
_SNAPSHOT_DATE = date(2025, 1, 1)


# ---------------------------------------------------------------------------
# Data card columns (kept in sync with FinancialProfileBase + DerivedFeatures)
# ---------------------------------------------------------------------------

PROFILE_COLUMNS: tuple[str, ...] = (
    "profile_id",
    "full_name",
    "date_of_birth",
    "age_years",
    "gender",
    "district",
    "marital_status",
    "occupation",
    "dependents",
    "years_employed",
    "gross_monthly_income_lkr",
    "monthly_expenses_lkr",
    "monthly_debt_service_lkr",
    "liquid_savings_lkr",
    "existing_investments_lkr",
    "total_debt_lkr",
    "epf_balance_lkr",
    "etf_balance_lkr",
    "health_insurance",
    "life_insurance_premium_annual_lkr",
    "home_loan_interest_annual_lkr",
    "donations_annual_lkr",
    "risk_tolerance",
    "investment_horizon_years",
    "income_sources_json",
    "tax_year",
    "gross_annual_taxable_income_lkr",
    "baseline_tax_liability_lkr",
    "effective_tax_rate",
    "disposable_income_monthly_lkr",
    "savings_rate",
    "debt_to_income",
    "archetype",
    "split",
)


# ---------------------------------------------------------------------------
# Generator config + RNG helpers
# ---------------------------------------------------------------------------


@dataclass
class GeneratorConfig:
    n_rows: int = 25_000
    seed: int = 42
    train_frac: float = 0.70
    val_frac: float = 0.15
    test_frac: float = 0.15
    tax_year: str = "2024_25"
    rules_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parents[1]
        / "rules"
        / "sl_tax_2024_25.yaml"
    )

    def __post_init__(self) -> None:
        total = self.train_frac + self.val_frac + self.test_frac
        if not 0.999 <= total <= 1.001:
            raise ValueError(
                f"train+val+test fractions must sum to 1, got {total}"
            )


def _choose(rng: np.random.Generator, options: tuple[str, ...], probs: tuple[float, ...]) -> str:
    return str(rng.choice(options, p=np.array(probs) / sum(probs)))


def _round_lkr(x: float) -> float:
    return float(round(max(0.0, x), 2))


def _sample_archetype_indices(rng: np.random.Generator, n: int) -> np.ndarray:
    weights = np.array([a.weight for a in _ARCHETYPES])
    probs = weights / weights.sum()
    return rng.choice(len(_ARCHETYPES), size=n, p=probs)


def _sample_districts(rng: np.random.Generator, n: int) -> np.ndarray:
    names = np.array([d[0] for d in _DISTRICTS])
    weights = np.array([d[1] for d in _DISTRICTS])
    return rng.choice(names, size=n, p=weights / weights.sum())


def _build_full_name(rng: np.random.Generator, gender: str) -> str:
    pool = _FIRST_NAMES_M if gender == "male" else _FIRST_NAMES_F
    first = rng.choice(pool)
    last = rng.choice(_LAST_NAMES)
    return f"{first} {last}"


def _split_assignment(rng: np.random.Generator, n: int, cfg: GeneratorConfig) -> np.ndarray:
    out = np.empty(n, dtype=object)
    u = rng.random(n)
    out[u < cfg.train_frac] = "train"
    out[(u >= cfg.train_frac) & (u < cfg.train_frac + cfg.val_frac)] = "val"
    out[u >= cfg.train_frac + cfg.val_frac] = "test"
    return out


# ---------------------------------------------------------------------------
# Per-row generation
# ---------------------------------------------------------------------------


def _build_income_sources(
    *,
    occupation: str,
    monthly_income: float,
    rng: np.random.Generator,
) -> list[dict]:
    """Decompose monthly income into a small set of source dicts."""
    if occupation == "employee":
        primary = monthly_income * float(rng.uniform(0.85, 1.0))
        sources = [
            {
                "kind": "employment",
                "monthly_amount": _round_lkr(primary),
                "currency": "LKR",
                "is_taxable": True,
            }
        ]
        leftover = max(0.0, monthly_income - primary)
        if leftover > 0:
            sources.append(
                {
                    "kind": "interest",
                    "monthly_amount": _round_lkr(leftover),
                    "currency": "LKR",
                    "is_taxable": True,
                }
            )
        return sources
    if occupation == "business_owner":
        biz = monthly_income * float(rng.uniform(0.7, 0.95))
        rental = monthly_income * float(rng.uniform(0.0, 0.2))
        rest = max(0.0, monthly_income - biz - rental)
        sources = [
            {"kind": "business", "monthly_amount": _round_lkr(biz), "currency": "LKR", "is_taxable": True}
        ]
        if rental > 100:
            sources.append({"kind": "rental", "monthly_amount": _round_lkr(rental), "currency": "LKR", "is_taxable": True})
        if rest > 100:
            sources.append({"kind": "dividend", "monthly_amount": _round_lkr(rest), "currency": "LKR", "is_taxable": True})
        return sources
    if occupation == "investor":
        div = monthly_income * float(rng.uniform(0.4, 0.7))
        interest = monthly_income * float(rng.uniform(0.2, 0.4))
        capital = max(0.0, monthly_income - div - interest)
        return [
            {"kind": "dividend", "monthly_amount": _round_lkr(div), "currency": "LKR", "is_taxable": True},
            {"kind": "interest", "monthly_amount": _round_lkr(interest), "currency": "LKR", "is_taxable": True},
            {"kind": "capital_gain", "monthly_amount": _round_lkr(capital), "currency": "LKR", "is_taxable": True},
        ]
    if occupation in {"self_employed", "professional"}:
        primary = monthly_income * float(rng.uniform(0.85, 1.0))
        rest = max(0.0, monthly_income - primary)
        sources = [
            {"kind": "business", "monthly_amount": _round_lkr(primary), "currency": "LKR", "is_taxable": True}
        ]
        if rest > 100:
            sources.append({"kind": "interest", "monthly_amount": _round_lkr(rest), "currency": "LKR", "is_taxable": True})
        return sources
    return [
        {"kind": "other", "monthly_amount": _round_lkr(monthly_income), "currency": "LKR", "is_taxable": True}
    ]


def _row_for_archetype(
    archetype: Archetype,
    *,
    rng: np.random.Generator,
    rules: TaxRules,
    tax_year: str,
    district: str,
) -> dict:
    age = int(rng.integers(archetype.age_range[0], archetype.age_range[1] + 1))
    dob = _SNAPSHOT_DATE - timedelta(days=age * 365 + int(rng.integers(0, 365)))

    gender_roll = rng.random()
    gender = "male" if gender_roll < 0.5 else "female"
    if rng.random() < 0.005:
        gender = "other"

    if age < 25:
        marital_probs = (0.85, 0.13, 0.005, 0.015)
    elif age < 35:
        marital_probs = (0.45, 0.50, 0.04, 0.01)
    elif age < 50:
        marital_probs = (0.20, 0.70, 0.08, 0.02)
    else:
        marital_probs = (0.10, 0.70, 0.10, 0.10)
    marital_status = _choose(rng, ("single", "married", "divorced", "widowed"), marital_probs)

    if marital_status == "single":
        dependents = int(rng.choice([0, 0, 0, 1, 1, 2], 1)[0])
    elif marital_status == "married":
        dependents = int(rng.choice([0, 1, 1, 2, 2, 3, 3, 4, 5], 1)[0])
    else:
        dependents = int(rng.choice([0, 1, 1, 2, 3], 1)[0])

    monthly_income = float(np.exp(rng.normal(archetype.log_income_mu, archetype.log_income_sigma)))
    monthly_income = max(35_000.0, min(monthly_income, 25_000_000.0))

    expense_ratio = float(rng.uniform(*archetype.expense_ratio_range))
    monthly_expenses = monthly_income * expense_ratio
    monthly_expenses *= 1.0 + 0.05 * dependents
    monthly_expenses = min(monthly_expenses, monthly_income * 0.97)

    has_debt = rng.random() < archetype.debt_prob
    if has_debt:
        debt_multiple = float(rng.uniform(0.5, 8.0))
        total_debt = monthly_income * 12 * debt_multiple
        monthly_debt_service = total_debt / float(rng.uniform(36.0, 240.0))
        monthly_debt_service = min(monthly_debt_service, monthly_income * 0.45)
    else:
        total_debt = 0.0
        monthly_debt_service = 0.0

    liquidity_months = float(rng.uniform(*archetype.liquidity_months_range))
    liquid_savings = monthly_expenses * liquidity_months
    investments_multiplier = float(rng.gamma(2.0, 0.6))
    if archetype.name == "investor":
        investments_multiplier *= 5.0
    elif archetype.name in {"senior_employee", "business_owner"}:
        investments_multiplier *= 2.0
    existing_investments = monthly_income * investments_multiplier

    if archetype.has_employer_provident:
        years_employed = int(min(age - 21, max(0, rng.integers(0, max(2, age - 22)))))
        basic_estimate = monthly_income * float(rng.uniform(0.55, 0.85))
        epf_balance = basic_estimate * 12 * (
            rules.provident.get("epf_employee_rate", 0.08)
            + rules.provident.get("epf_employer_rate", 0.12)
        ) * years_employed * float(rng.uniform(1.0, 1.4))
        etf_balance = basic_estimate * 12 * rules.provident.get("etf_employer_rate", 0.03) * years_employed * float(rng.uniform(1.0, 1.3))
    else:
        years_employed = 0
        epf_balance = 0.0
        etf_balance = 0.0

    risk_tolerance = _choose(rng, ("low", "medium", "high"), archetype.risk_tolerance_weights)
    horizon = int(rng.integers(archetype.horizon_range[0], archetype.horizon_range[1] + 1))
    horizon = min(horizon, max(1, 70 - age))

    health_insurance = bool(rng.random() < (0.25 + 0.4 * (archetype.name in {"senior_employee", "mid_employee", "professional", "business_owner"})))
    life_premium_annual = float(rng.choice([0, 0, 0, 0, 1])) * float(rng.uniform(20_000, 200_000))
    if archetype.name in {"young_employee", "self_employed_freelancer"}:
        life_premium_annual *= 0.4
    home_loan_interest_annual = 0.0
    if archetype.name in {"mid_employee", "senior_employee", "business_owner"} and rng.random() < 0.35:
        home_loan_interest_annual = float(rng.uniform(60_000, 1_200_000))
    donations_annual = float(rng.choice([0.0, 0.0, 0.0])) if rng.random() > 0.25 else float(rng.uniform(5_000, 250_000))

    income_sources = _build_income_sources(
        occupation=archetype.occupation, monthly_income=monthly_income, rng=rng
    )
    annual_income = sum(s["monthly_amount"] for s in income_sources if s["is_taxable"]) * 12.0

    rent_paid_annual = 0.0
    if archetype.name in {"young_employee", "self_employed_freelancer"} and rng.random() < 0.45:
        rent_paid_annual = float(rng.uniform(120_000, 900_000))

    taxable_after_deductions = apply_deductions(
        annual_income=annual_income,
        rules=rules,
        rent_paid_annual=rent_paid_annual,
        life_insurance_premium_annual=life_premium_annual,
        health_insurance_premium_annual=15_000.0 if health_insurance else 0.0,
        home_loan_interest_annual=home_loan_interest_annual,
        donations_annual=donations_annual,
    )
    baseline_tax = compute_annual_tax(taxable_after_deductions, rules)
    effective_tax_rate = baseline_tax / annual_income if annual_income > 0 else 0.0

    monthly_disposable = monthly_income - monthly_expenses - monthly_debt_service - (baseline_tax / 12.0)
    monthly_disposable = max(-monthly_income, monthly_disposable)
    savings_rate = max(0.0, min(1.0, monthly_disposable / monthly_income)) if monthly_income > 0 else 0.0
    debt_to_income = total_debt / annual_income if annual_income > 0 else 0.0

    return {
        "profile_id": str(uuid.uuid4()),
        "full_name": _build_full_name(rng, gender),
        "date_of_birth": dob.isoformat(),
        "age_years": age,
        "gender": gender,
        "district": district,
        "marital_status": marital_status,
        "occupation": archetype.occupation,
        "dependents": dependents,
        "years_employed": int(years_employed),
        "gross_monthly_income_lkr": _round_lkr(monthly_income),
        "monthly_expenses_lkr": _round_lkr(monthly_expenses),
        "monthly_debt_service_lkr": _round_lkr(monthly_debt_service),
        "liquid_savings_lkr": _round_lkr(liquid_savings),
        "existing_investments_lkr": _round_lkr(existing_investments),
        "total_debt_lkr": _round_lkr(total_debt),
        "epf_balance_lkr": _round_lkr(epf_balance),
        "etf_balance_lkr": _round_lkr(etf_balance),
        "health_insurance": bool(health_insurance),
        "life_insurance_premium_annual_lkr": _round_lkr(life_premium_annual),
        "home_loan_interest_annual_lkr": _round_lkr(home_loan_interest_annual),
        "donations_annual_lkr": _round_lkr(donations_annual),
        "risk_tolerance": risk_tolerance,
        "investment_horizon_years": int(horizon),
        "income_sources_json": json.dumps(income_sources, separators=(",", ":")),
        "tax_year": tax_year,
        "gross_annual_taxable_income_lkr": _round_lkr(annual_income),
        "baseline_tax_liability_lkr": _round_lkr(baseline_tax),
        "effective_tax_rate": float(round(effective_tax_rate, 6)),
        "disposable_income_monthly_lkr": _round_lkr(monthly_disposable),
        "savings_rate": float(round(savings_rate, 6)),
        "debt_to_income": float(round(debt_to_income, 6)),
        "archetype": archetype.name,
    }


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def generate_profiles(cfg: GeneratorConfig | None = None) -> pd.DataFrame:
    """Return a deterministic DataFrame of ``cfg.n_rows`` synthetic profiles."""
    cfg = cfg or GeneratorConfig()
    rules = load_tax_rules(cfg.rules_path)
    rng = np.random.default_rng(cfg.seed)

    archetype_idx = _sample_archetype_indices(rng, cfg.n_rows)
    districts = _sample_districts(rng, cfg.n_rows)

    rows: list[dict] = []
    for i in range(cfg.n_rows):
        a = _ARCHETYPES[int(archetype_idx[i])]
        rows.append(
            _row_for_archetype(
                a,
                rng=rng,
                rules=rules,
                tax_year=cfg.tax_year,
                district=str(districts[i]),
            )
        )

    df = pd.DataFrame(rows, columns=list(PROFILE_COLUMNS[:-1]))
    df["split"] = _split_assignment(rng, len(df), cfg)
    return df[list(PROFILE_COLUMNS)]


def write_profiles(df: pd.DataFrame, out_dir: Path) -> dict[str, Path]:
    """Persist ``df`` as parquet (+ CSV preview) and emit a data card."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = out_dir / "profiles.parquet"
    csv_path = out_dir / "profiles.csv"
    csv_preview = out_dir / "profiles_preview.csv"
    data_card = out_dir / "profiles_data_card.md"

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)
    df.head(200).to_csv(csv_preview, index=False)

    summary = {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "splits": df["split"].value_counts().to_dict(),
        "archetypes": df["archetype"].value_counts().to_dict(),
        "occupations": df["occupation"].value_counts().to_dict(),
        "income_quantiles_monthly": {
            q: float(df["gross_monthly_income_lkr"].quantile(q))
            for q in (0.05, 0.25, 0.50, 0.75, 0.95, 0.99)
        },
        "tax_quantiles_annual": {
            q: float(df["baseline_tax_liability_lkr"].quantile(q))
            for q in (0.05, 0.25, 0.50, 0.75, 0.95, 0.99)
        },
        "share_with_zero_tax": float((df["baseline_tax_liability_lkr"] == 0).mean()),
        "share_with_debt": float((df["total_debt_lkr"] > 0).mean()),
        "share_employees": float((df["occupation"] == "employee").mean()),
    }

    lines = [
        "# Synthetic Financial Profiles — Data Card",
        "",
        f"- Rows: **{summary['rows']:,}**",
        f"- Tax rules pack: `models/personalized-recommendation/rules/sl_tax_2024_25.yaml`",
        f"- Splits: {summary['splits']}",
        f"- Archetypes: {summary['archetypes']}",
        f"- Occupations: {summary['occupations']}",
        f"- Share with zero tax liability: {summary['share_with_zero_tax']:.2%}",
        f"- Share with debt: {summary['share_with_debt']:.2%}",
        f"- Share employees: {summary['share_employees']:.2%}",
        "",
        "## Monthly gross income quantiles (LKR)",
        "",
        "| Quantile | Value |",
        "| --- | ---: |",
        *(
            f"| p{int(q * 100):02d} | {summary['income_quantiles_monthly'][q]:,.0f} |"
            for q in (0.05, 0.25, 0.50, 0.75, 0.95, 0.99)
        ),
        "",
        "## Annual baseline tax liability quantiles (LKR)",
        "",
        "| Quantile | Value |",
        "| --- | ---: |",
        *(
            f"| p{int(q * 100):02d} | {summary['tax_quantiles_annual'][q]:,.0f} |"
            for q in (0.05, 0.25, 0.50, 0.75, 0.95, 0.99)
        ),
        "",
        "## Columns",
        "",
        *(f"- `{c}`" for c in df.columns),
        "",
    ]
    data_card.write_text("\n".join(lines), encoding="utf-8")

    return {
        "parquet": parquet_path,
        "csv": csv_path,
        "csv_preview": csv_preview,
        "data_card": data_card,
    }


__all__ = [
    "PROFILE_COLUMNS",
    "GeneratorConfig",
    "generate_profiles",
    "write_profiles",
]
