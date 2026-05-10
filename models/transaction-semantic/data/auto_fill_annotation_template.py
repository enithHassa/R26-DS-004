"""Auto-fill annotation CSV with taxonomy labels + IRD metadata (heuristic v1).

Uses narrative patterns common on Sri Lankan bank / e-wallet statements (Dialog Finance,
FriMi, NTB-style text) and maps them to keys in ``taxonomy.yaml``. Conservative: use
``unknown`` when no rule matches.

Also attaches ``act_reference`` and ``IRD_taxability`` from
``models/transaction-semantic/rules/sl_tax_rules_ira_2017_v1.yaml`` (first rule row per
``class_key``).

Legal sources in scope for this script's references (project PDFs you provided):
- Inland Revenue Act No. 24 of 2017 (as amended, including Acts No. 2/2025, 4/2023, etc.)
- Dataset_Specification_R26DS004.pdf (behavioural / deduction context — not a statute)

Outputs a NEW file by default so your hand-labeled CSV is not overwritten:
  ``annotation_template_extracted_filled.csv``

Review ``suggested_label`` / ``IRD_taxability`` / ``act_reference``, move labels to
``reviewer_label`` where you disagree, then run ``split_labeled_dataset.py``.

Usage::

    python models/transaction-semantic/data/auto_fill_annotation_template.py \\
        --input data/processed/transaction-semantic/annotation_template_extracted.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_RULEBOOK = REPO_ROOT / "models/transaction-semantic/rules/sl_tax_rules_ira_2017_v1.yaml"


def _load_class_ird_meta(rulebook_path: Path) -> dict[str, tuple[str, str]]:
    raw = yaml.safe_load(rulebook_path.read_text(encoding="utf-8"))
    rules = raw.get("rules") or {}
    out: dict[str, tuple[str, str]] = {}
    for _code, spec in rules.items():
        if not isinstance(spec, dict):
            continue
        ck = spec.get("class_key")
        if not isinstance(ck, str):
            continue
        ref = str(spec.get("rule_reference") or "")
        tax = str(spec.get("taxability_status") or "unknown")
        if ck not in out:
            out[ck] = (ref, tax)
    return out


# (pattern, label, confidence) — first match wins. Patterns run on lowercased description.
_HEURISTIC_RULES: list[tuple[re.Pattern[str], str, float]] = [
    # Internal wallet / round-up numeric rails (FriMi long account strings)
    (re.compile(r"^\s*\d{20,}\s"), "inter_account_transfer", 0.42),
    # Income-like inflows (credit side often implied by narrative; we still match text)
    (re.compile(r"\bsalary\b|\bpayroll\b|\bwages\b|\bapit\b|\bepf\b.*\bsalary\b|\bsal\s"), "employment_income", 0.55),
    (re.compile(r"\bbonus\b|\bincentive pay\b|\bperformance bonus\b"), "bonus_performance", 0.45),
    (
        re.compile(
            r"\binterest\b|\bint\.?\s*pd\b|\bint pd\b|\bsavings interest\b|\bfd interest\b|"
            r":\s*int\.?\s*pd\b|\baccrued interest\b",
        ),
        "interest_income",
        0.55,
    ),
    (re.compile(r"\bdividend\b|\bcse\b.*\bdiv\b"), "dividend_income", 0.4),
    (re.compile(r"\brent\b|\blease\b|\brental\b"), "rental_income", 0.35),
    (re.compile(r"\bfreelance\b|\bconsult(ancy|ing)\b|\binvoice\b|\bgig\b|\bupwork\b|\bfiverr\b"), "freelance_service", 0.4),
    (re.compile(r"\bbusiness\b.*\b(profit|receipt|sales)\b|\btrading\b"), "business_profit", 0.35),
    (re.compile(r"\bgratuity\b|\bretirement gratuity\b"), "gratuity", 0.55),
    (re.compile(r"\binsurance payout\b|\bclaim settlement\b|\blife insurance\b.*\bpayout\b"), "insurance_payout", 0.45),
    (re.compile(r"\bgift received\b|\bgift from\b"), "gift_received", 0.35),
    (re.compile(r"\breimbursement\b|\breimbursed\b"), "reimbursement", 0.35),
    # Loan / financing
    (re.compile(r"\bloan disbursement\b|\bdisbursement\b.*\bloan\b|\bpersonal loan\b.*\b(credit|received)\b"), "loan_received", 0.35),
    (re.compile(r"\bloan repayment\b|\bemi\b|\bhire purchase settlement\b|\bhp settlement\b"), "loan_repayment", 0.4),
    # Provident signals (often payroll deduction line)
    (re.compile(r"\bepf\b.*\b(deduct|employee|contribution)\b|\betf\b.*\bemployer\b|\bprovident fund\b"), "epf_etf_contribution", 0.45),
    # Qualifying / deductible flavour (narrow — not generic utility bills)
    (re.compile(r"\bdonation\b|\bcharity\b|\bpresident'?s fund\b|\bapproved charity\b"), "qualifying_payment", 0.4),
    (re.compile(r"\binsurance premium\b|\bmedical insurance premium\b|\blife insurance premium\b"), "qualifying_payment", 0.35),
    # Inter-account / wallet / bank rails (Dialog FriMi, CEFTS, FT rails)
    (
        re.compile(
            r"\b(cefts|eft|fund transfer|ft to_|ft from|ft to |from_dfp|to_dfp|to_ntb|to_hnb|to_comb|to_samp|to_boc|"
            r"to_pb|to_dfcc|to_lolc|from_dfp-|to_dfp-|frimi fund transfer|fund transfer from frimi|fund transfer from round|"
            r"fund transfer to round|topup_|invceft|ntb_xxxxxx|comb_xxxxxx|hnb_xxxxxx|dfcc_xxxxxx|"
            r"ub_xxxxxx|lolc_xxxxxx|_invceft)\b",
        ),
        "inter_account_transfer",
        0.52,
    ),
    (re.compile(r"\bfrimi atm\b|\batm withdrawal\b|\batm wdl\b|\bcash withdrawal\b"), "inter_account_transfer", 0.48),
    # Bank fees — not assessable income; neutral for income classifier
    (
        re.compile(
            r"\bft fee\b|\bfee_ntb\b|\bfee_samp\b|\bfee_comb\b|\bfee_hnb\b|\bfee_boc\b|\bfee_dfcc\b|\bfee_[a-z]{3,4}/",
        ),
        "inter_account_transfer",
        0.4,
    ),
    # Consumer / merchant spend (not in income taxonomy — leave unknown for tax-type classifier)
    (
        re.compile(
            r"\b(uber|pickme|netflix|spotify|pos transaction|mcdonald|kfc|cargills|keells|food city|"
            r"dfbill|ceb bill|hutch|dialog mobile|slt\b|telecom bill|fuel|petrol|lanka qr)\b",
        ),
        "unknown",
        0.25,
    ),
]


def _label_row(description: str, ird_meta: dict[str, tuple[str, str]]) -> tuple[str, float, str, str]:
    d = (description or "").strip().lower()
    if len(d) < 4:
        return "unknown", 0.0, ird_meta.get("unknown", ("Operational control", "unknown"))[0], ird_meta["unknown"][1]

    for pat, label, conf in _HEURISTIC_RULES:
        if pat.search(d):
            ref, tax = ird_meta.get(label, ("See taxonomy/rulebook", "unknown"))
            return label, conf, ref, tax

    return "unknown", 0.0, ird_meta.get("unknown", ("Operational control", "unknown"))[0], ird_meta["unknown"][1]


def run(
    *,
    input_csv: Path,
    output_csv: Path,
    rulebook_path: Path,
    fill_reviewer: bool,
) -> int:
    ird_meta = _load_class_ird_meta(rulebook_path)
    if "unknown" not in ird_meta:
        ird_meta["unknown"] = ("Operational control", "unknown")

    with input_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    extra = ["act_reference", "IRD_taxability", "auto_label_version", "final_label_hint"]
    for c in extra:
        if c not in fieldnames:
            fieldnames.append(c)

    version = "auto_heuristic_ird_v1"
    out_rows: list[dict[str, str]] = []
    counts: dict[str, int] = {}

    for row in rows:
        row = dict(row)
        desc = row.get("description") or ""
        label, conf, act_ref, tax = _label_row(desc, ird_meta)
        counts[label] = counts.get(label, 0) + 1

        row["suggested_label"] = label
        row["suggested_confidence"] = f"{conf:.3f}"
        row["act_reference"] = act_ref
        row["IRD_taxability"] = tax
        row["auto_label_version"] = version
        row["final_label_hint"] = "Use reviewer_label if set; else suggested_label"
        if fill_reviewer:
            row["reviewer_label"] = label
        if not row.get("label_source"):
            row["label_source"] = "auto_heuristic_v1"
        out_rows.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    print(f"wrote {len(out_rows)} rows to {output_csv}")
    print("label counts:", dict(sorted(counts.items(), key=lambda x: -x[1])[:15]), "... total classes", len(counts))
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Auto-fill annotation CSV with IRD-oriented labels.")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/transaction-semantic/annotation_template_extracted.csv"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/transaction-semantic/annotation_template_extracted_filled.csv"),
    )
    p.add_argument("--rulebook", type=Path, default=DEFAULT_RULEBOOK)
    p.add_argument(
        "--fill-reviewer-label",
        action="store_true",
        help="Also copy heuristic into reviewer_label (split uses reviewer in preference).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if not args.input.is_file():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    raise SystemExit(
        run(
            input_csv=args.input,
            output_csv=args.output,
            rulebook_path=args.rulebook,
            fill_reviewer=args.fill_reviewer_label,
        ),
    )
