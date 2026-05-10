"""Split a .cypher file into executable statements (skip // full-line comments)."""

from __future__ import annotations


def statements_from_cypher(text: str) -> list[str]:
    lines: list[str] = []
    for ln in text.splitlines():
        stripped = ln.strip()
        if stripped.startswith("//"):
            continue
        lines.append(ln)
    blob = "\n".join(lines)
    out: list[str] = []
    for part in blob.split(";"):
        s = part.strip()
        if s:
            out.append(s + ";")
    return out
