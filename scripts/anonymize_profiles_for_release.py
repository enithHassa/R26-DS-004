"""Anonymize a profiles CSV for release (remove direct identifiers).

Transforms:
- full_name -> Taxpayer_00001... (stable by row order)
- date_of_birth dropped (or set to empty)
- age_years -> age_band (categorical ranges)
- district -> province (generalization)

Writes a new CSV (does not overwrite by default).

Example:
    .venv-gen/bin/python scripts/anonymize_profiles_for_release.py \
      --in-csv data/synthetic/reference_matched/profiles_reference_matched.csv \
      --out-csv data/synthetic/reference_matched_anonymized/profiles_reference_matched_anonymized.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


_DISTRICT_TO_PROVINCE: dict[str, str] = {
    # Western
    "Colombo": "Western",
    "Gampaha": "Western",
    "Kalutara": "Western",
    # Central
    "Kandy": "Central",
    "Matale": "Central",
    "Nuwara Eliya": "Central",
    # Southern
    "Galle": "Southern",
    "Matara": "Southern",
    "Hambantota": "Southern",
    # Northern
    "Jaffna": "Northern",
    "Kilinochchi": "Northern",
    "Mannar": "Northern",
    "Vavuniya": "Northern",
    "Mullaitivu": "Northern",
    # Eastern
    "Batticaloa": "Eastern",
    "Ampara": "Eastern",
    "Trincomalee": "Eastern",
    # North Western
    "Kurunegala": "North Western",
    "Puttalam": "North Western",
    # North Central
    "Anuradhapura": "North Central",
    "Polonnaruwa": "North Central",
    # Uva
    "Badulla": "Uva",
    "Moneragala": "Uva",
    # Sabaragamuwa
    "Ratnapura": "Sabaragamuwa",
    "Kegalle": "Sabaragamuwa",
}


def age_to_band(age: float | int) -> str:
    try:
        a = int(age)
    except Exception:
        return "unknown"
    if a < 18:
        return "<18"
    if a <= 24:
        return "18-24"
    if a <= 29:
        return "25-29"
    if a <= 34:
        return "30-34"
    if a <= 39:
        return "35-39"
    if a <= 44:
        return "40-44"
    if a <= 49:
        return "45-49"
    if a <= 54:
        return "50-54"
    if a <= 59:
        return "55-59"
    if a <= 64:
        return "60-64"
    if a <= 70:
        return "65-70"
    return "70+"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--in-csv", type=Path, required=True)
    p.add_argument("--out-csv", type=Path, required=True)
    p.add_argument("--drop-dob", action="store_true", default=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    df = pd.read_csv(args.in_csv)

    # full_name -> Taxpayer_xxxxx
    df["full_name"] = [f"Taxpayer_{i+1:05d}" for i in range(len(df))]

    # age_years -> age_band (keep age_years only if needed; default drop)
    if "age_years" in df.columns:
        df["age_band"] = df["age_years"].map(age_to_band)
        df = df.drop(columns=["age_years"])

    # district -> province (keep district if mapping missing)
    if "district" in df.columns:
        df["province"] = df["district"].astype(str).map(lambda d: _DISTRICT_TO_PROVINCE.get(d, "Unknown"))
        df = df.drop(columns=["district"])

    # drop DOB
    if args.drop_dob and "date_of_birth" in df.columns:
        df = df.drop(columns=["date_of_birth"])

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, index=False)
    print(f"[anonymize] wrote {args.out_csv} rows={len(df)} cols={len(df.columns)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

