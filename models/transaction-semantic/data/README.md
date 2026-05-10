# Transaction Semantic Dataset Pipeline (Step 2)

Postgres is assumed (same DB as the FastAPI upload pipeline).

## 0) How much data do we have?

```bash
python models/transaction-semantic/data/dataset_inventory.py
python models/transaction-semantic/data/dataset_inventory.py --min-desc-len 12 --min-confidence 0.55 --json
```

Shows totals for `documents`, `extracted_transactions`, `transactions`, and **suitable_for_labeling** counts (non-empty description, positive amount, optional confidence / flagged filters), plus a breakdown by `bank_detected`.

## 1b) Auto-fill labels + IRD columns (heuristic, optional)

For a **first-pass** labeled file (pattern-based, conservative `unknown`), plus **`act_reference`** and **`IRD_taxability`** from `rules/sl_tax_rules_ira_2017_v1.yaml`:

```bash
python models/transaction-semantic/data/auto_fill_annotation_template.py \
  --input data/processed/transaction-semantic/annotation_template_extracted.csv \
  --output data/processed/transaction-semantic/annotation_template_extracted_filled.csv
```

- This is **not** a substitute for reading the Acts; use it to bootstrap, then correct **`reviewer_label`** where wrong.
- Add **`--fill-reviewer-label`** if you want `reviewer_label` copied from the heuristic (split prefers reviewer over suggested).

Primary statutory references in-repo: **IRA No. 24 of 2017** (rule YAML). Your PDF pack (Acts 2/2025, 4/2023, 10/2021, etc.) should be used when you tighten rules or hand-label edge cases.

## 1) Export labeling candidates (recommended: `extracted`)

Default source is **`extracted_transactions`** joined to **`documents`** (matches document uploads).

```bash
python models/transaction-semantic/data/build_labeling_dataset.py \
  --source extracted \
  --limit 12000 \
  --order random \
  --min-desc-len 10 \
  --min-confidence 0.0
```

Outputs under `data/processed/transaction-semantic/`:

| File | Purpose |
|------|---------|
| `label_candidates_extracted.csv` | Full feature columns for ML + audit |
| `llm_bootstrap_requests_extracted.jsonl` | One JSON per row for batch LLM labeling |
| `annotation_template_extracted.csv` | Same rows + empty `reviewer_label` / `suggested_label` |

### Columns (why they exist)

| Column | Use |
|--------|-----|
| `description` | Main text input for TF-IDF / transformer |
| `amount_lkr`, `amount_band`, `direction` | Numeric features; rules use amount + direction |
| `tx_date` | Time-based splits / assessment windows |
| `bank_detected`, `document_type`, `file_type` | Domain shift + doc-type feature |
| `debit` / `credit` | Optional explicit split from statement |
| `reference_no` | Weak labels / dispute trail |
| `parse_confidence`, `is_flagged` | Quality gate (raise `--min-confidence`, exclude flagged) |
| `row_id`, `document_id`, `filename`, `source_table` | Traceability and dedupe |

Legacy **`transactions`** only:

```bash
python models/transaction-semantic/data/build_labeling_dataset.py --source transactions --limit 5000
```

## 2) Create train/val/test splits from reviewed labels

After filling **`reviewer_label`** (preferred) or **`suggested_label`** in the annotation CSV:

```bash
python models/transaction-semantic/data/split_labeled_dataset.py \
  --labeled-csv data/processed/transaction-semantic/annotation_template_extracted.csv
```

Outputs:

- `train.csv`, `val.csv`, `test.csv`, `split_summary.json`

## Label policy

- Labels must exist in `models/transaction-semantic/taxonomy.yaml`.
- Classifier predicts taxonomy class only.
- Taxability is decided later by deterministic rules.
