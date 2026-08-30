"""Auditor activity rollup: group extracted rows by intent + merchant family."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .bank_feature_extractor import extract_bank_features
from .tax_semantic_paths import repo_root

_INTENT_LABELS: dict[str, tuple[str, str]] = {
    "BANK_INTEREST": ("Bank / FD interest", "Int.Pd and similar interest credits"),
    "WHT": ("Withholding / AIT", "WTax.Pd and withholding debits"),
    "BANK_FEE": ("Bank & transfer fees", "CEFTS charges, FT FEE, SMS/service fees"),
    "OWN_TOPUP": ("Own wallet top-ups", "TOPUP from linked banks"),
    "OWN_ACCOUNT": ("Own-account movements", "Narration matches a linked account"),
    "REVERSAL": ("Reversals", "Failed or reversed postings"),
    "SALARY": ("Salary / payroll", "Salary or payroll keywords"),
    "LOAN_PRINCIPAL": ("Loan principal", "Loan disbursement wording"),
    "PEER_OR_UNLABELLED_CREDIT": (
        "Unlabelled inward transfers",
        "INVCEFT / CEFTS / FT FROM peers — review for source",
    ),
    "OUTBOUND_TRANSFER": ("Outbound transfers", "FT TO / outbound CEFTS / ATM cash-out"),
    "MERCHANT_SPEND": ("Merchant spend", "POS and merchant debits"),
    "INSURANCE": ("Insurance-related", "Insurance wording — needs evidence"),
    "UNPARSED": ("Other / ungrouped", "No strong bank-code or merchant match"),
}


@dataclass(frozen=True)
class ActivityMember:
    row_id: str | None
    tx_date: str | None
    description: str
    direction: str
    amount_lkr: Decimal


@dataclass(frozen=True)
class ActivityGroup:
    group_key: str
    label: str
    hint: str
    direction: str
    intent_tag: str
    merchant_family: str | None
    count: int
    total_lkr: Decimal
    members: tuple[ActivityMember, ...]


def _lexicon_path() -> Path:
    return repo_root() / "models" / "transaction-semantic" / "data" / "activity_merchant_lexicon.yaml"


@lru_cache(maxsize=1)
def _load_merchant_families() -> tuple[tuple[str, str, str, tuple[str, ...]], ...]:
    path = _lexicon_path()
    if not path.is_file():
        return ()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    families = raw.get("families") or {}
    out: list[tuple[str, str, str, tuple[str, ...]]] = []
    if isinstance(families, dict):
        for key, body in families.items():
            if not isinstance(body, dict):
                continue
            patterns = body.get("patterns") or []
            out.append(
                (
                    str(key),
                    str(body.get("label") or key),
                    str(body.get("hint") or ""),
                    tuple(str(p).lower() for p in patterns if str(p).strip()),
                ),
            )
    return tuple(out)


def match_merchant_family(raw_desc: str) -> tuple[str, str, str] | None:
    text = (raw_desc or "").lower()
    for key, label, hint, patterns in _load_merchant_families():
        if any(p in text for p in patterns):
            return key, label, hint
    return None


def _group_meta(
    *,
    intent_tag: str,
    direction: str,
    raw_desc: str,
) -> tuple[str, str, str, str | None]:
    """Return group_key, label, hint, merchant_family."""
    family = match_merchant_family(raw_desc)
    if intent_tag == "MERCHANT_SPEND" and family:
        fam_key, fam_label, fam_hint = family
        return (
            f"merchant|{fam_key}|{direction}",
            fam_label,
            fam_hint,
            fam_key,
        )
    if intent_tag in {"UNPARSED", "OUTBOUND_TRANSFER"} and family and direction == "DR":
        fam_key, fam_label, fam_hint = family
        return (
            f"merchant|{fam_key}|{direction}",
            fam_label,
            fam_hint,
            fam_key,
        )
    if intent_tag == "PEER_OR_UNLABELLED_CREDIT":
        # Split INVCEFT rail vs named DFP peers when useful
        upper = (raw_desc or "").upper()
        if "INVCEFT" in upper or "CEFTS" in upper:
            return (
                f"inward_cefts|{direction}",
                "Inward CEFT / INVCEFT",
                "Inter-bank inward credits without a clear income code",
                None,
            )
        if "FROM_DFP" in upper or "FT FROM" in upper:
            return (
                f"wallet_p2p|{direction}",
                "Wallet / P2P credits",
                "FT FROM DFP and similar peer wallet credits",
                None,
            )
    base_label, base_hint = _INTENT_LABELS.get(
        intent_tag,
        ("Other / ungrouped", "No strong bank-code or merchant match"),
    )
    return f"intent|{intent_tag}|{direction}", base_label, base_hint, None


def classify_activity_row(
    *,
    raw_desc: str,
    direction: str,
) -> tuple[str, str, str, str, str | None]:
    """Return intent_tag, group_key, label, hint, merchant_family."""
    features = extract_bank_features(raw_desc, direction=direction, profile=None)
    intent = features.intent_tag
    group_key, label, hint, family = _group_meta(
        intent_tag=intent,
        direction=direction.upper(),
        raw_desc=raw_desc,
    )
    return intent, group_key, label, hint, family


def build_activity_summary(
    items: list[dict[str, Any]],
) -> list[ActivityGroup]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in items:
        raw_desc = str(item.get("raw_desc") or item.get("description") or "")
        direction = str(item.get("direction") or "").upper()
        amount = item.get("amount_lkr")
        if not isinstance(amount, Decimal):
            amount = Decimal(str(amount or "0"))
        intent, group_key, label, hint, family = classify_activity_row(
            raw_desc=raw_desc,
            direction=direction,
        )
        member = ActivityMember(
            row_id=str(item["row_id"]) if item.get("row_id") is not None else None,
            tx_date=str(item["tx_date"]) if item.get("tx_date") is not None else None,
            description=raw_desc,
            direction=direction,
            amount_lkr=amount,
        )
        bucket = buckets.get(group_key)
        if bucket is None:
            buckets[group_key] = {
                "group_key": group_key,
                "label": label,
                "hint": hint,
                "direction": direction,
                "intent_tag": intent,
                "merchant_family": family,
                "total": amount,
                "members": [member],
            }
        else:
            bucket["total"] += amount
            bucket["members"].append(member)

    groups: list[ActivityGroup] = []
    for bucket in buckets.values():
        members = tuple(
            sorted(
                bucket["members"],
                key=lambda m: (-m.amount_lkr, m.tx_date or "", m.description),
            ),
        )
        groups.append(
            ActivityGroup(
                group_key=bucket["group_key"],
                label=bucket["label"],
                hint=bucket["hint"],
                direction=bucket["direction"],
                intent_tag=bucket["intent_tag"],
                merchant_family=bucket["merchant_family"],
                count=len(members),
                total_lkr=bucket["total"],
                members=members,
            ),
        )
    groups.sort(key=lambda g: (-abs(g.total_lkr), g.label))
    return groups
