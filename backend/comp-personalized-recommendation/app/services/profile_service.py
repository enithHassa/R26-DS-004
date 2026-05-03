"""Financial profile service layer (FR1, FR2 — Phase 2 / WP4).

Owns all reads and writes of the ``financial_profiles`` table plus the
computation of ``DerivedFeatures``. Routers should never reach for the ORM
model directly; they call into this module.

The derived-feature pipeline mirrors the offline generator under
``models/personalized-recommendation/data/profile_generator.py`` so that
features computed at request time agree with the synthetic training set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import component_settings
from app.models.profile import FinancialProfile as FinancialProfileORM
from app.models.user import User as UserORM
from app.schemas.profile import (
    DerivedFeatures,
    FinancialProfileBase,
    FinancialProfileCreate,
    FinancialProfileUpdate,
)


class ProfileNotFoundError(LookupError):
    """Raised when a profile cannot be located by id."""


@dataclass(frozen=True)
class _ProfilePage:
    items: list[FinancialProfileORM]
    total: int


# ---------------------------------------------------------------------------
# Tax rules cache
# ---------------------------------------------------------------------------


def _import_rules_engine() -> Any:
    """Lazily import the offline rules engine.

    The ML package lives at ``models/personalized-recommendation/`` (with
    a hyphen) so its sub-packages aren't importable as regular dotted
    modules. We add the directory to ``sys.path`` on first call.
    """
    import sys

    ml_root = component_settings.COMP_RECOMMENDATION_RULES_PATH.parent.parent
    if str(ml_root) not in sys.path:
        sys.path.insert(0, str(ml_root))
    from rules.engine import (  # type: ignore[import-not-found]
        apply_deductions,
        compute_annual_tax,
        load_tax_rules,
    )

    return apply_deductions, compute_annual_tax, load_tax_rules


@lru_cache(maxsize=4)
def _load_rules(rules_path: Path) -> Any:
    apply_deductions, compute_annual_tax, load_tax_rules = _import_rules_engine()
    rules = load_tax_rules(rules_path)
    return rules, apply_deductions, compute_annual_tax


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_user(db: Session, user_id: UUID | None, full_name: str) -> UserORM:
    """Find/create the owning user. Phase 2 doesn't have auth wired yet so we
    materialise a placeholder user when ``user_id`` is omitted."""
    if user_id is not None:
        user = db.get(UserORM, user_id)
        if user is None:
            raise ProfileNotFoundError(f"User {user_id} does not exist")
        return user

    placeholder_email = f"profile-{uuid4().hex[:12]}@synthetic.local"
    user = UserORM(email=placeholder_email, full_name=full_name)
    db.add(user)
    db.flush()
    return user


def _payload_to_columns(payload: FinancialProfileBase | FinancialProfileUpdate) -> dict[str, Any]:
    """Dump the schema to ORM-ready columns.

    ``mode='json'`` converts ``Decimal``/``date``/``Enum`` to JSON-serialisable
    primitives, which is required for the ``income_sources`` JSON column.
    Top-level Decimal-typed columns are restored to ``Decimal`` so SQLAlchemy
    Numeric coercion stays clean.
    """
    raw = payload.model_dump(exclude_unset=True, mode="json")
    decimal_fields = {
        "gross_monthly_income",
        "monthly_expenses",
        "monthly_debt_service",
        "liquid_savings",
        "existing_investments",
        "total_debt",
        "epf_balance",
        "etf_balance",
        "life_insurance_premium_annual",
        "home_loan_interest_annual",
        "donations_annual",
    }
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if key == "date_of_birth" and isinstance(value, str):
            out[key] = date.fromisoformat(value)
        elif key in decimal_fields and value is not None:
            out[key] = Decimal(str(value))
        else:
            out[key] = value
    return out


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_profile(
    db: Session,
    payload: FinancialProfileCreate,
    *,
    user_id: UUID | None = None,
) -> FinancialProfileORM:
    user = _ensure_user(db, user_id, payload.full_name)
    columns = _payload_to_columns(payload)
    profile = FinancialProfileORM(user_id=user.id, **columns)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_profile(db: Session, profile_id: UUID) -> FinancialProfileORM:
    profile = db.get(FinancialProfileORM, profile_id)
    if profile is None:
        raise ProfileNotFoundError(f"Profile {profile_id} not found")
    return profile


def update_profile(
    db: Session,
    profile_id: UUID,
    payload: FinancialProfileUpdate,
) -> FinancialProfileORM:
    profile = get_profile(db, profile_id)
    columns = _payload_to_columns(payload)
    for key, value in columns.items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile_id: UUID) -> None:
    profile = get_profile(db, profile_id)
    db.delete(profile)
    db.commit()


def list_profiles(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    occupation: str | None = None,
    district: str | None = None,
) -> _ProfilePage:
    page = max(1, page)
    page_size = max(1, min(200, page_size))
    stmt = select(FinancialProfileORM)
    count_stmt = select(func.count()).select_from(FinancialProfileORM)
    if occupation:
        stmt = stmt.where(FinancialProfileORM.occupation == occupation)
        count_stmt = count_stmt.where(FinancialProfileORM.occupation == occupation)
    if district:
        stmt = stmt.where(FinancialProfileORM.district == district)
        count_stmt = count_stmt.where(FinancialProfileORM.district == district)
    stmt = stmt.order_by(FinancialProfileORM.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(stmt).scalars().all())
    total = int(db.execute(count_stmt).scalar_one())
    return _ProfilePage(items=items, total=total)


# ---------------------------------------------------------------------------
# Derived features
# ---------------------------------------------------------------------------


def _age_years(dob: date, snapshot: date | None = None) -> int:
    snapshot = snapshot or date.today()
    return snapshot.year - dob.year - ((snapshot.month, snapshot.day) < (dob.month, dob.day))


def _annual_taxable_income(profile: FinancialProfileORM) -> Decimal:
    sources = profile.income_sources or []
    if sources:
        annual = sum(
            Decimal(str(s.get("monthly_amount", 0))) for s in sources if s.get("is_taxable", True)
        ) * Decimal("12")
        return annual
    return profile.gross_monthly_income * Decimal("12")


def _eligibility_flags(
    *,
    age: int,
    profile: FinancialProfileORM,
    annual_income: Decimal,
    disposable_monthly: Decimal,
) -> dict[str, bool]:
    return {
        "above_tax_threshold": annual_income > Decimal("1200000"),
        "has_disposable_income": disposable_monthly > Decimal("0"),
        "has_employer_provident": profile.epf_balance > 0 or profile.occupation == "employee",
        "has_health_insurance": bool(profile.health_insurance),
        "has_home_loan": profile.home_loan_interest_annual > 0,
        "is_retirement_eligible": age >= 50,
        "has_dependents": profile.dependents > 0,
        "has_liquidity_buffer": profile.liquid_savings >= profile.monthly_expenses * 3,
    }


def compute_derived_features(profile: FinancialProfileORM) -> DerivedFeatures:
    """Compute the derived features used by the ranker / impact engine."""
    rules, apply_deductions, compute_annual_tax = _load_rules(
        component_settings.COMP_RECOMMENDATION_RULES_PATH
    )

    age = _age_years(profile.date_of_birth)
    annual_income = _annual_taxable_income(profile)

    taxable_after = apply_deductions(
        annual_income=float(annual_income),
        rules=rules,
        life_insurance_premium_annual=float(profile.life_insurance_premium_annual),
        health_insurance_premium_annual=15_000.0 if profile.health_insurance else 0.0,
        home_loan_interest_annual=float(profile.home_loan_interest_annual),
        donations_annual=float(profile.donations_annual),
    )
    baseline_tax = Decimal(str(compute_annual_tax(taxable_after, rules)))
    effective_rate = float(baseline_tax / annual_income) if annual_income > 0 else 0.0

    monthly_tax = baseline_tax / Decimal("12")
    monthly_disposable = (
        profile.gross_monthly_income
        - profile.monthly_expenses
        - profile.monthly_debt_service
        - monthly_tax
    )
    annual_disposable = monthly_disposable * Decimal("12")
    savings_rate = float(monthly_disposable / profile.gross_monthly_income) if profile.gross_monthly_income > 0 else 0.0
    savings_rate = max(0.0, min(1.0, savings_rate))

    debt_to_income = float(profile.total_debt / annual_income) if annual_income > 0 else 0.0
    liquidity_ratio = float(profile.liquid_savings / profile.monthly_expenses) if profile.monthly_expenses > 0 else 0.0

    return DerivedFeatures(
        profile_id=str(profile.id),
        age_years=age,
        disposable_income_monthly=monthly_disposable.quantize(Decimal("0.01")),
        disposable_income_annual=annual_disposable.quantize(Decimal("0.01")),
        savings_rate=round(savings_rate, 6),
        debt_to_income=round(debt_to_income, 6),
        liquidity_ratio=round(liquidity_ratio, 6),
        gross_annual_taxable_income=annual_income.quantize(Decimal("0.01")),
        baseline_tax_liability_annual=baseline_tax.quantize(Decimal("0.01")),
        effective_tax_rate=round(effective_rate, 6),
        eligibility_flags=_eligibility_flags(
            age=age,
            profile=profile,
            annual_income=annual_income,
            disposable_monthly=monthly_disposable,
        ),
    )


__all__ = [
    "ProfileNotFoundError",
    "compute_derived_features",
    "create_profile",
    "delete_profile",
    "get_profile",
    "list_profiles",
    "update_profile",
]
