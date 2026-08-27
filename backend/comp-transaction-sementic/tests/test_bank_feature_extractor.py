"""Layer-1 parsers for Sri Lankan bank narrations (NTB-style)."""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
C1_ROOT = Path(__file__).resolve().parents[1]
for path in (str(REPO_ROOT), str(C1_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.services.bank_feature_extractor import extract_bank_features
from app.services.taxpayer_profile import load_taxpayer_profile
from app.services.transaction_analyzer import analyze_transaction_fields
from backend.shared.schemas.enums import TxnDirection


def test_ntb_interest_credit_is_guaranteed_investment_income() -> None:
    result = analyze_transaction_fields(
        raw_desc="200280055988:Int.Pd:01-12-2025 to 31-12-2025",
        amount_lkr=Decimal("1712.77"),
        direction=TxnDirection.CR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.semantic_category == "interest_income"
    assert result.class_source == "deterministic"
    assert result.certainty_tier == "guaranteed_taxable"
    assert result.taxability_status == "taxable"


def test_ntb_cefts_charge_is_non_income() -> None:
    result = analyze_transaction_fields(
        raw_desc="CEFTS Charges S430894",
        amount_lkr=Decimal("25.00"),
        direction=TxnDirection.DR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.semantic_category == "bank_charge"
    assert result.certainty_tier == "guaranteed_non_taxable"
    assert result.taxable_amount_lkr == Decimal("0.00")


def test_ntb_pos_debit_is_personal_spend() -> None:
    result = analyze_transaction_fields(
        raw_desc="POS Transaction - CARGILLS FOODCITY GANE GANEMUL S762864",
        amount_lkr=Decimal("3486.04"),
        direction=TxnDirection.DR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.semantic_category == "personal_spend"
    assert result.certainty_tier == "guaranteed_non_taxable"


def test_unlabelled_inward_cefts_stays_indeterminate() -> None:
    result = analyze_transaction_fields(
        raw_desc="CEFTS/6135/AL SHAREQ AL MU/5620310207599-",
        amount_lkr=Decimal("214445.00"),
        direction=TxnDirection.CR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.certainty_tier == "indeterminate"
    assert result.evidence_needed == "invoice_loan_gift_or_shared_expense"
    assert result.taxable_amount_lkr == Decimal("214445.00")


def test_outbound_cefts_debit_is_not_income() -> None:
    result = analyze_transaction_fields(
        raw_desc="CEFTS/6010/FT/BOC/n p saduna sunilshan rajapaksha/",
        amount_lkr=Decimal("5000.00"),
        direction=TxnDirection.DR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.semantic_category == "personal_spend"
    assert result.certainty_tier == "guaranteed_non_taxable"


def test_own_account_digits_mark_internal_transfer() -> None:
    from app.services.taxpayer_profile import load_taxpayer_profile

    load_taxpayer_profile.cache_clear()
    profile = load_taxpayer_profile("taxpayer_00001")
    features = extract_bank_features(
        "TRF TO 200280055988 OWN SAVINGS",
        direction="CR",
        profile=profile,
    )
    assert features.own_account_match is True
    assert features.deterministic_class == "inter_account_transfer"


def test_dialog_fd_interest_is_guaranteed_taxable() -> None:
    result = analyze_transaction_fields(
        raw_desc="001030099637:Int.Pd:26-03-2025 to 25-04-2025",
        amount_lkr=Decimal("734.52"),
        direction=TxnDirection.CR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.semantic_category == "interest_income"
    assert result.certainty_tier == "guaranteed_taxable"


def test_dialog_hnb_topup_is_internal() -> None:
    result = analyze_transaction_fields(
        raw_desc="TOPUP_Hatton National Bank PLC_Savings top-up",
        amount_lkr=Decimal("50000.00"),
        direction=TxnDirection.CR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.semantic_category == "inter_account_transfer"
    assert result.certainty_tier == "guaranteed_non_taxable"


def test_dialog_invceft_stays_indeterminate_not_reimbursement() -> None:
    result = analyze_transaction_fields(
        raw_desc="NTB_XXXXXX0001 _INVCEFT_NA (S87245)",
        amount_lkr=Decimal("18000.00"),
        direction=TxnDirection.CR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.certainty_tier == "indeterminate"
    assert result.semantic_category == "unknown"
    assert result.taxable_amount_lkr == Decimal("18000.00")
    assert result.taxability_status.value == "taxable"
    assert "reimbursement" not in (result.narrative_interpretation or "").lower()


def test_dialog_from_dfp_peer_is_not_own_wallet() -> None:
    result = analyze_transaction_fields(
        raw_desc="FT FROM_DFP-001020365874-PAYMENT",
        amount_lkr=Decimal("90000.00"),
        direction=TxnDirection.CR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.certainty_tier == "indeterminate"
    assert result.semantic_category != "inter_account_transfer"


def test_dialog_ft_fee_is_bank_charge() -> None:
    result = analyze_transaction_fields(
        raw_desc="FT FEE_BOC/481107",
        amount_lkr=Decimal("15.00"),
        direction=TxnDirection.DR,
        facts={"taxpayer_id": "taxpayer_00001"},
    )
    assert result.semantic_category == "bank_charge"
    assert result.certainty_tier == "guaranteed_non_taxable"


def test_inflow_summary_relief_flag_does_not_tax_indet() -> None:
    from app.services.inflow_summary import summarize_inflows
    from app.services.transaction_analyzer import TransactionAnalyzeInput, analyze_transactions_batch

    items = [
        TransactionAnalyzeInput(
            raw_desc="001020023544:Int.Pd:26-03-2025 to 25-04-2025",
            amount_lkr=Decimal("26.36"),
            tx_date=date(2025, 4, 25),
            direction=TxnDirection.CR,
            facts={"taxpayer_id": "taxpayer_00001"},
        ),
        TransactionAnalyzeInput(
            raw_desc="NTB_XXXXXX0001 _INVCEFT_NA",
            amount_lkr=Decimal("1747000.00"),
            tx_date=date(2025, 4, 3),
            direction=TxnDirection.CR,
            facts={"taxpayer_id": "taxpayer_00001"},
        ),
    ]
    analyses = analyze_transactions_batch(items)
    rollup = summarize_inflows(items, analyses)
    assert rollup.guaranteed_taxable_inflows_lkr == Decimal("26.36")
    assert rollup.indeterminate_inflows_lkr == Decimal("1747000.00")
    assert analyses[1].taxable_amount_lkr == Decimal("1747000.00")
    assert rollup.exceeds_monthly_relief_equivalent_if_indet_is_income is True

