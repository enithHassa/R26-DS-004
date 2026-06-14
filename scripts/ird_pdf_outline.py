"""Extract PDF bookmark/outline trail for corpus chunk metadata (Phase 1b)."""

from __future__ import annotations

from typing import Any


def flatten_pdf_outline(reader: Any) -> list[tuple[int, str]]:
    """Return (1-based page, title) for each outline node, in traversal order."""
    outline = getattr(reader, "outline", None) or []
    if not outline:
        return []

    flat: list[tuple[int, str]] = []

    def walk(items: list[Any] | Any) -> None:
        if not isinstance(items, list):
            items = [items]
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            try:
                page = int(reader.get_destination_page_number(item)) + 1
            except Exception:
                continue
            title = getattr(item, "title", None)
            title = str(title).strip() if title else ""
            if title:
                flat.append((page, title))

    walk(outline)
    return flat


def outline_breadcrumb_map(
    flat: list[tuple[int, str]],
    page_nums: list[int],
    *,
    max_trail: int = 8,
) -> dict[int, list[str] | None]:
    """Precompute running outline titles for each PDF page number."""
    return {p: outline_breadcrumb_for_page(flat, p, max_trail=max_trail) for p in page_nums}


def outline_breadcrumb_for_page(
    flat: list[tuple[int, str]],
    page: int,
    *,
    max_trail: int = 8,
) -> list[str] | None:
    """Titles for outline destinations with page <= ``page`` (running section context)."""
    if not flat:
        return None
    indexed = [(i, p, t) for i, (p, t) in enumerate(flat)]
    indexed.sort(key=lambda x: (x[1], x[0]))
    chain = [t for _, p, t in indexed if p <= page]
    if not chain:
        return None
    return chain[-max_trail:]
