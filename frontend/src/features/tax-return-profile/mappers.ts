import type {
  FinancialProfile,
  FinancialProfileCreate,
} from "@/features/personalized-recommendation/types";

import { createDefaultTaxReturnDetail } from "./defaults";
import type { TaxReturnDetail } from "./types";

function isTaxReturnDetail(value: unknown): value is TaxReturnDetail {
  if (!value || typeof value !== "object") return false;
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.section1 === "object" &&
    obj.section1 != null &&
    typeof obj.section2 === "object" &&
    obj.section2 != null
  );
}

export function detailFromProfile(profile: FinancialProfile): TaxReturnDetail {
  const stored = profile.tax_return_detail;
  if (isTaxReturnDetail(stored)) {
    return stored;
  }
  return createDefaultTaxReturnDetail(profile);
}

export function detailToUpdatePayload(
  detail: TaxReturnDetail,
  completed: number[],
): Partial<FinancialProfileCreate> & {
  tax_return_detail: Record<string, unknown>;
  section_completion: number[];
} {
  const s1 = detail.section1;
  const s2 = detail.section2;
  const primaryEmployer = s2.employers[0];

  return {
    full_name: s1.fullName,
    gender: s1.gender as FinancialProfileCreate["gender"],
    province: s1.province.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    marital_status: s1.marital as FinancialProfileCreate["marital_status"],
    residency_status:
      s1.residency === "non-resident"
        ? "non_resident"
        : s1.residency === "dual"
          ? "dual"
          : "resident",
    dependents: Number(s1.dependants) || 0,
    gross_monthly_income: primaryEmployer?.gross
      ? String(Math.round(Number(primaryEmployer.gross) / 12))
      : undefined,
    annual_bonus_lkr: primaryEmployer?.bonus,
    epf_balance: primaryEmployer?.epf,
    etf_balance: primaryEmployer?.etf,
    life_insurance_premium_annual: detail.section6.lifePremium,
    home_loan_interest_annual: detail.section6.mortgageInterest,
    donations_annual: detail.section6.charitableApproved,
    tax_year: s1.taxYear.split("-")[0] ?? s1.taxYear,
    tax_return_detail: detail as unknown as Record<string, unknown>,
    section_completion: completed,
  };
}
