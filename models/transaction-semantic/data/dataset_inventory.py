"""Print row counts and breakdowns for labeling / training (Postgres).

Run from repo root with backend env and DB configured:

    python models/transaction-semantic/data/dataset_inventory.py
    python models/transaction-semantic/data/dataset_inventory.py --min-desc-len 12 --min-confidence 0.55
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.shared.config.database import engine


def _table_exists(conn, name: str) -> bool:
    try:
        conn.execute(text(f"SELECT 1 FROM {name} LIMIT 1"))
        return True
    except Exception:
        return False


def run_inventory(*, min_desc_len: int, min_confidence: float, exclude_flagged: bool) -> dict:
    out: dict = {"tables": {}, "extracted": {}, "transactions": {}, "documents": {}}
    flagged_sql = " AND NOT et.is_flagged " if exclude_flagged else ""
    conf_sql = (
        " AND (et.confidence IS NULL OR et.confidence >= :min_conf) "
        if min_confidence > 0
        else ""
    )

    with engine.connect() as conn:
        for t in ("documents", "extracted_transactions", "transactions"):
            out["tables"][t] = _table_exists(conn, t)

        if out["tables"].get("extracted_transactions"):
            total = conn.execute(text("SELECT COUNT(*) FROM extracted_transactions")).scalar()
            out["extracted"]["total_rows"] = int(total or 0)

            params: dict = {"min_len": min_desc_len}
            if min_confidence > 0:
                params["min_conf"] = min_confidence

            suitable = text(
                f"""
                SELECT COUNT(*) FROM extracted_transactions et
                WHERE et.description IS NOT NULL
                  AND LENGTH(TRIM(et.description)) >= :min_len
                  AND et.amount_lkr > 0
                  {flagged_sql}
                  {conf_sql}
                """,
            )
            n = conn.execute(suitable, params).scalar()
            out["extracted"]["suitable_for_labeling"] = int(n or 0)

            by_bank = conn.execute(
                text(
                    f"""
                    SELECT COALESCE(d.bank_detected, '(null)') AS bank, COUNT(*)::int AS n
                    FROM extracted_transactions et
                    JOIN documents d ON d.id = et.document_id
                    WHERE et.description IS NOT NULL
                      AND LENGTH(TRIM(et.description)) >= :min_len
                      AND et.amount_lkr > 0
                    {flagged_sql}
                    {conf_sql}
                    GROUP BY 1 ORDER BY n DESC
                    """,
                ),
                params,
            ).mappings().all()
            out["extracted"]["by_bank_detected"] = {r["bank"]: r["n"] for r in by_bank}

            dates = conn.execute(
                text(
                    """
                    SELECT MIN(et.tx_date) AS dmin, MAX(et.tx_date) AS dmax
                    FROM extracted_transactions et
                    """,
                ),
            ).mappings().one()
            out["extracted"]["tx_date_min"] = str(dates["dmin"]) if dates["dmin"] else None
            out["extracted"]["tx_date_max"] = str(dates["dmax"]) if dates["dmax"] else None

        if out["tables"].get("transactions"):
            total = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
            out["transactions"]["total_rows"] = int(total or 0)

        if out["tables"].get("documents"):
            total = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
            out["documents"]["total_rows"] = int(total or 0)

    out["filters"] = {
        "min_desc_len": min_desc_len,
        "min_confidence": min_confidence,
        "exclude_flagged": exclude_flagged,
    }
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Dataset inventory for transaction semantic labeling.")
    p.add_argument("--min-desc-len", type=int, default=10)
    p.add_argument("--min-confidence", type=float, default=0.0)
    p.add_argument("--include-flagged", action="store_true", help="Count rows with is_flagged=true too.")
    p.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    args = p.parse_args()

    data = run_inventory(
        min_desc_len=args.min_desc_len,
        min_confidence=args.min_confidence,
        exclude_flagged=not args.include_flagged,
    )
    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    print("=== Transaction semantic — dataset inventory ===\n")
    print("Tables present:", data["tables"])
    if data["documents"]:
        print(f"documents total rows: {data['documents'].get('total_rows', 'n/a')}")
    if data["extracted"]:
        ex = data["extracted"]
        print(f"extracted_transactions total rows: {ex.get('total_rows', 0)}")
        print(f"extracted date range: {ex.get('tx_date_min')} .. {ex.get('tx_date_max')}")
        print(f"suitable_for_labeling (filters={data['filters']}): {ex.get('suitable_for_labeling', 0)}")
        banks = ex.get("by_bank_detected") or {}
        if banks:
            print("\nSuitable rows by bank_detected:")
            for b, n in list(banks.items())[:25]:
                print(f"  {b}: {n}")
            if len(banks) > 25:
                print(f"  ... +{len(banks) - 25} more banks")
    if data["transactions"]:
        print(f"\ntransactions total rows: {data['transactions'].get('total_rows', 0)}")
    print("\nNext: python models/transaction-semantic/data/build_labeling_dataset.py --source extracted ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
