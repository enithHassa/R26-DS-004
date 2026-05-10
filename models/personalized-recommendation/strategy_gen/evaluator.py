"""Rule evaluator for strategy eligibility + feasibility checks."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from strategy_gen.catalog import StrategyCatalog, StrategyDefinition, load_strategy_catalog


class UnsafeExpressionError(ValueError):
    """Raised when an expression uses unsupported syntax."""


@dataclass(frozen=True)
class EvaluationCheck:
    code: str
    description: str
    passed: bool
    value: str | float | int | bool | None = None


@dataclass(frozen=True)
class StrategyEvaluationResult:
    strategy_id: str
    name: str
    is_eligible: bool
    ineligibility_reasons: tuple[str, ...]
    feasibility_score: float
    checks: tuple[EvaluationCheck, ...]
    required_docs: tuple[str, ...]
    estimation_method_type: str
    estimation_formula_ref: str


_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.In,
    ast.NotIn,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
)


def _safe_eval_expr(expr: str, context: dict[str, Any]) -> bool | float:
    normalized = (
        expr.replace(" true", " True")
        .replace(" false", " False")
        .replace(" null", " None")
        .replace("(true", "(True")
        .replace("(false", "(False")
        .replace("(null", "(None")
        .replace("== true", "== True")
        .replace("== false", "== False")
    )
    tree = ast.parse(normalized, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpressionError(f"Unsupported expression element: {type(node).__name__}")
    eval_context = dict(context)
    eval_context.update({"true": True, "false": False, "null": None})
    return eval(compile(tree, "<strategy_expr>", "eval"), {"__builtins__": {}}, eval_context)


def _eval_rule_tree(node: dict[str, Any], context: dict[str, Any], checks: list[EvaluationCheck]) -> bool:
    if "expr" in node:
        expr = str(node["expr"])
        value = _safe_eval_expr(expr, context)
        passed = bool(value)
        checks.append(EvaluationCheck(code="expr", description=expr, passed=passed, value=passed))
        return passed
    if "all" in node:
        children = [dict(x) for x in node["all"]]
        passed = all(_eval_rule_tree(ch, context, checks) for ch in children)
        checks.append(EvaluationCheck(code="all", description="all(...) block", passed=passed, value=passed))
        return passed
    if "any" in node:
        children = [dict(x) for x in node["any"]]
        passed = any(_eval_rule_tree(ch, context, checks) for ch in children)
        checks.append(EvaluationCheck(code="any", description="any(...) block", passed=passed, value=passed))
        return passed
    return True


def _evaluate_constraints(
    strategy: StrategyDefinition,
    context: dict[str, Any],
    checks: list[EvaluationCheck],
) -> list[str]:
    reasons: list[str] = []
    c = strategy.constraints

    for field in c.profile_fields_required:
        ok = field in context and context[field] not in (None, "")
        checks.append(
            EvaluationCheck(
                code="required_field",
                description=f"field `{field}` required",
                passed=ok,
                value=context.get(field),
            )
        )
        if not ok:
            reasons.append(f"missing required field: {field}")

    if c.max_debt_to_income is not None:
        dti = float(context.get("debt_to_income", 0.0))
        ok = dti <= c.max_debt_to_income
        checks.append(
            EvaluationCheck(
                code="max_debt_to_income",
                description=f"debt_to_income <= {c.max_debt_to_income}",
                passed=ok,
                value=round(dti, 6),
            )
        )
        if not ok:
            reasons.append("debt-to-income above strategy constraint")

    min_liq: float | None = c.min_liquidity_lkr
    if c.min_liquidity_lkr_expr:
        min_liq = float(_safe_eval_expr(c.min_liquidity_lkr_expr, context))
    if min_liq is not None:
        liq = float(context.get("liquid_savings_lkr", 0.0))
        ok = liq >= min_liq
        checks.append(
            EvaluationCheck(
                code="min_liquidity",
                description=f"liquid_savings_lkr >= {min_liq}",
                passed=ok,
                value=round(liq, 2),
            )
        )
        if not ok:
            reasons.append("insufficient liquidity for strategy")

    return reasons


def evaluate_strategy(
    strategy: StrategyDefinition,
    context: dict[str, Any],
) -> StrategyEvaluationResult:
    checks: list[EvaluationCheck] = []

    elig_ok = _eval_rule_tree(strategy.eligibility_rules, context, checks)
    reasons = [] if elig_ok else ["eligibility rules not satisfied"]
    reasons.extend(_evaluate_constraints(strategy, context, checks))

    is_eligible = len(reasons) == 0
    pass_count = sum(1 for c in checks if c.passed)
    total = len(checks) if checks else 1
    feasibility_score = round(pass_count / total, 6)

    return StrategyEvaluationResult(
        strategy_id=strategy.strategy_id,
        name=strategy.name,
        is_eligible=is_eligible,
        ineligibility_reasons=tuple(reasons),
        feasibility_score=feasibility_score,
        checks=tuple(checks),
        required_docs=strategy.constraints.required_docs,
        estimation_method_type=strategy.estimation_method.type,
        estimation_formula_ref=strategy.estimation_method.formula_ref,
    )


def generate_strategy_candidates(
    *,
    context: dict[str, Any],
    catalog_path: str,
    include_ineligible: bool = True,
) -> list[StrategyEvaluationResult]:
    catalog: StrategyCatalog = load_strategy_catalog(catalog_path)
    results: list[StrategyEvaluationResult] = []
    for s in sorted(catalog.strategies, key=lambda x: x.priority_hint):
        r = evaluate_strategy(s, context)
        if include_ineligible or r.is_eligible:
            results.append(r)
    return results

