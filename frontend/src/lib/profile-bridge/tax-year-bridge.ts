/**
 * Bridge Tax Return Profile year labels (2024-2025, 2024 / 2025) and ORM/OE keys (2024_25).
 */

/** Normalize any YA label to ORM ``tax_year`` (`2024_25`) or null if unparseable. */
export function normalizeTaxYearToOrm(ya: string | null | undefined): string | null {
  if (!ya?.trim()) return null;

  const compact = ya.trim().replace(/\s+/g, "");
  if (/^\d{4}_\d{2}$/.test(compact)) {
    return compact;
  }

  const slashOrShortDash = compact.match(/^(\d{4})[/-](\d{2,4})$/);
  if (slashOrShortDash) {
    const end = slashOrShortDash[2].length === 2 ? slashOrShortDash[2] : slashOrShortDash[2].slice(-2);
    return `${slashOrShortDash[1]}_${end}`;
  }

  const dashed = compact.match(/^(\d{4})-(\d{4})$/);
  if (dashed) {
    return `${dashed[1]}_${dashed[2].slice(-2)}`;
  }

  if (/^\d{4}$/.test(compact)) {
    const start = Number(compact);
    return `${compact}_${String(start + 1).slice(-2)}`;
  }

  return null;
}

/** ORM / mixed YA label → TRP Sec 1 dropdown value (`2024-2025`). */
export function taxYearForUi(ya: string | null | undefined): string {
  if (!ya?.trim()) return "";
  if (ya.includes("-") && !/^\d{4}_\d{2}$/.test(ya.trim())) {
    const dashed = ya.trim().replace(/\s+/g, "").replace(/\//g, "-");
    const match = /^(\d{4})-(\d{4})$/.exec(dashed);
    if (match) return `${match[1]}-${match[2]}`;
    const short = /^(\d{4})-(\d{2})$/.exec(dashed);
    if (short) {
      const endYear = `${short[1].slice(0, 2)}${short[2]}`;
      return `${short[1]}-${endYear}`;
    }
    return ya.trim();
  }

  const orm = normalizeTaxYearToOrm(ya);
  if (!orm) return ya.trim();

  const [start, endShort] = orm.split("_");
  const endYear = `${start.slice(0, 2)}${endShort}`;
  return `${start}-${endYear}`;
}

/** TRP / profile `tax_year` → OE `assessment_year`. */
export function trpTaxYearToOeAssessmentYear(taxYear: string): string | null {
  return normalizeTaxYearToOrm(taxYear);
}

/** Normalize document / rollup `tax_year` for API filters. */
export function normalizeDocumentTaxYear(taxYear: string | null | undefined): string | undefined {
  const orm = normalizeTaxYearToOrm(taxYear);
  return orm ?? taxYear?.trim() ?? undefined;
}
