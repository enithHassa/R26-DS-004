/**
 * Bridge Tax Return Profile year labels (2024-2025) and OE Engine YA keys (2024_25).
 */

/** TRP / profile `tax_year` → OE `assessment_year`. */
export function trpTaxYearToOeAssessmentYear(taxYear: string): string | null {
  const trimmed = taxYear.trim();
  const dashed = trimmed.match(/^(\d{4})-(\d{4})$/);
  if (dashed) {
    return `${dashed[1]}_${dashed[2].slice(-2)}`;
  }
  const underscored = trimmed.match(/^(\d{4})_(\d{2})$/);
  if (underscored) {
    return trimmed;
  }
  return null;
}

/** Normalize document / rollup `tax_year` for API filters. */
export function normalizeDocumentTaxYear(taxYear: string | null | undefined): string | undefined {
  if (!taxYear?.trim()) return undefined;
  const oe = trpTaxYearToOeAssessmentYear(taxYear);
  return oe ?? taxYear.trim();
}
