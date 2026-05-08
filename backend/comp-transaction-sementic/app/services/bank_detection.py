"""Heuristic bank detection from filename + optional text probe (Phase 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BankDetectionResult:
    """Outcome of auto bank detection."""

    bank_code: str | None
    confidence: float
    signals: list[str] = field(default_factory=list)


_BANK_RULES: list[tuple[str, list[str], float]] = [
    (
        "NTB",
        [
            "nations trust bank",
            "nationstrust",
            "www.nationstrust.com",
            "consolidated monthly statement",
        ],
        0.55,
    ),
    (
        "SAMPATH",
        [
            "sampath bank",
            "sampathbank",
            "www.sampath.lk",
        ],
        0.5,
    ),
    (
        "BOC",
        ["bank of ceylon", "boc.lk", "boc bank"],
        0.55,
    ),
    (
        "COMMERCIAL",
        ["commercial bank", "combank", "combank.lk"],
        0.55,
    ),
    (
        "HNB",
        ["hatton national bank", "hnb.lk", "hnb bank"],
        0.55,
    ),
    (
        "DFCC",
        ["dfcc bank", "dfcc.lk"],
        0.5,
    ),
]

_FILENAME_HINTS: list[tuple[str, list[str], float]] = [
    ("NTB", ["ntb", "nations_trust", "nationstrust"], 0.45),
    ("SAMPATH", ["sampath", "smb_estatement", "smb_est"], 0.4),
    ("BOC", ["boc", "bank_of_ceylon"], 0.4),
    ("COMMERCIAL", ["commercial", "combank"], 0.35),
    ("HNB", ["hnb", "hatton"], 0.35),
    ("DFCC", ["dfcc"], 0.35),
]


def detect_bank(
    *,
    filename: str,
    text_probe: str | None = None,
    raw_bytes_probe: bytes | None = None,
) -> BankDetectionResult:
    """Score bank candidates from filename and optional UTF-8/Latin-1 text probe."""
    signals: list[str] = []
    scores: dict[str, float] = {}

    def add_score(code: str, delta: float, reason: str) -> None:
        scores[code] = scores.get(code, 0.0) + delta
        signals.append(f"{code}:{reason}")

    name = Path(filename).name.lower()
    for code, keywords, weight in _FILENAME_HINTS:
        if any(k in name for k in keywords):
            add_score(code, weight, f"filename_match({code})")

    blob = ""
    if text_probe:
        blob += text_probe.lower()
    if raw_bytes_probe:
        blob += raw_bytes_probe[:12000].decode("utf-8", errors="ignore").lower()

    for code, phrases, weight in _BANK_RULES:
        for phrase in phrases:
            if phrase in blob:
                add_score(code, weight, f"text_hit:{phrase}")
                break

    if not scores:
        return BankDetectionResult(bank_code=None, confidence=0.0, signals=["no_match"])

    best_code = max(scores, key=lambda k: scores[k])
    best_score = min(1.0, scores[best_code])
    if best_score < 0.35:
        return BankDetectionResult(
            bank_code=None,
            confidence=best_score,
            signals=signals + ["below_threshold"],
        )

    return BankDetectionResult(
        bank_code=best_code,
        confidence=round(best_score, 3),
        signals=signals,
    )
