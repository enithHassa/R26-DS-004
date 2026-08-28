import type { FinancialProfile } from "@/features/personalized-recommendation/types";

import { createDefaultTaxReturnDetail } from "./defaults";
import type { EmployerRow, TaxReturnDetail } from "./types";

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

function sumEmployerField(employers: EmployerRow[], key: keyof EmployerRow): number {
  return employers.reduce((sum, row) => {
    const raw = row[key];
    const n = raw === "" || raw == null ? 0 : Number(raw);
    return sum + (Number.isFinite(n) ? n : 0);
  }, 0);
}

/** ``2024-2025`` or ``2024`` → ``2024_25`` for the ORM ``tax_year`` column. */
export function taxYearToOrm(ya: string): string {
  const cleaned = ya.trim();
  if (/^\d{4}_\d{2}$/.test(cleaned)) {
    return cleaned;
  }
  if (cleaned.includes("-")) {
    const [start, end] = cleaned.split("-", 2);
    if (start && end) {
      return `${start}_${end.slice(-2)}`;
    }
  }
  if (/^\d{4}$/.test(cleaned)) {
    const start = Number(cleaned);
    return `${cleaned}_${String(start + 1).slice(-2)}`;
  }
  return cleaned;
}

function sumDonations(section6: TaxReturnDetail["section6"]): string {
  const total =
    Number(section6.charitablePresident || 0) +
    Number(section6.charitableApproved || 0) +
    Number(section6.charitableReligious || 0) +
    Number(section6.charitableOther || 0);
  return total > 0 ? String(total) : "";
}

/**
 * Fields the auditor sets for recommendations that the Tax Return Profile
 * must not overwrite on save (sent only via financial-intake / auditor wizard).
 */
export const RECOMMENDATION_ONLY_SCALAR_KEYS = [
  "monthly_expenses",
  "monthly_debt_service",
  "total_debt",
  "liquid_savings",
  "existing_investments",
  "vehicle_value",
  "property_value",
  "occupation",
  "employment_type",
  "employer_sector",
  "years_employed",
  "risk_tolerance",
  "investment_horizon_years",
  "retirement_age_target",
  "income_sources",
] as const;

export type TaxReturnProfileUpdatePayload = {
  full_name?: string;
  date_of_birth?: string;
  gender?: FinancialProfile["gender"];
  district?: string;
  marital_status?: FinancialProfile["marital_status"];
  residency_status?: FinancialProfile["residency_status"];
  nationality?: string | null;
  dependents?: number;
  gross_monthly_income?: string;
  annual_bonus_lkr?: string;
  epf_balance?: string;
  etf_balance?: string;
  health_insurance?: boolean;
  life_insurance_premium_annual?: string;
  home_loan_interest_annual?: string;
  donations_annual?: string;
  tax_year?: string;
  tax_return_detail: Record<string, unknown>;
  section_completion: number[];
};

export function detailFromProfile(profile: FinancialProfile): TaxReturnDetail {
  const base = createDefaultTaxReturnDetail(profile);
  const stored = profile.tax_return_detail;
  if (!isTaxReturnDetail(stored)) {
    return base;
  }
  return {
    ...base,
    section1: { ...base.section1, ...stored.section1 },
    section2: {
      ...base.section2,
      ...stored.section2,
      employers:
        stored.section2.employers?.length > 0
          ? stored.section2.employers
          : base.section2.employers,
    },
    section3: { ...base.section3, ...stored.section3 },
    section4: { ...base.section4, ...stored.section4 },
    section5: { ...base.section5, ...stored.section5 },
    section6: { ...base.section6, ...stored.section6 },
    section7: { ...base.section7, ...stored.section7 },
    section8: { ...base.section8, ...stored.section8 },
  };
}

/** Map Tax Return Profile → PATCH payload (Bucket A scalars + JSON blob only). */
export function detailToUpdatePayload(
  detail: TaxReturnDetail,
  completed: number[],
): TaxReturnProfileUpdatePayload {
  const s1 = detail.section1;
  const s2 = detail.section2;
  const s6 = detail.section6;
  const employers = s2.employers ?? [];

  const grossAnnual = sumEmployerField(employers, "gross");
  const bonusAnnual = sumEmployerField(employers, "bonus");
  const epfAnnual = sumEmployerField(employers, "epf");
  const etfAnnual = sumEmployerField(employers, "etf");
  const donations = sumDonations(s6);

  const payload: TaxReturnProfileUpdatePayload = {
    tax_return_detail: detail as unknown as Record<string, unknown>,
    section_completion: completed,
  };

  if (s1.fullName) payload.full_name = s1.fullName;
  if (s1.dob) payload.date_of_birth = s1.dob;
  if (s1.gender) payload.gender = s1.gender as FinancialProfile["gender"];
  if (s1.district) payload.district = s1.district;
  if (s1.marital) payload.marital_status = s1.marital as FinancialProfile["marital_status"];
  payload.residency_status =
    s1.residency === "non-resident"
      ? "non_resident"
      : s1.residency === "dual"
        ? "dual"
        : "resident";
  if (s1.nationality) {
    const natMap: Record<string, string> = {
      lk: "Sri Lankan",
      dual: "Dual Citizen",
      foreign: "Foreign",
    };
    payload.nationality = natMap[s1.nationality] ?? s1.nationality;
  }
  payload.dependents = Number(s1.dependants) || 0;
  if (s1.taxYear) payload.tax_year = taxYearToOrm(s1.taxYear);

  if (grossAnnual > 0) {
    payload.gross_monthly_income = String(Math.round(grossAnnual / 12));
  }
  if (bonusAnnual > 0) payload.annual_bonus_lkr = String(bonusAnnual);
  if (epfAnnual > 0) payload.epf_balance = String(epfAnnual);
  if (etfAnnual > 0) payload.etf_balance = String(etfAnnual);

  payload.health_insurance = s6.hasMedical || Number(s6.medicalPremium || 0) > 0;
  if (s6.lifePremium) payload.life_insurance_premium_annual = s6.lifePremium;
  if (s6.mortgageInterest) payload.home_loan_interest_annual = s6.mortgageInterest;
  if (donations) payload.donations_annual = donations;

  return payload;
}
