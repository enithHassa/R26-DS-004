"""Text normalization aligned with Colab preprocess notebook."""

from __future__ import annotations

import re
import unicodedata


def normalize_unicode(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def clean_description(value: str) -> str:
    text = normalize_unicode(value or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def build_text_primary(
    *,
    description: str,
    bank_detected: str | None = None,
    direction: str | None = None,
    amount_band: str | None = None,
    document_type: str | None = None,
) -> str:
    parts = [clean_description(description)]
    if bank_detected and bank_detected.strip():
        parts.append(f"[bank:{bank_detected.strip().lower()}]")
    if direction and direction.strip():
        parts.append(f"[dir:{direction.strip().upper()}]")
    if amount_band and amount_band.strip():
        parts.append(f"[band:{amount_band.strip().lower()}]")
    if document_type and document_type.strip():
        parts.append(f"[doc:{document_type.strip().lower()}]")
    return " ".join(part for part in parts if part)
