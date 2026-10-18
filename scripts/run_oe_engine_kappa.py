#!/usr/bin/env python3
"""Score Cohen's kappa for OE Engine relief recommendations.

Example (from repo root):
  .\\.venv-backend\\Scripts\\python.exe scripts/run_oe_engine_kappa.py `
    --csv models/opt-explain-engine/evaluation/fixtures/kappa_sample_reliefs.csv `
    --out-json reports/oe_engine_kappa.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "models" / "opt-explain-engine" / "evaluation"
sys.path.insert(0, str(EVAL_DIR))

from kappa import kappa_from_csv, write_result_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Cohen's kappa for OE Engine relief recommendation validation"
    )
    ap.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="CSV with system_label and expert_label (plus compare_group_id)",
    )
    ap.add_argument(
        "--weighted",
        action="store_true",
        help="Also compute linear weighted kappa (for ordinal 0-4 grades)",
    )
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    result = kappa_from_csv(args.csv, weighted=args.weighted)
    print(f"Pairs:                {result.n_pairs}")
    print(f"Observed agreement:   {result.observed_agreement:.4f}")
    print(f"Cohen's kappa:        {result.cohen_kappa:.4f}")
    if result.weighted_kappa is not None:
        print(f"Weighted kappa:       {result.weighted_kappa:.4f}")
    print(f"Interpretation:       {result.interpretation}")
    print(f"Labels:               {', '.join(result.labels)}")
    print("Confusion (rows=expert, cols=system):")
    print(f"  {result.labels}")
    for label, row in zip(result.labels, result.confusion):
        print(f"  {label:>20s} {row}")
    for note in result.notes:
        print(f"Note: {note}")

    if args.out_json:
        write_result_json(result, args.out_json)
        print(f"Wrote {args.out_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
