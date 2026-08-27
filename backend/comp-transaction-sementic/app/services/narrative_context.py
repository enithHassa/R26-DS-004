"""Taxonomy RAG for noisy bank-statement descriptions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .taxonomy_catalog_service import get_income_type_catalog


@dataclass(frozen=True)
class NarrativeContextHit:
    class_key: str
    score: float
    description: str
    default_taxability_status: str


@dataclass(frozen=True)
class NarrativeResolution:
    interpretation: str
    hits: tuple[NarrativeContextHit, ...]
    suggested_class_key: str | None
    suggestion_score: float | None


_CLASS_PHRASE_SEEDS: dict[str, tuple[str, ...]] = {
    "employment_income": (
        "salary",
        "wages",
        "payroll",
        "monthly salary",
        "overtime",
        "employer credit",
    ),
    "bonus_performance": ("bonus", "performance incentive", "incentive payment"),
    "freelance_service": ("freelance", "consulting fee", "service payment", "invoice payment"),
    "business_profit": ("business receipt", "sales proceeds", "customer payment"),
    "interest_income": (
        "fd interest",
        "interest credit",
        "savings interest",
        "fixed deposit",
        "int.pd",
        "int pd",
    ),
    "dividend_income": ("dividend", "share dividend"),
    "rental_income": ("rent received", "rental income", "lease payment"),
    "inter_account_transfer": (
        "own account transfer",
        "savings to current",
        "current to savings",
        "round up account",
        "between my accounts",
    ),
    "qualifying_payment": (
        "bill payment",
        "utility payment",
        "merchant payment",
        "purchase payment",
        "expense payment",
    ),
    "loan_received": ("loan disbursement", "loan received", "facility drawdown"),
    "loan_repayment": ("loan repayment", "loan installment", "housing loan"),
    "gift_received": ("gift", "birthday gift", "family transfer gift"),
    "reimbursement": ("reimbursement", "expense refund", "travel claim"),
    "capital_gain": ("capital gain", "share sale proceeds"),
    "insurance_payout": ("insurance claim", "insurance payout"),
    "bank_charge": ("cefts charges", "bank charges", "service fee", "sms charges"),
    "personal_spend": ("pos transaction", "cargills", "foodcity", "atm withdrawal"),
    "withholding_tax": ("wtax.pd", "wht", "ait", "withholding tax"),
    "unknown": ("miscellaneous credit", "unclear payment", "unidentified transfer"),
}

_INTERNAL_TRANSFER_HINTS = re.compile(
    r"\b(round up|own account|between my accounts|savings to current|current to savings)\b",
    re.IGNORECASE,
)
_CREDIT_INCOME_CLASSES = frozenset(
    {
        "employment_income",
        "employment_allowance_taxable",
        "employment_allowance_exempt",
        "bonus_performance",
        "freelance_service",
        "business_profit",
        "rental_income",
        "interest_income",
        "dividend_income",
        "gift_received",
        "reimbursement",
        "insurance_payout",
        "gratuity",
        "capital_gain",
        "loan_received",
    },
)
_DEBIT_OUTFLOW_CLASSES = frozenset(
    {
        "qualifying_payment",
        "loan_repayment",
        "epf_etf_contribution",
        "personal_spend",
        "bank_charge",
        "withholding_tax",
    },
)


class NarrativeContextIndex:
    def __init__(self, class_keys: list[str], documents: list[str], metadata: list[dict[str, str]]) -> None:
        self._class_keys = class_keys
        self._metadata = metadata
        self._vectorizer = TfidfVectorizer(
            max_features=20_000,
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True,
        )
        self._matrix = self._vectorizer.fit_transform(documents)

    def resolve(self, raw_desc: str, *, direction: str | None = None, top_k: int = 3) -> NarrativeResolution:
        if is_noisy_statement_description(raw_desc):
            return NarrativeResolution(
                interpretation=(
                    "Description is mostly numeric or too noisy for confident automation; "
                    "review the source slip."
                ),
                hits=(),
                suggested_class_key="unknown",
                suggestion_score=None,
            )

        query = _build_query(raw_desc, direction=direction)
        if not query.strip():
            return NarrativeResolution(
                interpretation="No description text to interpret.",
                hits=(),
                suggested_class_key=None,
                suggestion_score=None,
            )

        candidate_k = min(max(top_k, 3) * 3, len(self._class_keys))
        q = self._vectorizer.transform([query])
        sims = cosine_similarity(q, self._matrix)[0]
        top_idx = np.argpartition(-sims, candidate_k - 1)[:candidate_k]
        top_idx = top_idx[np.argsort(-sims[top_idx])]
        ranked_hits = [
            NarrativeContextHit(
                class_key=self._class_keys[int(idx)],
                score=float(sims[int(idx)]),
                description=self._metadata[int(idx)]["description"],
                default_taxability_status=self._metadata[int(idx)]["default_taxability_status"],
            )
            for idx in top_idx
        ]
        allowed_hits = [
            hit
            for hit in ranked_hits
            if _narrative_candidate_allowed(hit.class_key, raw_desc=raw_desc, direction=direction)
        ]
        hits = tuple(allowed_hits[:top_k])
        best = hits[0] if hits else None
        interpretation = _build_interpretation(raw_desc, direction=direction, best=best, hits=hits)
        return NarrativeResolution(
            interpretation=interpretation,
            hits=hits,
            suggested_class_key=best.class_key if best else "unknown",
            suggestion_score=best.score if best else None,
        )


def is_noisy_statement_description(raw_desc: str) -> bool:
    stripped = raw_desc.strip()
    if len(stripped) < 4:
        return True
    letters = sum(ch.isalpha() for ch in stripped)
    digits = sum(ch.isdigit() for ch in stripped)
    if letters == 0 and digits >= 6:
        return True
    return len(stripped) > 12 and digits / len(stripped) > 0.6


def has_confirmed_internal_transfer_evidence(raw_desc: str) -> bool:
    return bool(_INTERNAL_TRANSFER_HINTS.search(raw_desc))


def _narrative_candidate_allowed(
    class_key: str,
    *,
    raw_desc: str,
    direction: str | None,
) -> bool:
    if class_key == "inter_account_transfer" and not has_confirmed_internal_transfer_evidence(raw_desc):
        return False
    if direction == "DR" and class_key in _CREDIT_INCOME_CLASSES:
        return False
    if direction == "CR" and class_key in _DEBIT_OUTFLOW_CLASSES:
        return False
    return True


def _build_query(raw_desc: str, *, direction: str | None) -> str:
    parts = [raw_desc.strip()]
    if direction:
        parts.append(f"direction_{direction.lower()}")
    return " ".join(parts)


def _build_interpretation(
    raw_desc: str,
    *,
    direction: str | None,
    best: NarrativeContextHit | None,
    hits: tuple[NarrativeContextHit, ...],
) -> str:
    if best is None:
        return f"Could not map '{raw_desc}' to a known income pattern."
    direction_note = f"{direction} movement" if direction else "movement"
    alt = ", ".join(hit.class_key for hit in hits[1:3])
    alt_note = f" Alternatives: {alt}." if alt else ""
    return (
        f"Reads like {best.class_key} ({best.description}) for this {direction_note}; "
        f"default treatment is {best.default_taxability_status}.{alt_note}"
    )


def _build_index() -> NarrativeContextIndex:
    class_keys: list[str] = []
    documents: list[str] = []
    metadata: list[dict[str, str]] = []
    for entry in get_income_type_catalog():
        seeds = _CLASS_PHRASE_SEEDS.get(entry.class_key, ())
        document = " ".join(
            [
                entry.class_key.replace("_", " "),
                entry.group.replace("_", " "),
                entry.description,
                *seeds,
            ],
        )
        class_keys.append(entry.class_key)
        documents.append(document)
        metadata.append(
            {
                "description": entry.description,
                "default_taxability_status": entry.default_taxability_status,
            },
        )
    return NarrativeContextIndex(class_keys, documents, metadata)


@lru_cache(maxsize=1)
def get_narrative_context_index() -> NarrativeContextIndex:
    return _build_index()


def resolve_narrative_context(
    raw_desc: str,
    *,
    direction: str | None = None,
    top_k: int = 3,
) -> NarrativeResolution:
    return get_narrative_context_index().resolve(raw_desc, direction=direction, top_k=top_k)
