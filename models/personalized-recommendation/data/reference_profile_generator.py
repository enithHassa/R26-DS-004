"""Generate synthetic profiles matched to an EY-style reference CSV.

Samples prototype rows from the reference (preserving categorical joint structure),
applies calibrated multiplicative jitter on financial continuous fields, rebuilds
``income_sources_json``, and recomputes tax via the same rules engine as
:data:`profile_generator`.

The output schema matches ``PROFILE_COLUMNS`` in :mod:`profile_generator`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rules.engine import apply_deductions, compute_annual_tax, load_tax_rules

from data.profile_generator import (
    PROFILE_COLUMNS,
    GeneratorConfig,
    _build_full_name,
    _choose,
    _round_lkr,
    _split_assignment,
)

# ---------------------------------------------------------------------------
# EY CSV → internal schema
# ---------------------------------------------------------------------------

_INCOME_TYPE_MAP: dict[str, str] = {
    "Employment": "employment",
    "Business": "business",
    "Dividends": "dividend",
    "Professional Service": "business",
}

_OCC_MAP: dict[str, str] = {
    "Employee": "employee",
    "Business Owner": "business_owner",
    "Self-Employed": "professional",
}

_DISTRICT_NORMALIZE: dict[str, str] = {
    "Kollupitiya": "Colombo",
}


def _parse_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().upper()
    return s in {"TRUE", "1", "YES", "T"}


def _norm_tax_year(v: Any) -> str:
    s = str(v).strip().replace("/", "_")
    return s


def infer_archetype(age: int, occupation: str) -> str:
    if occupation == "employee":
        if age < 30:
            return "young_employee"
        if age <= 45:
            return "mid_employee"
        return "senior_employee"
    if occupation == "business_owner":
        return "business_owner"
    if occupation == "professional":
        if age < 35:
            return "self_employed_freelancer"
        return "self_employed_professional"
    return "mid_employee"


_ARCHETYPE_RISK_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "young_employee": (0.20, 0.55, 0.25),
    "mid_employee": (0.30, 0.50, 0.20),
    "senior_employee": (0.45, 0.40, 0.15),
    "self_employed_professional": (0.25, 0.45, 0.30),
    "business_owner": (0.15, 0.45, 0.40),
    "self_employed_freelancer": (0.30, 0.50, 0.20),
    "investor": (0.20, 0.40, 0.40),
    "retiree": (0.65, 0.30, 0.05),
}


def _sample_risk(archetype: str, rng: np.random.Generator) -> str:
    w = _ARCHETYPE_RISK_WEIGHTS.get(archetype, (0.33, 0.34, 0.33))
    return _choose(rng, ("low", "medium", "high"), w)


def _sources_ey_to_profile(sources_raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in sources_raw:
        t = str(item["type"])
        kind = _INCOME_TYPE_MAP.get(t)
        if kind is None:
            kind = "other"
        amt = float(item["amount"])
        out.append(
            {
                "kind": kind,
                "monthly_amount": _round_lkr(amt),
                "currency": "LKR",
                "is_taxable": True,
            }
        )
    return out


def _jitter_positive(x: float, rng: np.random.Generator, sigma: float) -> float:
    if x is None or not np.isfinite(x) or float(x) <= 0:
        return 0.0
    return float(max(0.0, float(x) * np.exp(rng.normal(0.0, sigma))))


def _jitter_optional_positive(
    x: float, rng: np.random.Generator, sigma: float
) -> float:
    """Keep zeros with high probability; jitter positives."""
    if x is None or not np.isfinite(x) or float(x) <= 0:
        return 0.0
    return _jitter_positive(float(x), rng, sigma)


def load_ey_reference_csv(path: Path | str) -> pd.DataFrame:
    return pd.read_csv(path)


def ey_series_to_profile_row(
    row: pd.Series,
    *,
    rng: np.random.Generator,
    rules,
    tax_year_tag: str,
    finance_sigma: float,
    anonymize_names: bool = True,
) -> dict[str, Any]:
    """Map one EY row to a profile dict; optionally jitter financial fields."""
    gender = str(row["Gender"]).strip().lower()
    if gender not in {"male", "female"}:
        gender = rng.choice(["male", "female"])

    occ_raw = str(row["Occupation"]).strip()
    occupation = _OCC_MAP.get(occ_raw, "employee")

    district = str(row["District"]).strip()
    district = _DISTRICT_NORMALIZE.get(district, district)

    marital = str(row["Marital Status"]).strip().lower()
    dependents = int(row["Number of Dependents"])
    years_employed = int(max(0, row["Years of Employment"]))
    age = int(row["Age"])

    sources_raw = json.loads(row["Sources of Income"])
    sources = _sources_ey_to_profile(sources_raw)

    # Jitter component amounts; rescale preserves mixture weights.
    factors = np.exp(rng.normal(0.0, finance_sigma, size=len(sources)))
    for i, s in enumerate(sources):
        base = float(s["monthly_amount"])
        if base > 0:
            sources[i]["monthly_amount"] = _round_lkr(base * float(factors[i]))
    gross_monthly = float(sum(float(s["monthly_amount"]) for s in sources))

    monthly_expenses = _jitter_positive(float(row["Monthly Expenses"]), rng, finance_sigma)
    monthly_expenses = min(monthly_expenses, gross_monthly * 0.97)

    debt_pay = float(row["Monthly Debt Repayment"])
    monthly_debt = _jitter_optional_positive(debt_pay, rng, finance_sigma)
    monthly_debt = min(monthly_debt, gross_monthly * 0.45)

    liquid = _jitter_positive(float(row["Liquid Savings"]), rng, finance_sigma)
    investments = _jitter_positive(float(row["Existing Investments"]), rng, finance_sigma)

    epf = float(row["EPF Balance"])
    etf = float(row["ETF Balance"])
    epf_j = _jitter_optional_positive(epf, rng, finance_sigma)
    etf_j = _jitter_optional_positive(etf, rng, finance_sigma)

    total_debt_raw = float(row["Total Outstanding Debt"])
    if total_debt_raw <= 0:
        total_debt = 0.0
    else:
        total_debt = _jitter_positive(total_debt_raw, rng, finance_sigma)

    life_prem = float(row["Annual Life Insurance Premium"])
    life_prem_j = _jitter_optional_positive(life_prem, rng, finance_sigma)
    home_loan = float(row["Annual Home Loan Interest"])
    home_loan_j = _jitter_optional_positive(home_loan, rng, finance_sigma)
    donations = float(row["Annual Donations"])
    donations_j = _jitter_optional_positive(donations, rng, finance_sigma)

    health_insurance = _parse_bool(row["Has Health Insurance"])
    horizon = int(row["Investment Horizon (Years)"])
    horizon = int(np.clip(horizon + int(round(rng.normal(0, 1.5))), 1, 40))

    dob = str(row["Date of Birth"]).strip()
    archetype = infer_archetype(age, occupation)
    risk_tolerance = _sample_risk(archetype, rng)

    if anonymize_names:
        full_name = _build_full_name(rng, gender)
    else:
        full_name = str(row["Full Name"]).strip()

    annual_income = sum(float(s["monthly_amount"]) for s in sources if s["is_taxable"]) * 12.0

    rent_paid_annual = 0.0
    taxable_after = apply_deductions(
        annual_income=annual_income,
        rules=rules,
        rent_paid_annual=rent_paid_annual,
        life_insurance_premium_annual=life_prem_j,
        health_insurance_premium_annual=15_000.0 if health_insurance else 0.0,
        home_loan_interest_annual=home_loan_j,
        donations_annual=donations_j,
    )
    baseline_tax = compute_annual_tax(taxable_after, rules)
    effective_tax_rate = baseline_tax / annual_income if annual_income > 0 else 0.0

    monthly_disposable = gross_monthly - monthly_expenses - monthly_debt - (baseline_tax / 12.0)
    monthly_disposable = max(-gross_monthly, monthly_disposable)
    savings_rate = (
        max(0.0, min(1.0, monthly_disposable / gross_monthly)) if gross_monthly > 0 else 0.0
    )
    debt_to_income = total_debt / annual_income if annual_income > 0 else 0.0

    return {
        "profile_id": str(uuid.uuid4()),
        "full_name": full_name,
        "date_of_birth": dob,
        "age_years": age,
        "gender": gender,
        "district": district,
        "marital_status": marital,
        "occupation": occupation,
        "dependents": dependents,
        "years_employed": years_employed,
        "gross_monthly_income_lkr": _round_lkr(gross_monthly),
        "monthly_expenses_lkr": _round_lkr(monthly_expenses),
        "monthly_debt_service_lkr": _round_lkr(monthly_debt),
        "liquid_savings_lkr": _round_lkr(liquid),
        "existing_investments_lkr": _round_lkr(investments),
        "total_debt_lkr": _round_lkr(total_debt),
        "epf_balance_lkr": _round_lkr(epf_j),
        "etf_balance_lkr": _round_lkr(etf_j),
        "health_insurance": health_insurance,
        "life_insurance_premium_annual_lkr": _round_lkr(life_prem_j),
        "home_loan_interest_annual_lkr": _round_lkr(home_loan_j),
        "donations_annual_lkr": _round_lkr(donations_j),
        "risk_tolerance": risk_tolerance,
        "investment_horizon_years": horizon,
        "income_sources_json": json.dumps(sources, separators=(",", ":")),
        "tax_year": tax_year_tag,
        "gross_annual_taxable_income_lkr": _round_lkr(annual_income),
        "baseline_tax_liability_lkr": _round_lkr(baseline_tax),
        "effective_tax_rate": float(round(effective_tax_rate, 6)),
        "disposable_income_monthly_lkr": _round_lkr(monthly_disposable),
        "savings_rate": float(round(savings_rate, 6)),
        "debt_to_income": float(round(debt_to_income, 6)),
        "archetype": archetype,
    }


def ey_reference_to_profiles_dataframe(
    ey_df: pd.DataFrame,
    *,
    rules_path: Path | None = None,
    finance_sigma: float = 0.0,
    seed: int = 42,
    anonymize_names: bool = False,
) -> pd.DataFrame:
    """Convert every EY row to PROFILE_COLUMNS (sigma=0 reproduces structure w/o jitter)."""
    cfg = GeneratorConfig(rules_path=rules_path or GeneratorConfig().rules_path)
    rules = load_tax_rules(cfg.rules_path)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for _, row in ey_df.iterrows():
        ty = _norm_tax_year(row["Tax Year"])
        rows.append(
            ey_series_to_profile_row(
                row,
                rng=rng,
                rules=rules,
                tax_year_tag=ty,
                finance_sigma=finance_sigma,
                anonymize_names=anonymize_names,
            )
        )
    out = pd.DataFrame(rows, columns=list(PROFILE_COLUMNS[:-1]))
    out["split"] = "reference"
    return out[list(PROFILE_COLUMNS)]


@dataclass
class ReferenceMatchedConfig:
    n_rows: int = 22_000
    seed: int = 42
    finance_sigma: float = 0.055
    train_frac: float = 0.70
    val_frac: float = 0.15
    test_frac: float = 0.15
    tax_year: str = "2024_25"
    rules_path: Path | None = None


def generate_reference_matched_profiles(
    ey_df: pd.DataFrame,
    cfg: ReferenceMatchedConfig | None = None,
) -> pd.DataFrame:
    """Bootstrap sample EY rows with financial jitter; output PROFILE_COLUMNS."""
    cfg = cfg or ReferenceMatchedConfig()
    rules_path = cfg.rules_path or GeneratorConfig().rules_path
    rules = load_tax_rules(rules_path)
    rng = np.random.default_rng(cfg.seed)

    n_ref = len(ey_df)
    idx_pool = np.arange(n_ref)

    rows: list[dict[str, Any]] = []
    for _ in range(cfg.n_rows):
        j = int(rng.choice(idx_pool))
        row = ey_df.iloc[j]
        d = ey_series_to_profile_row(
            row,
            rng=rng,
            rules=rules,
            tax_year_tag=cfg.tax_year,
            finance_sigma=cfg.finance_sigma,
            anonymize_names=True,
        )
        rows.append(d)

    df = pd.DataFrame(rows, columns=list(PROFILE_COLUMNS[:-1]))
    gcfg = GeneratorConfig(
        seed=cfg.seed + 1,
        train_frac=cfg.train_frac,
        val_frac=cfg.val_frac,
        test_frac=cfg.test_frac,
    )
    df["split"] = _split_assignment(np.random.default_rng(cfg.seed + 2), len(df), gcfg)
    return df[list(PROFILE_COLUMNS)]


def write_reference_matched(
    df: pd.DataFrame,
    out_dir: Path,
    *,
    basename: str = "profiles_reference_matched",
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / f"{basename}.parquet"
    csv_path = out_dir / f"{basename}.csv"
    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)
    return {"parquet": parquet_path, "csv": csv_path}
