"""Linked-account profile used by Layer 1 own-capital matching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .tax_semantic_paths import repo_root

DEFAULT_TAXPAYER_ID = "taxpayer_00001"


def _digits_only(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


_RAIL_ABBREVS = frozenset({"DFP", "CEFT", "CEFTS", "NTB", "HNB", "COMB", "BOC", "SAMP", "LOLC"})


@dataclass(frozen=True)
class TaxpayerProfile:
    taxpayer_id: str
    display_name: str
    linked_account_numbers: tuple[str, ...]
    linked_wallet_ids: tuple[str, ...]
    linked_topup_bank_phrases: tuple[str, ...]
    employers: tuple[str, ...]

    def account_digits(self) -> tuple[str, ...]:
        return tuple(_digits_only(n) for n in self.linked_account_numbers if _digits_only(n))

    def description_hits_own_account(self, raw_desc: str) -> bool:
        text = raw_desc or ""
        compact = _digits_only(text)
        for acct in self.account_digits():
            if len(acct) >= 8 and acct in compact:
                return True
        upper = text.upper()
        for wallet in self.linked_wallet_ids:
            token = wallet.strip().upper()
            if len(token) < 5 or token in _RAIL_ABBREVS:
                continue
            if re.search(rf"\b{re.escape(token)}\b", upper):
                return True
        return False

    def description_is_own_bank_topup(self, raw_desc: str) -> bool:
        upper = (raw_desc or "").upper()
        if "TOPUP" not in upper:
            return False
        for phrase in self.linked_topup_bank_phrases:
            token = phrase.strip().upper()
            if len(token) >= 3 and token in upper:
                return True
        return False


def _profiles_dir() -> Path:
    return repo_root() / "models" / "transaction-semantic" / "data"


def _from_mapping(raw: dict[str, Any], fallback_id: str) -> TaxpayerProfile:
    accounts = raw.get("linked_account_numbers") or []
    wallets = raw.get("linked_wallet_ids") or []
    topup_banks = raw.get("linked_topup_bank_phrases") or []
    employers = raw.get("employers") or []
    return TaxpayerProfile(
        taxpayer_id=str(raw.get("taxpayer_id") or fallback_id),
        display_name=str(raw.get("display_name") or fallback_id),
        linked_account_numbers=tuple(str(x) for x in accounts),
        linked_wallet_ids=tuple(str(x) for x in wallets),
        linked_topup_bank_phrases=tuple(str(x) for x in topup_banks),
        employers=tuple(str(x) for x in employers),
    )


@lru_cache(maxsize=8)
def load_taxpayer_profile(taxpayer_id: str = DEFAULT_TAXPAYER_ID) -> TaxpayerProfile:
    path = _profiles_dir() / f"{taxpayer_id}.yaml"
    if not path.is_file():
        return TaxpayerProfile(
            taxpayer_id=taxpayer_id,
            display_name=taxpayer_id,
            linked_account_numbers=(),
            linked_wallet_ids=(),
            linked_topup_bank_phrases=(),
            employers=(),
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raw = {}
    return _from_mapping(raw, taxpayer_id)
