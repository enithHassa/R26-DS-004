#!/usr/bin/env python3
"""Run Phase 6 offline evaluation: frozen artifacts + ablation + fairness.

Example (from repo root):
  .venv-backend/bin/python scripts/run_phase6_evaluation.py \\
    --csv "data/synthetic/profiles_corrected_tax (1).csv" \\
    --catalog models/personalized-recommendation/rules/strategy_catalog.yaml \\
    --user-meta backend/comp-personalized-recommendation/app/artifacts/user_feature_meta.json \\
    --artifacts-dir backend/comp-personalized-recommendation/app/artifacts \\
    --out-json reports/phase6_eval.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "models" / "personalized-recommendation"))

from evaluation.runner import run_offline_evaluation  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 6 offline evaluation")
    ap.add_argument("--csv", type=Path, required=True, help="Synthetic profiles CSV with split column")
    ap.add_argument("--catalog", type=Path, required=True)
    ap.add_argument("--user-meta", type=Path, required=True, help="user_feature_meta.json")
    ap.add_argument("--artifacts-dir", type=Path, default=None, help="Phase 4 artifact directory")
    ap.add_argument("--train-limit", type=int, default=8000)
    ap.add_argument("--eval-limit", type=int, default=1500)
    ap.add_argument("--eval-split", type=str, default="val")
    ap.add_argument("--no-ablation", action="store_true", help="Skip retrained ablation arms")
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    report = run_offline_evaluation(
        csv_path=args.csv,
        catalog_path=args.catalog,
        user_meta_path=args.user_meta,
        artifacts_dir=args.artifacts_dir,
        train_limit=args.train_limit,
        eval_limit=args.eval_limit,
        eval_split=args.eval_split,
        include_ablation=not args.no_ablation,
    )

    print(f"Eval split={report.eval_split} profiles={report.n_profiles} strategies={report.n_strategies}")
    for row in report.leaderboard():
        ndcg5 = row.metrics.get("ndcg@5", 0.0)
        mrr = row.metrics.get("mrr", 0.0)
        disp = row.fairness.get("occupation", {}).get("disparity", 0.0)
        print(f"  {row.name:42s}  ndcg@5={ndcg5:.4f}  mrr={mrr:.4f}  occ_disparity={disp:.4f}")

    if args.out_json:
        report.write_json(args.out_json)
        print(f"Wrote {args.out_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
