"""Graded relevance labels for LambdaMART training (behavioral proxy)."""

from __future__ import annotations

from strategy_gen.evaluator import StrategyEvaluationResult


def relevance_from_evaluation(
    eval_result: StrategyEvaluationResult,
    *,
    priority_hint: int,
    max_priority: int = 10,
) -> int:
    """Integer label in [0, 4]. Higher = better for ranking.

    Ineligible strategies get 0. Eligible strategies get 1–3 from inverted
    priority_hint (lower hint = higher business priority in catalog).
    Feasibility bumps the grade slightly.
    """
    if not eval_result.is_eligible:
        return 0
    # invert priority: hint 0 -> strongest, hint 999 -> weakest
    span = max(1, max_priority)
    inv = max(0.0, 1.0 - min(float(priority_hint), float(span)) / float(span))
    base = 1 + int(inv * 2.99)  # 1..3
    feas = float(eval_result.feasibility_score)
    if feas >= 0.85:
        base = min(4, base + 1)
    return int(min(4, max(1, base)))
