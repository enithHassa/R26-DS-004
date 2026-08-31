import { describe, expect, it } from "vitest";

import type { SlabLine } from "../../api";
import { roundLkr } from "../format-lkr";
import { ordinaryTaxFromSlabs } from "./compute-scenario";

/** Simplified 6%/12% bands for unit checks (not a real YA schedule). */
const BANDS: SlabLine[] = [
  { band_index: 0, lower: 0, upper: 500_000, rate_percent: 6, slice: 0, tax: 0, band_label: "", quote: "", source_doc_id: "" },
  { band_index: 1, lower: 500_000, upper: null, rate_percent: 12, slice: 0, tax: 0, band_label: "", quote: "", source_doc_id: "" },
];

describe("ordinaryTaxFromSlabs / Tax Impact attribution", () => {
  it("matches the user’s example: 50k saved on 100k prior tax → 50% impact", () => {
    // Construct taxable so tax(with) ≈ 50_000 and tax(before) ≈ 100_000 after +applied.
    // With bands: tax(t) = 0.06*min(t,500k) + 0.12*max(0,t-500k)
    const taxableWith = 666_666.67;
    const applied = 1_083_333.33 - 666_666.67;
    const taxWith = ordinaryTaxFromSlabs(taxableWith, BANDS);
    const taxBefore = ordinaryTaxFromSlabs(taxableWith + applied, BANDS);
    const taxSaved = roundLkr(taxBefore - taxWith);
    const impact = (taxSaved / taxBefore) * 100;
    expect(taxWith).toBeCloseTo(50_000, 1);
    expect(taxBefore).toBeCloseTo(100_000, 1);
    expect(taxSaved).toBeCloseTo(50_000, 1);
    expect(Math.round(impact)).toBe(50);
  });
});
