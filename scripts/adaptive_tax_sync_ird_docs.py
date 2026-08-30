"""Sync Desktop IRD_Docs PDFs into data/raw/adaptive-tax (Phase 6.0).

Maps Desktop filenames to corpus_manifest.json ``file_name`` values.
Does not rebuild Chroma (run adaptive_tax_build_chroma.py separately when needed).
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from backend.shared.config.settings import PROJECT_ROOT

# Desktop name → manifest file_name (when they differ).
_DESKTOP_ALIASES: dict[str, str] = {
    "IR_Act_No_24_2017_E.pdf": "IR_Act_No._24_2017_E.pdf",
}


def _manifest_docs() -> list[dict]:
    path = PROJECT_ROOT / "models" / "adaptive-tax" / "corpus_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("documents") or [])


def sync_ird_docs(
    *,
    source_dir: Path,
    dest_dir: Path,
    dry_run: bool = False,
) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    messages: list[str] = []
    # Build reverse: dest file_name -> possible source names
    wanted = [
        d["file_name"]
        for d in _manifest_docs()
        if d.get("doc_type") == "pdf" and d.get("source_doc_id") != "ird-calc-ontology-v5"
    ]
    alias_rev = {v: k for k, v in _DESKTOP_ALIASES.items()}
    for dest_name in wanted:
        candidates = [dest_name]
        if dest_name in alias_rev:
            candidates.insert(0, alias_rev[dest_name])
        src: Path | None = None
        for cand in candidates:
            p = source_dir / cand
            if p.is_file():
                src = p
                break
        if src is None:
            messages.append(f"MISSING {dest_name}")
            continue
        dest = dest_dir / dest_name
        if dry_run:
            messages.append(f"WOULD_COPY {src.name} -> {dest_name}")
            continue
        shutil.copy2(src, dest)
        messages.append(f"OK {src.name} -> {dest_name} ({dest.stat().st_size} bytes)")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(r"c:\Users\H P\Desktop\Research_Project\IRD_Docs"),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "adaptive-tax",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for line in sync_ird_docs(
        source_dir=args.source, dest_dir=args.dest, dry_run=args.dry_run
    ):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
