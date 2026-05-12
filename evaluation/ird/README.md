# Committed IRD manifest snapshot (Phase 1b)

`data/raw/` is gitignored in this repo, so **canonical CSV copies** used for your Tier A/B ingest live here:

- `source_manifest_filled.csv` — official IRD `source_url` values, `file_name` matching `data/raw/ird/downloads/`, and `sha256` from the run that produced `corpus_v1`.

To reproduce locally:

1. Copy PDFs into `data/raw/ird/downloads/` with the same `file_name` column values.
2. Copy `source_manifest_filled.csv` to `data/raw/ird/source_manifest_filled.csv` (or use `--manifest` pointing here).
3. Run `scripts/ird_phase1b_finalize.py` with `--files-root data/raw/ird/downloads`.

Lex Specialis starter (manual refinement): `lex_specialis_edges.csv`.
