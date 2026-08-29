import { detailFromProfile } from "@/features/tax-return-profile/mappers";
import { normalizeTaxYearToOrm } from "@/lib/profile-bridge/tax-year-bridge";
import type { TaxReturnDetail } from "@/features/tax-return-profile/types";
import type { FinancialProfile } from "@/features/personalized-recommendation/types";
import type {
  InterviewIncomeState,
  InterestScheduleLine,
  TerminalBenefitRow,
} from "@/features/optimization-explainable-engine/types";
import { hydrateIncomeAmounts } from "@/features/optimization-explainable-engine/types";

function num(raw: string | undefined | null): number {
  if (raw == null || raw === "") return 0;
  const n = Number(String(raw).replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function str(n: number): string {
  return n > 0 ? String(Math.round(n)) : "0";
}

function sumEmployerField(
  detail: TaxReturnDetail,
  key: "gross" | "bonus" | "overtime" | "allowances" | "apit",
): number {
  return detail.section2.employers.reduce((sum, row) => sum + num(row[key]), 0);
}

function buildInterestSchedule(detail: TaxReturnDetail): InterestScheduleLine[] {
  const lines: InterestScheduleLine[] = [];
  let idx = 0;

  for (const fd of detail.section3.fds) {
    if (!fd.interest && !fd.wht) continue;
    lines.push({
      id: `profile-fd-${idx++}`,
      label: fd.bank ? `${fd.bank} FD` : `Fixed deposit ${idx}`,
      interest: fd.interest || "0",
      wht: fd.wht || "0",
    });
  }

  if (detail.section3.hasSavings && num(detail.section3.savingsInterest) > 0) {
    lines.push({
      id: `profile-savings-${idx++}`,
      label: "Savings interest",
      interest: detail.section3.savingsInterest || "0",
      wht: detail.section3.savingsWht || "0",
    });
  }

  if (detail.section3.hasGovSec && num(detail.section3.govInterest) > 0) {
    lines.push({
      id: `profile-gov-${idx++}`,
      label: "Government securities interest",
      interest: detail.section3.govInterest || "0",
      wht: detail.section3.govWht || "0",
    });
  }

  if (detail.section3.hasUnitTrust && num(detail.section3.unitTrustDistribution) > 0) {
    lines.push({
      id: `profile-ut-${idx++}`,
      label: detail.section3.unitTrustFund || "Unit trust distribution",
      interest: detail.section3.unitTrustDistribution || "0",
      wht: detail.section3.unitTrustWht || "0",
    });
  }

  return lines;
}

function totalInterestFromSchedule(lines: InterestScheduleLine[]): number {
  return lines.reduce((sum, line) => sum + num(line.interest), 0);
}

function totalDividends(detail: TaxReturnDetail): number {
  return detail.section3.divs.reduce((sum, row) => sum + num(row.total), 0);
}

function totalRents(detail: TaxReturnDetail): number {
  return detail.section5.properties.reduce(
    (sum, row) => sum + num(row.gross || row.rent),
    0,
  );
}

function businessTotals(detail: TaxReturnDetail): { gross: number; deductions: number } {
  let gross = 0;
  let deductions = 0;

  for (const biz of detail.section4.businesses) {
    gross += num(biz.revenue);
    deductions +=
      num(biz.cogs) +
      num(biz.wages) +
      num(biz.rent) +
      num(biz.utilities) +
      num(biz.depreciation) +
      num(biz.professional) +
      num(biz.advertising) +
      num(biz.other);
  }

  if (detail.section4.hasFreelance) {
    gross += num(detail.section4.freelanceLkr);
    deductions +=
      num(detail.section4.freelanceExpenses) + num(detail.section4.freelanceCommissions);
  }

  if (detail.section4.hasProfessional) {
    gross += num(detail.section4.professionalRevenue);
    deductions += num(detail.section4.professionalExpenses);
  }

  if (detail.section4.hasAgri) {
    gross += num(detail.section4.agriRevenue);
    deductions += num(detail.section4.agriExpenses);
  }

  return { gross, deductions };
}

function buildTerminalBenefits(detail: TaxReturnDetail): TerminalBenefitRow[] {
  const rows: TerminalBenefitRow[] = [];
  let idx = 0;

  if (detail.section2.hasGratuity && num(detail.section2.gratuityAmount) > 0) {
    rows.push({
      id: `profile-gratuity-${idx++}`,
      type: "retiring_gratuity",
      amount: detail.section2.gratuityAmount,
      employmentPeriodOver20Years: num(detail.section2.gratuityYears) >= 20,
      lossOfOfficeSchemeApproved: false,
      terminalBenefitPeriod: "",
    });
  }

  if (detail.section2.hasSeverance && num(detail.section2.severanceAmount) > 0) {
    rows.push({
      id: `profile-severance-${idx++}`,
      type: "loss_of_office_compensation",
      amount: detail.section2.severanceAmount,
      employmentPeriodOver20Years: false,
      lossOfOfficeSchemeApproved: false,
      terminalBenefitPeriod: "",
    });
  }

  return rows;
}

export type ProfileToOeResult = {
  assessmentYear: string;
  income: InterviewIncomeState;
};

/** Map Tax Return Profile detail into OE Engine user-side income fields. */
export function taxReturnDetailToInterviewIncome(
  detail: TaxReturnDetail,
): ProfileToOeResult {
  const interestSchedule = buildInterestSchedule(detail);
  const interestTotal = totalInterestFromSchedule(interestSchedule);
  const dividendTotal = totalDividends(detail);
  const rentTotal = totalRents(detail);
  const { gross: bizGross, deductions: bizDeductions } = businessTotals(detail);
  const terminalBenefits = buildTerminalBenefits(detail);

  const salary = sumEmployerField(detail, "gross");
  const bonus = sumEmployerField(detail, "bonus");
  const overtime = sumEmployerField(detail, "overtime");
  const allowances = sumEmployerField(detail, "allowances");
  const apit = sumEmployerField(detail, "apit");

  const income = hydrateIncomeAmounts({
    taxpayerName: detail.section1.fullName || "",
    tin: detail.section1.tin || "",
    form: {
      employment_income: "0",
      employment_final_withholding: "0",
      business_income: "0",
      business_gross: str(bizGross),
      business_deductions: str(bizDeductions),
      capital_allowances: "0",
      investment_income: "0",
      investment_final_withholding: "0",
      other_income: "0",
      other_final_withholding: "0",
    },
    employmentMode: "components",
    businessMode: bizGross > 0 ? "breakdown" : "net",
    investmentMode: "components",
    otherMode: "components",
    employmentAmounts: {
      emp_salary: str(salary),
      emp_bonus: str(bonus),
      emp_overtime: str(overtime),
      emp_housing_allowance: str(allowances),
      emp_commission: detail.section2.hasCommission ? detail.section2.commissionAmount || "0" : "0",
      emp_pension: detail.section2.hasPension ? detail.section2.pensionAmount || "0" : "0",
      emp_gifts: detail.section2.hasGifts ? detail.section2.giftAmount || "0" : "0",
      emp_gratuity: detail.section2.hasGratuity ? detail.section2.gratuityAmount || "0" : "0",
    },
    businessAmounts: {
      biz_gross: str(bizGross),
      biz_deductions: str(bizDeductions),
      biz_net_profits: str(Math.max(0, bizGross - bizDeductions)),
    },
    investmentAmounts: {
      inv_interest: str(interestTotal),
      inv_dividends: str(dividendTotal),
      inv_rents: str(rentTotal),
    },
    otherAmounts: {},
    otherCustomRows: [],
    interestSchedule,
    apitAlreadyPaid: str(apit),
    hasTerminalBenefits: terminalBenefits.length > 0,
    terminalBenefits,
  });

  const assessmentYear = normalizeTaxYearToOrm(detail.section1.taxYear || "") || "2025_26";

  return { assessmentYear, income };
}

export function profileToInterviewIncome(profile: FinancialProfile): ProfileToOeResult {
  const detail = detailFromProfile(profile);
  return taxReturnDetailToInterviewIncome(detail);
}
