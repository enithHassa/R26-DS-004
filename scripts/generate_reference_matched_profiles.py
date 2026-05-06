"""Generate synthetic profiles (22k–25k) matched to an EY reference CSV.

Bootstrap-resamples anonymised reference rows, jitters finance fields, recomputes
tax via ``sl_tax_2024_25.yaml``, and writes parquet + CSV next to the generic
synthetic outputs.

Example::

    source .venv-gen/bin/activate
    python scripts/generate_reference_matched_profiles.py \\
        --reference ~/Downloads/research_ready_profiles_2_2-2.csv \\
        --rows 22000 --seed 42 --finance-sigma 0.055

"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = REPO_ROOT / "models" / "personalized-recommendation"
for path in (str(REPO_ROOT), str(ML_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data.reference_profile_generator import (  # noqa: E402
    ReferenceMatchedConfig,
    generate_reference_matched_profiles,
    load_ey_reference_csv,
    write_reference_matched,
    ey_reference_to_profiles_dataframe,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="Path to research_ready_profiles / EY-style CSV.",
    )
    p.add_argument("--rows", type=int, default=22_000, help="Synthetic rows (use 20000–25000).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--finance-sigma",
        type=float,
        default=0.055,
        help="Lognormal jitter σ on positive financial amounts (≈ multiplicative CV).",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "data" / "synthetic" / "reference_matched",
    )
    p.add_argument("--tax-year", default="2024_25")
    p.add_argument(
        "--write-reference-parquet",
        action="store_true",
        help="Also write ey_reference_profiles_fmt.csv (mapped reference, σ=0) for validation.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ey_df = load_ey_reference_csv(args.reference)
    print(f"[ref-matched] Loaded reference n={len(ey_df)} from {args.reference}")

    cfg = ReferenceMatchedConfig(
        n_rows=args.rows,
        seed=args.seed,
        finance_sigma=args.finance_sigma,
        tax_year=args.tax_year,
    )
    syn = generate_reference_matched_profiles(ey_df, cfg)
    paths = write_reference_matched(syn, args.out_dir)
    print(f"[ref-matched] Wrote {paths['csv']}")
    print(f"[ref-matched] Shape {syn.shape}")
    print("[ref-matched] occupation:\n", syn["occupation"].value_counts().to_string())

    if args.write_reference_parquet:
        ref_fmt = ey_reference_to_profiles_dataframe(
            ey_df,
            finance_sigma=0.0,
            seed=args.seed,
            anonymize_names=True,
        )
        rp = args.out_dir / "ey_reference_profiles_fmt.csv"
        ref_fmt.to_csv(rp, index=False)
        print(f"[ref-matched] Wrote mapped reference σ=0 → {rp}")

    print("[ref-matched] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
