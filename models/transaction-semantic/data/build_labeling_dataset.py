"""Build candidate labeling datasets from persisted DB rows.

Supports:
- ``extracted_transactions`` (document upload pipeline) — default
- ``transactions`` (legacy / direct persist)

Outputs (under ``--output-dir``):
- ``label_candidates.csv`` — rich columns for taxonomy + rule features
- ``llm_bootstrap_requests.jsonl`` — one JSON object per row for batch LLM labeling
- ``annotation_template.csv`` — same rows + empty reviewer columns

Column rationale (classifier + rule engine):
- ``description``: primary text input (mBERT / TF-IDF).
- ``amount_lkr``, ``amount_band``, ``direction``: numeric / structural features; rules use amount.
- ``tx_date``: time splits and assessment windows.
- ``bank_detected``, ``file_type``, ``content_type``: domain shift + document_type feature.
- ``debit`` / ``credit``: optional explicit split when both exist in source.
- ``reference_no``: weak labels / dispute resolution.
- ``parse_confidence``, ``is_flagged``: quality gate; filter high-confidence rows for auto-labeling.
- ``document_id``, ``filename``, ``row_id``, ``source_table``: audit trail and dedupe keys.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.shared.config.database import engine


def _amount_band(amount_lkr: float) -> str:
    if amount_lkr < 10_000:
        return "lt_10k"
    if amount_lkr < 50_000:
        return "10k_50k"
    if amount_lkr < 200_000:
        return "50k_200k"
    return "gte_200k"


def _doc_type_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return "unknown"
    ct = content_type.lower()
    if "pdf" in ct:
        return "bank_statement_pdf"
    if "csv" in ct:
        return "bank_statement_csv"
    if "spreadsheet" in ct or "excel" in ct:
        return "bank_statement_xlsx"
    if ct.startswith("image/"):
        return "bank_statement_image"
    return "other"


def _doc_type_from_source(source_type: str | None, raw_payload: dict[str, Any] | None) -> str:
    if isinstance(raw_payload, dict):
        ct = str(raw_payload.get("content_type") or "").lower()
        if "pdf" in ct:
            return "bank_statement_pdf"
        if "csv" in ct:
            return "bank_statement_csv"
        if "excel" in ct or "spreadsheet" in ct:
            return "bank_statement_xlsx"
        if ct.startswith("image/"):
            return "bank_statement_image"
    if source_type:
        return source_type
    return "unknown"


def _llm_prompt_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "description": row["description"],
        "amount_lkr": row["amount_lkr"],
        "tx_date": row["tx_date"],
        "direction": row["direction"],
        "bank_code": row["bank_detected"],
        "document_type": row["document_type"],
        "reference_no": row.get("reference_no") or "",
        "task": "Predict one taxonomy label for Sri Lanka IRD income classification.",
        "output_schema": {
            "label": "string",
            "confidence": "number_0_to_1",
            "reasoning": "string",
            "needs_human_review": "boolean",
        },
    }


def _fetch_extracted(
    *,
    limit: int,
    min_date: str | None,
    max_date: str | None,
    min_desc_len: int,
    min_confidence: float,
    exclude_flagged: bool,
    order: str,
) -> list[dict[str, Any]]:
    where = [
        "et.description IS NOT NULL",
        "LENGTH(TRIM(et.description)) >= :min_desc_len",
        "et.amount_lkr > 0",
    ]
    params: dict[str, Any] = {"limit": limit, "min_desc_len": min_desc_len}
    if min_date:
        where.append("et.tx_date >= :min_date")
        params["min_date"] = min_date
    if max_date:
        where.append("et.tx_date <= :max_date")
        params["max_date"] = max_date
    if exclude_flagged:
        where.append("NOT et.is_flagged")
    if min_confidence > 0:
        where.append("(et.confidence IS NULL OR et.confidence >= :min_conf)")
        params["min_conf"] = min_confidence

    order_sql = "et.tx_date DESC, et.id ASC"
    if order == "random":
        order_sql = "RANDOM()"
    elif order == "bank_stratified":
        # Round-robin-ish: order by bank hash then date (simple stratification without window functions)
        order_sql = "d.bank_detected NULLS LAST, RANDOM()"

    sql = f"""
        SELECT
            et.id AS row_id,
            et.document_id,
            d.filename,
            d.content_type,
            d.bank_detected,
            et.tx_date,
            et.description,
            et.reference_no,
            et.amount_lkr,
            et.debit,
            et.credit,
            et.direction::text AS direction,
            et.confidence AS parse_confidence,
            et.is_flagged,
            et.raw_row_json
        FROM extracted_transactions et
        JOIN documents d ON d.id = et.document_id
        WHERE {" AND ".join(where)}
        ORDER BY {order_sql}
        LIMIT :limit
    """
    rows: list[dict[str, Any]] = []
    with engine.connect() as conn:
        for row in conn.execute(text(sql), params).mappings().all():
            amount = float(row["amount_lkr"])
            raw_json = row["raw_row_json"] if isinstance(row["raw_row_json"], dict) else {}
            file_type = str(raw_json.get("file_type") or "")
            content_type = row.get("content_type")
            rows.append(
                {
                    "row_id": str(row["row_id"]),
                    "source_table": "extracted_transactions",
                    "document_id": str(row["document_id"]),
                    "filename": row["filename"] or "",
                    "content_type": content_type or "",
                    "document_type": _doc_type_from_content_type(content_type),
                    "bank_detected": (row["bank_detected"] or "").strip(),
                    "file_type": file_type,
                    "tx_date": row["tx_date"].isoformat(),
                    "description": str(row["description"]).strip(),
                    "reference_no": (row["reference_no"] or "").strip(),
                    "amount_lkr": round(amount, 2),
                    "amount_band": _amount_band(amount),
                    "debit": "" if row["debit"] is None else str(row["debit"]),
                    "credit": "" if row["credit"] is None else str(row["credit"]),
                    "direction": str(row["direction"]),
                    "parse_confidence": row["parse_confidence"],
                    "is_flagged": str(bool(row["is_flagged"])).lower(),
                },
            )
    return rows


def _fetch_transactions(
    *,
    limit: int,
    min_date: str | None,
    max_date: str | None,
    min_desc_len: int,
    order: str,
) -> list[dict[str, Any]]:
    where = [
        "t.raw_desc IS NOT NULL",
        "LENGTH(TRIM(t.raw_desc)) >= :min_desc_len",
        "t.amount_lkr > 0",
    ]
    params: dict[str, Any] = {"limit": limit, "min_desc_len": min_desc_len}
    if min_date:
        where.append("t.tx_date >= :min_date")
        params["min_date"] = min_date
    if max_date:
        where.append("t.tx_date <= :max_date")
        params["max_date"] = max_date

    order_sql = "t.tx_date DESC, t.id ASC"
    if order == "random":
        order_sql = "RANDOM()"

    sql = f"""
        SELECT
            t.id AS row_id,
            t.tx_date,
            t.raw_desc AS description,
            t.amount_lkr,
            t.direction::text AS direction,
            t.bank_code,
            t.source_type,
            t.raw_payload
        FROM transactions t
        WHERE {" AND ".join(where)}
        ORDER BY {order_sql}
        LIMIT :limit
    """
    rows: list[dict[str, Any]] = []
    with engine.connect() as conn:
        for row in conn.execute(text(sql), params).mappings().all():
            amount = float(row["amount_lkr"])
            payload = row["raw_payload"] if isinstance(row["raw_payload"], dict) else {}
            rows.append(
                {
                    "row_id": str(row["row_id"]),
                    "source_table": "transactions",
                    "document_id": "",
                    "filename": str(payload.get("source_filename") or ""),
                    "content_type": str(payload.get("content_type") or ""),
                    "document_type": _doc_type_from_source(row["source_type"], payload),
                    "bank_detected": (row["bank_code"] or "").strip(),
                    "file_type": str(payload.get("file_type") or ""),
                    "tx_date": row["tx_date"].isoformat(),
                    "description": str(row["description"]).strip(),
                    "reference_no": "",
                    "amount_lkr": round(amount, 2),
                    "amount_band": _amount_band(amount),
                    "debit": "",
                    "credit": "",
                    "direction": str(row["direction"]),
                    "parse_confidence": payload.get("parse_confidence"),
                    "is_flagged": "false",
                },
            )
    return rows


def build_candidates(
    *,
    output_dir: Path,
    source: str,
    limit: int,
    min_date: str | None,
    max_date: str | None,
    min_desc_len: int,
    min_confidence: float,
    exclude_flagged: bool,
    order: str,
    seed: int,
) -> None:
    random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    if source == "extracted":
        candidates = _fetch_extracted(
            limit=limit,
            min_date=min_date,
            max_date=max_date,
            min_desc_len=min_desc_len,
            min_confidence=min_confidence,
            exclude_flagged=exclude_flagged,
            order=order,
        )
    elif source == "transactions":
        candidates = _fetch_transactions(
            limit=limit,
            min_date=min_date,
            max_date=max_date,
            min_desc_len=min_desc_len,
            order=order,
        )
    else:
        raise ValueError(f"Unknown --source {source!r}; use extracted or transactions")

    base_name = f"label_candidates_{source}"
    candidates_csv = output_dir / f"{base_name}.csv"
    fieldnames = list(candidates[0].keys()) if candidates else [
        "row_id",
        "source_table",
        "document_id",
        "filename",
        "content_type",
        "document_type",
        "bank_detected",
        "file_type",
        "tx_date",
        "description",
        "reference_no",
        "amount_lkr",
        "amount_band",
        "debit",
        "credit",
        "direction",
        "parse_confidence",
        "is_flagged",
    ]

    with candidates_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    requests_jsonl = output_dir / f"llm_bootstrap_requests_{source}.jsonl"
    with requests_jsonl.open("w", encoding="utf-8") as f:
        for row in candidates:
            f.write(json.dumps(_llm_prompt_payload(row), ensure_ascii=True) + "\n")

    annotation_csv = output_dir / f"annotation_template_{source}.csv"
    annotation_extra = [
        "suggested_label",
        "suggested_confidence",
        "reviewer_label",
        "reviewer_notes",
        "label_source",
    ]
    ann_fields = fieldnames + annotation_extra
    with annotation_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ann_fields)
        writer.writeheader()
        for row in candidates:
            writer.writerow(
                {
                    **row,
                    "suggested_label": "",
                    "suggested_confidence": "",
                    "reviewer_label": "",
                    "reviewer_notes": "",
                    "label_source": "manual",
                },
            )

    print(f"source={source} wrote {len(candidates)} rows")
    print(f"  {candidates_csv}")
    print(f"  {requests_jsonl}")
    print(f"  {annotation_csv}")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build transaction labeling candidate files from DB.")
    p.add_argument(
        "--source",
        choices=("extracted", "transactions"),
        default="extracted",
        help="extracted_transactions (upload pipeline) or legacy transactions table.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/transaction-semantic"),
    )
    p.add_argument("--limit", type=int, default=15_000, help="Max rows to export.")
    p.add_argument("--min-date", type=str, default=None, help="YYYY-MM-DD")
    p.add_argument("--max-date", type=str, default=None, help="YYYY-MM-DD")
    p.add_argument("--min-desc-len", type=int, default=10, help="Skip very short / garbage descriptions.")
    p.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="For extracted rows only: require parse_confidence >= this (NULL passes if 0).",
    )
    p.add_argument(
        "--include-flagged",
        action="store_true",
        help="Include rows with is_flagged=true (extracted only).",
    )
    p.add_argument(
        "--order",
        choices=("date_desc", "random", "bank_stratified"),
        default="random",
        help="Row sampling order. random helps spread banks/dates in the CSV cap.",
    )
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    build_candidates(
        output_dir=args.output_dir,
        source=args.source,
        limit=args.limit,
        min_date=args.min_date,
        max_date=args.max_date,
        min_desc_len=args.min_desc_len,
        min_confidence=args.min_confidence,
        exclude_flagged=not args.include_flagged,
        order=args.order,
        seed=args.seed,
    )
