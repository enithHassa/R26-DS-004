"""User × strategy pair features for LambdaMART and adoption models (Phase 4 / WP6)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from strategy_gen.catalog import StrategyDefinition

# Extra columns appended to the user-level feature row for each pair.
PAIR_NUM_FEATURES = ["strategy_priority_hint"]
PAIR_CAT_FEATURES = ["strategy_id", "strategy_category"]


def pair_column_names(user_num: list[str], user_cat: list[str]) -> tuple[list[str], list[str]]:
    """Return (all_numeric_names, all_categorical_names) for the flat pair row."""
    return (
        [*user_num, *PAIR_NUM_FEATURES],
        [*user_cat, *PAIR_CAT_FEATURES],
    )


def build_pair_row(
    user_row: dict[str, Any],
    strategy: StrategyDefinition,
    *,
    user_num_keys: list[str],
    user_cat_keys: list[str],
) -> dict[str, Any]:
    """Merge one user feature dict with strategy-side fields.

    ``user_row`` must contain all ``user_num_keys`` and ``user_cat_keys`` (e.g. from
    the same builder used for the legacy matcher).
    """
    out: dict[str, Any] = {}
    for k in user_num_keys:
        v = user_row.get(k, 0.0)
        out[k] = float(v) if v is not None else 0.0
    for k in user_cat_keys:
        v = user_row.get(k, "unknown")
        out[k] = "unknown" if v is None else str(v)
    out["strategy_priority_hint"] = float(strategy.priority_hint)
    out["strategy_id"] = str(strategy.strategy_id)
    out["strategy_category"] = str(strategy.category)
    return out


def build_pair_dataframe(
    user_row: dict[str, Any],
    strategies: tuple[StrategyDefinition, ...],
    *,
    user_num_keys: list[str],
    user_cat_keys: list[str],
) -> pd.DataFrame:
    """One row per strategy, catalog order preserved."""
    rows = [
        build_pair_row(user_row, s, user_num_keys=user_num_keys, user_cat_keys=user_cat_keys)
        for s in strategies
    ]
    num_cols, cat_cols = pair_column_names(user_num_keys, user_cat_keys)
    return pd.DataFrame(rows, columns=[*num_cols, *cat_cols])
