#!/usr/bin/env python3
"""Merge modular YAML fragments into one TaxOptBRulePack-compatible file.

Usage (repo root):
  python scripts/compose_tax_opt_b_rules.py
  python scripts/compose_tax_opt_b_rules.py --manifest models/tax-optimization/rules/modular/MANIFEST.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMP_OPT = ROOT / "backend" / "comp-tax-optimization"
if str(COMP_OPT) not in sys.path:
    sys.path.insert(0, str(COMP_OPT))

from tax_opt_b_app.services.tax_opt_b_rules_loader import parse_tax_opt_b_rules_dict

PACK_KEYS = frozenset({
    "schema_version",
    "assessment_year",
    "currency",
    "sources",
    "thresholds",
    "allowed_relief_codes",
    "rules",
})


def _deep_merge_thresholds(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if k == "deductions" and isinstance(v, dict) and isinstance(out.get("deductions"), dict):
            merged = dict(out["deductions"])
            merged.update(v)
            out["deductions"] = merged
        else:
            out[k] = v
    return out


def _merge_fragments(fragments: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for raw in fragments:
        if not raw:
            continue
        for key, val in raw.items():
            if key not in PACK_KEYS or val is None:
                continue
            if key == "thresholds":
                if not isinstance(val, dict):
                    raise ValueError("thresholds fragment must be a mapping")
                prev = merged.get("thresholds")
                if not prev:
                    merged["thresholds"] = dict(val)
                else:
                    merged["thresholds"] = _deep_merge_thresholds(prev, val)
            elif key in ("sources", "rules"):
                merged.setdefault(key, [])
                if isinstance(val, list):
                    merged[key].extend(val)
                else:
                    raise ValueError(f"{key} must be a list when present")
            elif key == "allowed_relief_codes":
                merged.setdefault(key, [])
                if isinstance(val, list):
                    merged[key].extend(str(x) for x in val)
                else:
                    raise ValueError("allowed_relief_codes must be a list")
            else:
                merged[key] = val
    if merged.get("allowed_relief_codes"):
        merged["allowed_relief_codes"] = list(dict.fromkeys(merged["allowed_relief_codes"]))
    return merged


def _load_manifest(path: Path) -> tuple[Path, list[Path]]:
    with path.open(encoding="utf-8") as f:
        m = yaml.safe_load(f)
    if not isinstance(m, dict):
        raise ValueError("MANIFEST root must be a mapping")
    out_rel = m.get("output")
    if not isinstance(out_rel, str) or not out_rel.strip():
        raise ValueError("MANIFEST must set non-empty string 'output'")
    includes = m.get("includes")
    if not isinstance(includes, list) or not includes:
        raise ValueError("MANIFEST must set non-empty list 'includes'")
    base = path.parent
    paths: list[Path] = []
    for item in includes:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("each includes[] entry must be a non-empty string")
        frag = (base / item).resolve()
        paths.append(frag)
    return ROOT / out_rel, paths


def _load_fragment(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Fragment not found: {path}")
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be a mapping or empty document")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose modular tax rule YAML into one pack file.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "models" / "tax-optimization" / "rules" / "modular" / "MANIFEST.yaml",
    )
    parser.add_argument("--check", action="store_true", help="Validate with parse_tax_opt_b_rules_dict only")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    out_path, frag_paths = _load_manifest(manifest_path)
    fragments = [_load_fragment(p) for p in frag_paths]
    merged = _merge_fragments(fragments)
    parse_tax_opt_b_rules_dict(merged, path=out_path)
    if args.check:
        print("OK:", manifest_path)
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(
            "# Composed from modular fragments — edit sources under models/tax-optimization/rules/modular/\n"
            "# and re-run: python scripts/compose_tax_opt_b_rules.py\n\n"
        )
        yaml.safe_dump(
            merged,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    print(f"Wrote {out_path.relative_to(ROOT)} ({len(frag_paths)} fragments)")


if __name__ == "__main__":
    main()
