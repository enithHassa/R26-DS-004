"""Generate the Phase 1 synthetic financial profiles dataset.

Uses the deterministic generator under
``models/personalized-recommendation/data/profile_generator.py``. Writes
parquet + CSV preview + a data card to ``data/synthetic/``.

Usage:

.. code-block:: bash

    source .venv-ml/bin/activate
    python -m scripts.generate_synthetic_profiles --rows 25000 --seed 42

"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ML_ROOT = REPO_ROOT / "models" / "personalized-recommendation"

# Hyphenated dir names are not importable as packages directly. Putting the
# ML root on sys.path makes ``rules``, ``data``, ``features`` etc. importable
# as top-level modules from any process that runs this script.
for path in (str(REPO_ROOT), str(ML_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from data.profile_generator import GeneratorConfig, generate_profiles, write_profiles  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=25_000, help="Number of synthetic profiles to generate.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "data" / "synthetic",
        help="Output directory for parquet + preview CSV + data card.",
    )
    parser.add_argument("--tax-year", default="2024_25", help="Snapshot tax year tag.")
    parser.add_argument(
        "--rules-path",
        type=Path,
        default=ML_ROOT / "rules" / "sl_tax_2024_25.yaml",
        help="Path to the YAML tax rule pack.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = GeneratorConfig(
        n_rows=args.rows,
        seed=args.seed,
        tax_year=args.tax_year,
        rules_path=args.rules_path,
    )

    print(f"[generator] Generating {cfg.n_rows:,} profiles (seed={cfg.seed})...")
    df = generate_profiles(cfg)

    print(f"[generator] DataFrame shape: {df.shape}")
    print("[generator] Archetype counts:")
    print(df["archetype"].value_counts().to_string())

    paths = write_profiles(df, args.out_dir)
    for label, p in paths.items():
        print(f"[generator] Wrote {label}: {p.relative_to(REPO_ROOT)}")

    print("[generator] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
