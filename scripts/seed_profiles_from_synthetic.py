"""Bulk-load synthetic financial profiles into Postgres.

Reads a synthetic dataset (CSV or parquet) and inserts each row into the
``users`` + ``financial_profiles`` tables via SQLAlchemy core. Existing
profiles are skipped so the script is idempotent.

Usage:

.. code-block:: bash

    source .venv-backend/bin/activate
    alembic upgrade head
    python -m scripts.seed_profiles_from_synthetic --limit 5000

Pass ``--limit -1`` to seed every row.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pandas as pd
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]
COMPONENT_ROOT = REPO_ROOT / "backend" / "comp-personalized-recommendation"
for path in (str(REPO_ROOT), str(COMPONENT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.shared.config.database import SessionLocal  # noqa: E402

import app.models  # noqa: E402, F401  registers ORM tables
from app.models.profile import FinancialProfile  # noqa: E402
from app.models.user import User  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=REPO_ROOT / "data" / "synthetic" / "profiles.csv",
        help="Path to synthetic profiles dataset (.csv or .parquet).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5_000,
        help="Number of rows to seed. Use -1 to load every row.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows per INSERT batch (per table).",
    )
    return parser.parse_args(argv)


_PROVINCE_TO_DISTRICT: dict[str, str] = {
    "Western": "Colombo",
    "Central": "Kandy",
    "Southern": "Galle",
    "Northern": "Jaffna",
    "Eastern": "Trincomalee",
    "North Western": "Kurunegala",
    "North Central": "Anuradhapura",
    "Uva": "Badulla",
    "Sabaragamuwa": "Ratnapura",
}


def _parse_age_band_midpoint(age_band: str) -> int:
    cleaned = age_band.strip()
    if cleaned.endswith("+"):
        return int(cleaned[:-1])
    if "-" in cleaned:
        lower, upper = cleaned.split("-", 1)
        return (int(lower) + int(upper)) // 2
    return int(cleaned)


def _derive_date_of_birth(row: dict) -> date:
    if row.get("date_of_birth"):
        return pd.to_datetime(row["date_of_birth"]).date()
    # Verified synthetic dataset stores age bands, not full DOB.
    age_mid = _parse_age_band_midpoint(str(row.get("age_band", "35-39")))
    tax_year = str(row.get("tax_year", "2024_25"))
    snapshot_year = int(tax_year.split("_", 1)[0]) + 1
    return date(snapshot_year - age_mid, 6, 30)


def _derive_district(row: dict) -> str:
    district = str(row.get("district") or "").strip()
    if district:
        return district
    province = str(row.get("province") or "").strip()
    return _PROVINCE_TO_DISTRICT.get(province, "Colombo")


def _load_dataset(dataset_path: Path) -> pd.DataFrame:
    suffix = dataset_path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(dataset_path)
    if suffix == ".csv":
        return pd.read_csv(dataset_path)
    raise ValueError(f"Unsupported dataset format: {dataset_path.suffix}")


def _row_to_user(row: dict) -> dict:
    profile_uuid = UUID(row["profile_id"])
    return {
        "id": uuid4(),
        "email": f"synthetic-{profile_uuid.hex}@tax-advisory.local",
        "full_name": row["full_name"],
        "is_active": True,
    }


def _row_to_profile(row: dict, *, user_id: UUID) -> dict:
    return {
        "id": UUID(row["profile_id"]),
        "user_id": user_id,
        "full_name": row["full_name"],
        "date_of_birth": _derive_date_of_birth(row),
        "gender": row["gender"],
        "district": _derive_district(row),
        "marital_status": row["marital_status"],
        "occupation": row["occupation"],
        "dependents": int(row["dependents"]),
        "years_employed": int(row["years_employed"]),
        "gross_monthly_income": Decimal(str(row["gross_monthly_income_lkr"])),
        "monthly_expenses": Decimal(str(row["monthly_expenses_lkr"])),
        "monthly_debt_service": Decimal(str(row["monthly_debt_service_lkr"])),
        "liquid_savings": Decimal(str(row["liquid_savings_lkr"])),
        "existing_investments": Decimal(str(row["existing_investments_lkr"])),
        "total_debt": Decimal(str(row["total_debt_lkr"])),
        "epf_balance": Decimal(str(row["epf_balance_lkr"])),
        "etf_balance": Decimal(str(row["etf_balance_lkr"])),
        "health_insurance": bool(row["health_insurance"]),
        "life_insurance_premium_annual": Decimal(str(row["life_insurance_premium_annual_lkr"])),
        "home_loan_interest_annual": Decimal(str(row["home_loan_interest_annual_lkr"])),
        "donations_annual": Decimal(str(row["donations_annual_lkr"])),
        "risk_tolerance": row["risk_tolerance"],
        "investment_horizon_years": int(row["investment_horizon_years"]),
        "income_sources": json.loads(row["income_sources_json"]),
        "tax_year": row["tax_year"],
    }


def _existing_profile_ids(db: Session, candidate_ids: list[UUID]) -> set[UUID]:
    if not candidate_ids:
        return set()
    rows = db.execute(
        select(FinancialProfile.id).where(FinancialProfile.id.in_(candidate_ids))
    ).all()
    return {r[0] for r in rows}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_path = args.dataset
    if not dataset_path.exists():
        print(f"[seed] Dataset not found at {dataset_path}.")
        return 1

    df = _load_dataset(dataset_path)
    if args.limit != -1:
        df = df.head(args.limit)

    print(f"[seed] Loading {len(df):,} rows into Postgres (batch={args.batch_size})...")

    inserted = 0
    skipped = 0
    with SessionLocal() as db:
        for batch_start in range(0, len(df), args.batch_size):
            batch = df.iloc[batch_start : batch_start + args.batch_size].to_dict(orient="records")
            ids = [UUID(r["profile_id"]) for r in batch]
            already = _existing_profile_ids(db, ids)
            new_rows = [r for r in batch if UUID(r["profile_id"]) not in already]
            skipped += len(batch) - len(new_rows)

            if not new_rows:
                continue

            users = [_row_to_user(r) for r in new_rows]
            db.execute(insert(User), users)
            profile_rows = [
                _row_to_profile(r, user_id=u["id"]) for r, u in zip(new_rows, users, strict=True)
            ]
            db.execute(insert(FinancialProfile), profile_rows)
            db.commit()
            inserted += len(profile_rows)
            print(f"[seed]  inserted {inserted:,} / {len(df):,} (skipped {skipped:,})")

    print(f"[seed] Done. inserted={inserted:,}, skipped_existing={skipped:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
