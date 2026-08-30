"""Layer 1: parse SL bank narrations into features + deterministic class when safe."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .taxpayer_profile import TaxpayerProfile

_CEFTS = re.compile(r"\bcefts?\b|_invceft_", re.IGNORECASE)
_INVCEFT = re.compile(r"_invceft_|invceft", re.IGNORECASE)
_POS = re.compile(r"\bpos\b", re.IGNORECASE)
_INT_PD = re.compile(r"\bint(?:erest)?[.\s-]*pd\b|\bfd interest\b|\binterest credit\b", re.IGNORECASE)
_WTAX = re.compile(r"\bwtax[.\s-]*pd\b|\bwht\b|\bait\b|\bwithholding tax\b", re.IGNORECASE)
_CHARGES = re.compile(
    r"\b(cefts?\s*charges?|bank charges?|sms charges?|service (?:fee|charge)|ft\s*fee)",
    re.IGNORECASE,
)
_REVERSAL = re.compile(r"\b(revers(?:ed|al)?|rev\.?:)\b", re.IGNORECASE)
_SALARY = re.compile(r"\b(salary|payroll|wages|overtime|bonus)\b", re.IGNORECASE)
_LOAN = re.compile(r"\b(loan disbursement|loan received|facility drawdown)\b", re.IGNORECASE)
_INSURANCE = re.compile(r"\b(insurance (?:claim|payout)|nic\b)\b", re.IGNORECASE)
_TOPUP = re.compile(r"\btopup", re.IGNORECASE)
_FT_FROM = re.compile(r"\bft\s*from_|\bfrom_dfp-", re.IGNORECASE)
_FT_TO = re.compile(r"\bft\s*to_|\bto_[a-z]{2,5}-", re.IGNORECASE)
_ATM = re.compile(r"\batm\b", re.IGNORECASE)


@dataclass(frozen=True)
class BankNarrationFeatures:
    channel: str
    intent_tag: str
    counterparty_type: str
    flow_direction: str
    own_account_match: bool
    deterministic_class: str | None
    evidence_needed: str | None
    certainty_hint: str | None
    parse_note: str

    def as_facts(self) -> dict[str, str | bool]:
        facts: dict[str, str | bool] = {
            "channel": self.channel,
            "intent_tag": self.intent_tag,
            "counterparty_type": self.counterparty_type,
            "own_account_match": self.own_account_match,
        }
        if self.evidence_needed:
            facts["evidence_needed"] = self.evidence_needed
        return facts


def extract_bank_features(
    raw_desc: str,
    *,
    direction: str,
    profile: TaxpayerProfile | None = None,
) -> BankNarrationFeatures:
    text = raw_desc or ""
    direction_u = (direction or "").upper()
    own = bool(profile and profile.description_hits_own_account(text))
    own_topup = bool(profile and profile.description_is_own_bank_topup(text))

    channel = "unknown"
    if _INVCEFT.search(text) or _CEFTS.search(text):
        channel = "cefts"
    elif _POS.search(text):
        channel = "pos"
    elif _INT_PD.search(text):
        channel = "interest_posting"
    elif _WTAX.search(text):
        channel = "withholding"
    elif _CHARGES.search(text):
        channel = "bank_fee"
    elif _TOPUP.search(text):
        channel = "wallet_topup"
    elif _FT_FROM.search(text):
        channel = "wallet_p2p"
    elif _FT_TO.search(text):
        channel = "outbound_ft"
    elif _ATM.search(text):
        channel = "atm"

    if _REVERSAL.search(text):
        return BankNarrationFeatures(
            channel=channel or "reversal",
            intent_tag="REVERSAL",
            counterparty_type="BANK",
            flow_direction=direction_u,
            own_account_match=own,
            deterministic_class="inter_account_transfer",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="Reversal or failed posting; net tax impact treated as nil (capital restoration).",
        )

    if _WTAX.search(text):
        return BankNarrationFeatures(
            channel="withholding",
            intent_tag="WHT",
            counterparty_type="BANK",
            flow_direction=direction_u,
            own_account_match=own,
            deterministic_class="withholding_tax",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="WTax.Pd / AIT debit is not assessable income; Comp 2 applies s.89 credits.",
        )

    if _INT_PD.search(text) and direction_u == "CR":
        return BankNarrationFeatures(
            channel="interest_posting",
            intent_tag="BANK_INTEREST",
            counterparty_type="FINANCIAL_INSTITUTION",
            flow_direction=direction_u,
            own_account_match=own,
            deterministic_class="interest_income",
            evidence_needed=None,
            certainty_hint="guaranteed_taxable",
            parse_note="Bank/FD interest credit (IRA s.7(2)(a)). Comp 2/5 apply AIT — Comp 1 does not compute tax.",
        )

    if _CHARGES.search(text):
        return BankNarrationFeatures(
            channel="bank_fee",
            intent_tag="BANK_FEE",
            counterparty_type="BANK",
            flow_direction=direction_u,
            own_account_match=own,
            deterministic_class="bank_charge",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="Bank/CEFTS/FT fee is not income.",
        )

    if _POS.search(text) and direction_u == "DR":
        return BankNarrationFeatures(
            channel="pos",
            intent_tag="MERCHANT_SPEND",
            counterparty_type="MERCHANT",
            flow_direction=direction_u,
            own_account_match=own,
            deterministic_class="personal_spend",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="POS debit is personal spend, not assessable income.",
        )

    if direction_u == "CR" and (_TOPUP.search(text) and (own or own_topup)):
        return BankNarrationFeatures(
            channel="wallet_topup",
            intent_tag="OWN_TOPUP",
            counterparty_type="SELF",
            flow_direction=direction_u,
            own_account_match=True,
            deterministic_class="inter_account_transfer",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="Wallet top-up from a linked own bank (no accession to wealth).",
        )

    if own:
        return BankNarrationFeatures(
            channel=channel,
            intent_tag="OWN_ACCOUNT",
            counterparty_type="SELF",
            flow_direction=direction_u,
            own_account_match=True,
            deterministic_class="inter_account_transfer",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="Narration matches a linked own account number; internal capital movement.",
        )

    if _SALARY.search(text) and direction_u == "CR":
        return BankNarrationFeatures(
            channel=channel,
            intent_tag="SALARY",
            counterparty_type="EMPLOYER",
            flow_direction=direction_u,
            own_account_match=False,
            deterministic_class="employment_income",
            evidence_needed=None,
            certainty_hint="guaranteed_taxable",
            parse_note="Salary/payroll keyword; employment income (IRA s.5).",
        )

    if _LOAN.search(text) and direction_u == "CR":
        return BankNarrationFeatures(
            channel=channel,
            intent_tag="LOAN_PRINCIPAL",
            counterparty_type="LENDER",
            flow_direction=direction_u,
            own_account_match=False,
            deterministic_class="loan_received",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="Loan principal inflow is capital, not income (IRA s.31 context).",
        )

    if _INSURANCE.search(text) and direction_u == "CR":
        return BankNarrationFeatures(
            channel=channel,
            intent_tag="INSURANCE",
            counterparty_type="INSURER",
            flow_direction=direction_u,
            own_account_match=False,
            deterministic_class=None,
            evidence_needed="insurance_or_service_evidence",
            certainty_hint="indeterminate",
            parse_note="Insurance-like wording without claim confirmation; keep indeterminate until evidence.",
        )

    if direction_u == "DR" and (_CEFTS.search(text) or _FT_TO.search(text) or _ATM.search(text)):
        return BankNarrationFeatures(
            channel=channel if channel != "unknown" else "outbound_ft",
            intent_tag="OUTBOUND_TRANSFER",
            counterparty_type="THIRD_PARTY",
            flow_direction=direction_u,
            own_account_match=False,
            deterministic_class="personal_spend",
            evidence_needed=None,
            certainty_hint="guaranteed_non_taxable",
            parse_note="Outbound debit is not income of this taxpayer (s.11 deductibility is Comp 2 if business is declared).",
        )

    if direction_u == "CR" and (
        _INVCEFT.search(text) or _CEFTS.search(text) or _FT_FROM.search(text) or _ATM.search(text)
    ):
        return BankNarrationFeatures(
            channel="cefts" if (_INVCEFT.search(text) or _CEFTS.search(text)) else channel,
            intent_tag="PEER_OR_UNLABELLED_CREDIT",
            counterparty_type="THIRD_PARTY",
            flow_direction=direction_u,
            own_account_match=False,
            deterministic_class=None,
            evidence_needed="invoice_loan_gift_or_shared_expense",
            certainty_hint="indeterminate",
            parse_note=(
                "Unlabelled third-party credit is not a taxable event by itself (IRA s.120/s.141). "
                "Do not treat PAYMENT/INVCEFT wording as s.6 income or as tax-free."
            ),
        )

    return BankNarrationFeatures(
        channel=channel,
        intent_tag="UNPARSED",
        counterparty_type="UNKNOWN",
        flow_direction=direction_u,
        own_account_match=False,
        deterministic_class=None,
        evidence_needed="invoice_loan_gift_or_shared_expense" if direction_u == "CR" else None,
        certainty_hint="indeterminate" if direction_u == "CR" else None,
        parse_note="No deterministic bank-code match; credit stays indeterminate.",
    )
