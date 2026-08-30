"""Unit tests for deterministic IRA rule evaluation."""

from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
import sys


def _load_executor_module():
    repo_root = Path(__file__).resolve().parents[3]
    mod_path = repo_root / "models" / "transaction-semantic" / "rules" / "executor.py"
    spec = importlib.util.spec_from_file_location("tx_semantic_rule_executor_test", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_interest_income_is_taxable() -> None:
    mod = _load_executor_module()
    executor = mod.TaxRuleExecutor()
    decision = executor.evaluate(class_key="interest_income", amount_lkr=Decimal("1500.00"))
    assert decision.tax_rule_code == "INT_AIT_REPORTABLE"
    assert decision.taxability_status == "taxable"
    assert decision.taxable_amount_lkr == Decimal("1500.00")


def test_internal_transfer_is_exempt() -> None:
    mod = _load_executor_module()
    executor = mod.TaxRuleExecutor()
    decision = executor.evaluate(class_key="inter_account_transfer", amount_lkr=Decimal("25000"))
    assert decision.taxability_status == "exempt"
    assert decision.taxable_amount_lkr == Decimal("0.00")


def test_unknown_credit_is_presumptively_taxable() -> None:
    mod = _load_executor_module()
    executor = mod.TaxRuleExecutor()
    decision = executor.evaluate(class_key="unknown", amount_lkr=Decimal("18000.00"))
    assert decision.taxability_status == "taxable"
    assert decision.taxable_amount_lkr == Decimal("18000.00")
    assert decision.decision_mode == "human_required"


def test_gift_requires_facts_for_branch() -> None:
    mod = _load_executor_module()
    executor = mod.TaxRuleExecutor()
    decision = executor.evaluate(class_key="gift_received", amount_lkr=Decimal("10000"))
    assert decision.taxability_status == "unknown"
    assert decision.review_reason == "conditional_facts_missing"

    relative = executor.evaluate(
        class_key="gift_received",
        amount_lkr=Decimal("10000"),
        facts={"counterparty_type": "relative"},
    )
    assert relative.taxability_status == "exempt"
    assert relative.condition_id_matched == "gift_from_relative"
