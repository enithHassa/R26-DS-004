"""Validate reviewed labels and produce train/val/test CSV splits."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import random
import sys

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_label_set(taxonomy_path: Path) -> set[str]:
    raw = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8"))
    labels = raw.get("labels", [])
    return {item["key"] for item in labels if isinstance(item, dict) and "key" in item}


def _resolve_final_label(row: dict[str, str]) -> str:
    reviewer = (row.get("reviewer_label") or "").strip()
    if reviewer:
        return reviewer
    return (row.get("suggested_label") or "").strip()


def _stratified_split(
    rows: list[dict[str, str]],
    *,
    test_size: float,
    val_size: float,
    random_state: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    by_label: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_label.setdefault(row["final_label"], []).append(row)

    rng = random.Random(random_state)
    train: list[dict[str, str]] = []
    val: list[dict[str, str]] = []
    test: list[dict[str, str]] = []

    for label_rows in by_label.values():
        rng.shuffle(label_rows)
        n = len(label_rows)
        n_test = max(1, round(n * test_size)) if n >= 3 else (1 if n > 1 else 0)
        n_val = max(1, round(n * val_size)) if n >= 3 else (1 if n > 2 else 0)
        if n_test + n_val >= n:
            n_val = max(0, n - n_test - 1)
        test.extend(label_rows[:n_test])
        val.extend(label_rows[n_test : n_test + n_val])
        train.extend(label_rows[n_test + n_val :])

    rng.shuffle(train)
    rng.shuffle(val)
    rng.shuffle(test)
    return train, val, test


def build_splits(
    *,
    labeled_csv_path: Path,
    taxonomy_path: Path,
    output_dir: Path,
    test_size: float,
    val_size: float,
    random_state: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with labeled_csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if not rows:
        raise ValueError("labeled dataset is empty")

    filtered: list[dict[str, str]] = []
    for row in rows:
        row = dict(row)
        row["final_label"] = _resolve_final_label(row)
        if row["final_label"]:
            filtered.append(row)
    if not filtered:
        raise ValueError("no rows have final labels (reviewer_label/suggested_label)")

    valid_labels = _load_label_set(taxonomy_path)
    invalid = sorted({row["final_label"] for row in filtered} - valid_labels)
    if invalid:
        raise ValueError(f"labels not found in taxonomy: {invalid}")

    if "description" not in filtered[0] or "amount_lkr" not in filtered[0]:
        raise ValueError("expected columns missing (description, amount_lkr)")

    train, val, test = _stratified_split(
        filtered,
        test_size=test_size,
        val_size=val_size,
        random_state=random_state,
    )

    train_path = output_dir / "train.csv"
    val_path = output_dir / "val.csv"
    test_path = output_dir / "test.csv"
    fieldnames = list(filtered[0].keys())
    for path, part in ((train_path, train), (val_path, val), (test_path, test)):
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(part)

    class_counts: dict[str, int] = {}
    for row in filtered:
        class_counts[row["final_label"]] = class_counts.get(row["final_label"], 0) + 1

    summary = {
        "total_rows": int(len(filtered)),
        "train_rows": int(len(train)),
        "val_rows": int(len(val)),
        "test_rows": int(len(test)),
        "class_counts": class_counts,
        "test_size": test_size,
        "val_size": val_size,
        "random_state": random_state,
    }
    summary_path = output_dir / "split_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"wrote {train_path}, {val_path}, {test_path}")
    print(f"wrote summary to {summary_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create train/val/test splits from labeled CSV.")
    parser.add_argument("--labeled-csv", type=Path, required=True)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=Path("models/transaction-semantic/taxonomy.yaml"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/transaction-semantic"),
    )
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--random-state", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    build_splits(
        labeled_csv_path=args.labeled_csv,
        taxonomy_path=args.taxonomy,
        output_dir=args.output_dir,
        test_size=args.test_size,
        val_size=args.val_size,
        random_state=args.random_state,
    )
