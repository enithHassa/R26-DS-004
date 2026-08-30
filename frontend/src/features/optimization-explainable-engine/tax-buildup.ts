import type { CalculateResponse, SlabLine } from "./api";
import { formatLkr } from "./format-lkr";

export function sortedSlabLines(lines: SlabLine[] | undefined | null): SlabLine[] {
  return [...(lines ?? [])].sort(
    (a, b) => (a.band_index ?? 0) - (b.band_index ?? 0),
  );
}

/** Bands that actually received taxable income (slice > 0). */
export function activeSlabLines(lines: SlabLine[] | undefined | null): SlabLine[] {
  return sortedSlabLines(lines).filter((b) => (b.slice ?? 0) > 0);
}

export function slabKey(band: SlabLine, index: number): string {
  return `${band.band_index ?? index}-${band.rate_percent}-${band.lower}-${band.upper ?? "open"}`;
}

export function ordinaryTaxFromSlabs(lines: SlabLine[] | undefined | null): number {
  return (lines ?? []).reduce((sum, b) => sum + (b.tax ?? 0), 0);
}

export type TaxBuildupSummary = {
  taxable: number;
  bands: SlabLine[];
  ordinaryTax: number;
  terminalTax: number;
  taxPayable: number;
  apitCredit: number;
  whtCredit: number;
  balancePayable: number;
  taxRefund: number;
};

export function taxBuildupFromResult(result: CalculateResponse): TaxBuildupSummary {
  const bands = activeSlabLines(result.slab_lines);
  const ordinaryTax = ordinaryTaxFromSlabs(result.slab_lines);
  const terminalTax = result.terminal_benefit_tax ?? 0;
  const apitCredit = result.apit_credit ?? 0;
  const whtCredit = result.wht_credit ?? 0;
  return {
    taxable: result.taxable_income,
    bands,
    ordinaryTax,
    terminalTax,
    taxPayable: result.tax_payable,
    apitCredit,
    whtCredit,
    balancePayable: result.balance_payable ?? result.tax_payable,
    taxRefund: result.tax_refund ?? 0,
  };
}

export function formatBandRange(band: SlabLine): string {
  const lower = formatLkr(band.lower ?? 0);
  if (band.upper == null) return `${lower}+`;
  return `${lower} – ${formatLkr(band.upper)}`;
}
