"""Cohen's kappa for OE Engine relief recommendation validation.

Pair system claim decisions with independent expert labels for the same
(taxpayer, YA, relief) cases. Answers the panel question: how do you validate
Optimization and Explainable Engine recommendations beyond calculate accuracy?
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from sklearn.metrics import cohen_kappa_score, confusion_matrix

LANDIS_KOCH_BANDS: tuple[tuple[float, float, str], ...] = (
    (float("-inf"), 0.0, "poor (worse than chance)"),
    (0.0, 0.20, "slight"),
    (0.21, 0.40, "fair"),
    (0.41, 0.60, "moderate"),
    (0.61, 0.80, "substantial"),
    (0.81, 1.01, "almost perfect"),
)


def interpret_kappa(kappa: float) -> str:
    for low, high, label in LANDIS_KOCH_BANDS:
        if low <= kappa < high:
            return label
    return "almost perfect"


@dataclass(frozen=True)
class KappaResult:
    n_pairs: int
    observed_agreement: float
    cohen_kappa: float
    weighted_kappa: float | None
    interpretation: str
    labels: list[str]
    confusion: list[list[int]]
    system_counts: dict[str, int]
    expert_counts: dict[str, int]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_str_labels(values: Sequence[Any]) -> list[str]:
    out: list[str] = []
    for raw in values:
        text = str(raw).strip()
        if text == "":
            raise ValueError("Empty label is not allowed")
        out.append(text)
    return out


def compute_kappa(
    system_labels: Sequence[Any],
    expert_labels: Sequence[Any],
    *,
    weighted: bool = False,
) -> KappaResult:
    if len(system_labels) != len(expert_labels):
        raise ValueError(
            f"Length mismatch: system={len(system_labels)} expert={len(expert_labels)}"
        )
    if len(system_labels) == 0:
        raise ValueError("Need at least one labeled pair")

    y_sys = _as_str_labels(system_labels)
    y_exp = _as_str_labels(expert_labels)
    labels = sorted(set(y_sys) | set(y_exp))

    agree = sum(1 for a, b in zip(y_sys, y_exp) if a == b)
    observed = agree / len(y_sys)

    kappa = float(cohen_kappa_score(y_exp, y_sys, labels=labels))
    weighted_k: float | None = None
    notes: list[str] = []
    if weighted:
        try:
            numeric = all(str(x).lstrip("-").replace(".", "", 1).isdigit() for x in labels)
            if numeric:
                weighted_k = float(
                    cohen_kappa_score(y_exp, y_sys, labels=labels, weights="linear")
                )
            else:
                notes.append("weighted kappa skipped — labels are not numeric/ordinal")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"weighted kappa skipped: {exc}")

    cm = confusion_matrix(y_exp, y_sys, labels=labels)
    return KappaResult(
        n_pairs=len(y_sys),
        observed_agreement=round(observed, 6),
        cohen_kappa=round(kappa, 6),
        weighted_kappa=None if weighted_k is None else round(weighted_k, 6),
        interpretation=interpret_kappa(kappa),
        labels=labels,
        confusion=cm.astype(int).tolist(),
        system_counts=dict(Counter(y_sys)),
        expert_counts=dict(Counter(y_exp)),
        notes=notes,
    )


REQUIRED_COLUMNS = ("system_label", "expert_label")


def load_label_csv(path: Path) -> tuple[list[str], list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"No header row in {path}")
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"{path} missing columns {missing}; found {list(reader.fieldnames)}"
            )
        rows: list[dict[str, str]] = []
        system: list[str] = []
        expert: list[str] = []
        for i, row in enumerate(reader, start=2):
            sys_lab = (row.get("system_label") or "").strip()
            exp_lab = (row.get("expert_label") or "").strip()
            if not sys_lab and not exp_lab:
                continue
            if not sys_lab or not exp_lab:
                raise ValueError(f"Row {i}: both system_label and expert_label required")
            system.append(sys_lab)
            expert.append(exp_lab)
            rows.append({k: (v or "").strip() for k, v in row.items()})
    if not system:
        raise ValueError(f"No labeled pairs in {path}")
    return system, expert, rows


def kappa_from_csv(path: Path, *, weighted: bool = False) -> KappaResult:
    system, expert, _rows = load_label_csv(path)
    return compute_kappa(system, expert, weighted=weighted)


def write_result_json(result: KappaResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
