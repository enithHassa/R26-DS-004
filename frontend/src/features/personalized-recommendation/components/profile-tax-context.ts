import type { CalculateResponse as OeEngineCalculateResponse } from "@/features/optimization-explainable-engine/api";
import type { CalculateResponse as OeRagCalculateResponse } from "@/features/optimization-explainable/api";
import type { DerivedFeatures } from "../types";

export type ProfileTaxReliefLine = {
  name: string;
  applied: number;
  claimed: number;
};

export type ProfileTaxSummary = {
  taxableIncome: number;
  taxPayable: number;
  grossIncome: number;
  totalReliefs: number;
  reliefs: ProfileTaxReliefLine[];
  source: "snapshot" | "live";
  statusLabel?: string;
};

export function summaryFromOeEngineResult(
  result: OeEngineCalculateResponse,
  source: "snapshot" | "live",
  statusLabel?: string,
): ProfileTaxSummary {
  return {
    taxableIncome: result.taxable_income,
    taxPayable: result.tax_payable,
    grossIncome: result.gross_income,
    totalReliefs: result.total_reliefs,
    reliefs: result.relief_lines
      .filter((r) => r.applied > 0 || r.claim > 0)
      .map((r) => ({
        name: r.display_name,
        applied: r.applied,
        claimed: r.claim,
      })),
    source,
    statusLabel,
  };
}

export function summaryFromOeRagResult(
  result: OeRagCalculateResponse,
  source: "snapshot" | "live",
): ProfileTaxSummary {
  return {
    taxableIncome: result.taxable_income,
    taxPayable: result.tax_payable,
    grossIncome: result.gross_income,
    totalReliefs: result.total_reliefs,
    reliefs: result.relief_lines
      .filter((r) => r.applied > 0 || r.claim > 0)
      .map((r) => ({
        name: r.display_name,
        applied: r.applied,
        claimed: r.claim,
      })),
    source,
  };
}

export function summaryFromDerivedFeatures(features: DerivedFeatures): ProfileTaxSummary {
  const gross = Number(features.gross_annual_taxable_income);
  const tax = Number(features.baseline_tax_liability_annual);
  const grossSafe = Number.isFinite(gross) ? gross : 0;
  const taxSafe = Number.isFinite(tax) ? tax : 0;
  return {
    taxableIncome: grossSafe,
    taxPayable: taxSafe,
    grossIncome: grossSafe,
    totalReliefs: 0,
    reliefs: [],
    source: "live",
    statusLabel: "Comp 3 rules engine",
  };
}

export function parseSnapshotCalculateResult(
  raw: Record<string, unknown> | null | undefined,
): OeEngineCalculateResponse | null {
  if (!raw || typeof raw !== "object") return null;
  const taxable = Number(raw.taxable_income);
  const tax = Number(raw.tax_payable);
  if (!Number.isFinite(taxable) || !Number.isFinite(tax)) return null;
  return raw as unknown as OeEngineCalculateResponse;
}

/** Map profile tax_year (YYYY_YY) to OE assessment_year when formats align. */
export function profileTaxYearToAssessmentYear(taxYear: string): string {
  return taxYear.trim() || "2025_26";
}
