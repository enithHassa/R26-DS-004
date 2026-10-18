import type { CalculateResponse } from "@/features/optimization-explainable-engine/api";
import {
  businessIncomeLkr,
  employmentIncomeLkr,
  interestIncomeLkr,
  investmentIncomeLkr,
  otherIncomeLkr,
  rentsIncomeLkr,
} from "@/features/optimization-explainable-engine/income-aggregate";
import type { InterviewSession } from "@/features/optimization-explainable-engine/types";
import type { ProfileTaxableIncomeMonthlyResponse } from "@/features/personalized-recommendation/api/profiles";
import type { FinancialProfile } from "@/features/personalized-recommendation/types";
import { detailFromProfile } from "@/features/tax-return-profile/mappers";
import type { TaxReturnDetail } from "@/features/tax-return-profile/types";
import { taxYearForUi } from "@/lib/profile-bridge/tax-year-bridge";

import type { TaxReturnExportPayload } from "./api";

function num(raw: string | undefined | null): number {
  if (raw == null || raw === "") return 0;
  const n = Number(String(raw).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function yaLabel(assessmentYear: string, detail: TaxReturnDetail): string {
  const fromProfile = taxYearForUi(detail.section1.taxYear || assessmentYear);
  if (fromProfile.includes("-")) return fromProfile.replace(/-/g, "/");
  if (fromProfile.includes("/")) return fromProfile;
  if (assessmentYear.includes("_")) {
    const [a, b] = assessmentYear.split("_");
    return `${a}/${b}`;
  }
  return assessmentYear || "—";
}

function interestLinesFromDetail(detail: TaxReturnDetail): TaxReturnExportPayload["interest_lines"] {
  const lines: TaxReturnExportPayload["interest_lines"] = [];

  for (const fd of detail.section3.fds) {
    if (!fd.interest && !fd.wht && !fd.principal) continue;
    lines.push({
      bank: fd.bank || "Fixed deposit",
      source_type: "FD INTEREST",
      withholding_agent_tin: "",
      wht_certificate_no: "",
      date: fd.maturity || "",
      account_or_fd_no: fd.accNo || "",
      type: "FD",
      fd_amount: num(fd.principal) || null,
      gross_interest: num(fd.interest),
      wht: num(fd.wht),
    });
  }

  if (detail.section3.hasSavings && num(detail.section3.savingsInterest) > 0) {
    lines.push({
      bank: "Savings interest",
      source_type: "SAVINGS INTEREST",
      withholding_agent_tin: "",
      wht_certificate_no: "",
      date: "",
      account_or_fd_no: "",
      type: "SAVINGS",
      fd_amount: null,
      gross_interest: num(detail.section3.savingsInterest),
      wht: num(detail.section3.savingsWht),
    });
  }

  if (detail.section3.hasGovSec && num(detail.section3.govInterest) > 0) {
    lines.push({
      bank: "Government securities",
      source_type: "FD INTEREST",
      withholding_agent_tin: "",
      wht_certificate_no: "",
      date: "",
      account_or_fd_no: "",
      type: "FD",
      fd_amount: null,
      gross_interest: num(detail.section3.govInterest),
      wht: num(detail.section3.govWht),
    });
  }

  if (detail.section3.hasUnitTrust && num(detail.section3.unitTrustDistribution) > 0) {
    lines.push({
      bank: detail.section3.unitTrustFund || "Unit trust",
      source_type: "FD INTEREST",
      withholding_agent_tin: "",
      wht_certificate_no: "",
      date: "",
      account_or_fd_no: "",
      type: "FD",
      fd_amount: null,
      gross_interest: num(detail.section3.unitTrustDistribution),
      wht: num(detail.section3.unitTrustWht),
    });
  }

  return lines;
}

function pensionFromDetail(detail: TaxReturnDetail): TaxReturnExportPayload["pension"] {
  if (!detail.section2.hasPension || num(detail.section2.pensionAmount) <= 0) {
    return null;
  }
  const annual = num(detail.section2.pensionAmount);
  const payer = detail.section2.pensionPayer || "";
  const kind = detail.section2.pensionType || "";
  return {
    pensioner_name: detail.section1.fullName || "",
    status_note: [payer, kind, "Annual total from tax return profile"]
      .filter(Boolean)
      .join(" · "),
    pension_number: "",
    lines: [
      {
        pen_date: "YA total",
        bpen: 0,
        cla: 0,
        ota: 0,
        spa: 0,
        dsa: 0,
        maa: 0,
        sur: 0,
        tded: 0,
        tpen: annual,
        pnet: annual,
      },
    ],
  };
}

function taxableSummaryFromComp1(
  monthly: ProfileTaxableIncomeMonthlyResponse | null | undefined,
): TaxReturnExportPayload["taxable_summary"] {
  if (!monthly) return null;
  return {
    total_taxable_lkr: num(monthly.total_taxable_lkr),
    covered_month_count: monthly.covered_month_count,
    missing_month_count: monthly.missing_month_count,
    lines: monthly.lines.map((line) => ({
      class_key: line.class_key,
      calendar_month: line.calendar_month,
      taxable_amount_lkr: num(line.taxable_amount_lkr),
      transaction_count: line.transaction_count,
    })),
  };
}

export type BuildExportArgs = {
  profile: FinancialProfile;
  session: InterviewSession;
  calculateResult: CalculateResponse;
  taxableMonthly?: ProfileTaxableIncomeMonthlyResponse | null;
  referenceCode?: string;
};

/** Assemble the OE `/export/tax-return` payload from profile + OE + Comp1. */
export function buildTaxReturnExportPayload(args: BuildExportArgs): TaxReturnExportPayload {
  const detail = detailFromProfile(args.profile);
  const { session, calculateResult } = args;
  const income = session.income;

  return {
    header: {
      full_name: income.taxpayerName || detail.section1.fullName || args.profile.full_name || "",
      tin: income.tin || detail.section1.tin || "",
      assessment_year_label: yaLabel(session.assessmentYear, detail),
      reference_code: args.referenceCode || "",
    },
    income_breakdown: {
      employment: employmentIncomeLkr(income),
      interest: interestIncomeLkr(income),
      business: businessIncomeLkr(income),
      rents: rentsIncomeLkr(income),
      other: otherIncomeLkr(income),
      investment: investmentIncomeLkr(income),
    },
    calculate_result: calculateResult as unknown as Record<string, unknown>,
    interest_lines: interestLinesFromDetail(detail),
    pension: pensionFromDetail(detail),
    taxable_summary: taxableSummaryFromComp1(args.taxableMonthly),
  };
}
