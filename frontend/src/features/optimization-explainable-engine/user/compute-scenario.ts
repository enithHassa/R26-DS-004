import {
  postCalculate,
  type CalculateResponse,
  type ReliefLine,
  type SlabLine,
} from "../api";
import { buildCalculateRequest } from "../build-calculate-request";
import { roundLkr } from "../format-lkr";
import type { InterviewSession, ReliefAnswer } from "../types";

/** One relief opportunity with the tax payable cut attributable to that relief. */
export type TaxpayerOpportunity = ReliefLine & {
  /** LKR ordinary tax removed by this relief. */
  tax_saved: number;
  /** Ordinary tax if this relief were not applied (denominator for Tax Impact %). */
  tax_before: number;
};

export type TaxpayerComputeResult = {
  baseline: CalculateResponse;
  optimized: CalculateResponse;
  savings: number;
  opportunities: TaxpayerOpportunity[];
};

/** Same progressive-slab math as OE Engine `tax_from_slabs` (ordinary income tax only). */
export function ordinaryTaxFromSlabs(taxable: number, bands: SlabLine[]): number {
  const safeTaxable = Math.max(0, roundLkr(taxable));
  let total = 0;
  const ordered = [...bands].sort(
    (a, b) => (a.band_index ?? 0) - (b.band_index ?? 0),
  );
  for (const band of ordered) {
    const lower = Number(band.lower) || 0;
    const upper =
      band.upper == null || band.upper === ("" as unknown)
        ? null
        : Number(band.upper);
    const rate = Number(band.rate_percent) || 0;
    let slice = 0;
    if (safeTaxable <= lower) {
      slice = 0;
    } else if (upper == null || !Number.isFinite(upper)) {
      slice = Math.max(0, safeTaxable - lower);
    } else {
      slice = Math.max(0, Math.min(safeTaxable, upper) - lower);
    }
    total = roundLkr(total + roundLkr((slice * rate) / 100));
  }
  return total;
}

/**
 * Tax cut from one relief ≈ tax(taxable + applied) − tax(taxable), using the
 * optimized scenario’s slabs. Works for auto-applied reliefs (e.g. personal)
 * that cannot be toggled via claims.
 */
function taxAttributionForLine(
  line: ReliefLine,
  taxable: number,
  bands: SlabLine[],
): Pick<TaxpayerOpportunity, "tax_saved" | "tax_before"> {
  const applied = Math.max(0, line.applied || 0);
  const taxWith = ordinaryTaxFromSlabs(taxable, bands);
  const taxBefore = ordinaryTaxFromSlabs(taxable + applied, bands);
  const taxSaved = Math.max(0, taxBefore - taxWith);
  return { tax_saved: taxSaved, tax_before: taxBefore };
}

export async function computeTaxpayerScenario(
  session: InterviewSession,
  claims: ReliefAnswer[],
): Promise<TaxpayerComputeResult> {
  const baselineSession: InterviewSession = {
    ...session,
    reliefAnswers: [],
  };
  const optimizedSession: InterviewSession = {
    ...session,
    reliefAnswers: claims,
  };

  const [baseline, optimized] = await Promise.all([
    postCalculate(buildCalculateRequest(baselineSession)),
    postCalculate(buildCalculateRequest(optimizedSession)),
  ]);

  const savings = Math.max(0, (baseline.tax_payable ?? 0) - (optimized.tax_payable ?? 0));
  const taxable = optimized.taxable_income ?? 0;
  const bands = optimized.slab_lines ?? [];

  const opportunities: TaxpayerOpportunity[] = (optimized.relief_lines ?? [])
    .filter((line) => line.applied > 0)
    .map((line) => {
      const { tax_saved, tax_before } = taxAttributionForLine(line, taxable, bands);
      return { ...line, tax_saved, tax_before };
    })
    .sort((a, b) => b.tax_saved - a.tax_saved || b.applied - a.applied)
    .slice(0, 3);

  return { baseline, optimized, savings, opportunities };
}
