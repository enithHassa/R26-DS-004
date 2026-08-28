import type { FinancialProfile } from "@/features/personalized-recommendation/types";

import type {
  BizRow,
  DivRow,
  EmployerRow,
  FdRow,
  PropRow,
  Section1Detail,
  Section2Detail,
  Section3Detail,
  Section4Detail,
  Section5Detail,
  Section6Detail,
  Section7Detail,
  Section8Detail,
  TaxReturnDetail,
} from "./types";

export const blankEmployer = (): EmployerRow => ({
  name: "",
  tin: "",
  role: "",
  from: "",
  to: "",
  current: "yes",
  gross: "",
  apit: "",
  epf: "",
  etf: "",
  bonus: "",
  allowances: "",
  noncash: "",
  overtime: "",
});

export const blankFd = (): FdRow => ({
  bank: "",
  accNo: "",
  maturity: "",
  principal: "",
  interest: "",
  wht: "",
  type: "fd",
});

export const blankDiv = (): DivRow => ({
  company: "",
  shares: "",
  dps: "",
  total: "",
  wht: "",
  resident: "yes",
});

export const blankBiz = (): BizRow => ({
  name: "",
  regNo: "",
  type: "sole",
  nature: "",
  start: "",
  revenue: "",
  cogs: "",
  wages: "",
  rent: "",
  utilities: "",
  depreciation: "",
  professional: "",
  advertising: "",
  other: "",
});

export const blankProp = (): PropRow => ({
  addr: "",
  type: "residential",
  usage: "rented",
  months: "12",
  rent: "",
  gross: "",
  joint: "no",
  share: "100",
  maintenance: "",
  insurance: "",
  mortgage: "",
  mgmt: "",
  other: "",
});

function provinceFromDistrict(district?: string): string {
  const map: Record<string, string> = {
    Colombo: "western",
    Gampaha: "western",
    Kalutara: "western",
    Kandy: "central",
    Matale: "central",
    "Nuwara Eliya": "central",
    Galle: "southern",
    Matara: "southern",
    Hambantota: "southern",
    Jaffna: "northern",
    Kilinochchi: "northern",
    Mannar: "northern",
    Mullaitivu: "northern",
    Vavuniya: "northern",
    Batticaloa: "eastern",
    Ampara: "eastern",
    Trincomalee: "eastern",
    Kurunegala: "north-western",
    Puttalam: "north-western",
    Anuradhapura: "north-central",
    Polonnaruwa: "north-central",
    Badulla: "uva",
    Monaragala: "uva",
    Ratnapura: "sabaragamuwa",
    Kegalle: "sabaragamuwa",
  };
  return map[district ?? ""] ?? "western";
}

function nationalityToCode(nationality?: string | null): string {
  if (!nationality) return "lk";
  const lower = nationality.toLowerCase();
  if (lower.includes("dual")) return "dual";
  if (lower.includes("foreign")) return "foreign";
  return "lk";
}

function taxYearForUi(taxYear?: string): string {
  if (!taxYear) return "";
  if (taxYear.includes("-")) return taxYear;
  const match = /^(\d{4})_(\d{2})$/.exec(taxYear);
  if (match) {
    const endYear = `${match[1].slice(0, 2)}${match[2]}`;
    return `${match[1]}-${endYear}`;
  }
  if (/^\d{4}$/.test(taxYear)) {
    const start = Number(taxYear);
    return `${start}-${start + 1}`;
  }
  return taxYear;
}

function hasPositiveAmount(value?: string | null): boolean {
  return value != null && value !== "" && Number(value) > 0;
}

function blankSection1(): Section1Detail {
  return {
    fullName: "",
    preferredName: "",
    nic: "",
    tin: "",
    dob: "",
    gender: "",
    nationality: "lk",
    residency: "resident",
    filingBasis: "individual",
    marital: "single",
    dependants: "0",
    taxYear: "",
    email: "",
    phone: "",
    altPhone: "",
    addr1: "",
    addr2: "",
    city: "",
    district: "",
    province: "western",
    postal: "",
    spouseName: "",
    spouseNic: "",
    spouseTin: "",
    spouseEmployer: "",
    agentName: "",
    agentTin: "",
    agentFirm: "",
    agentPhone: "",
    agentEmail: "",
    passport: "",
    hasSpouse: false,
    hasAgent: false,
  };
}

function blankSection2(): Section2Detail {
  return {
    employers: [blankEmployer()],
    hasDirector: false,
    directorFees: "",
    companyName: "",
    directorTin: "",
    hasGratuity: false,
    gratuityAmount: "",
    gratuityYears: "",
    gratuityType: "",
    hasSeverance: false,
    severanceAmount: "",
    severanceReason: "",
    hasCommission: false,
    commissionAmount: "",
    commissionPayer: "",
    hasPension: false,
    pensionAmount: "",
    pensionPayer: "",
    pensionType: "",
    hasGifts: false,
    giftAmount: "",
    giftDescription: "",
  };
}

function blankSection3(): Section3Detail {
  return {
    fds: [],
    divs: [],
    hasSavings: false,
    savingsInterest: "",
    savingsWht: "",
    hasGovSec: false,
    govTbill: "",
    govTbond: "",
    govInterest: "",
    govWht: "",
    hasUnitTrust: false,
    unitTrustFund: "",
    unitTrustDistribution: "",
    unitTrustWht: "",
    hasCSE: false,
    cseProceeds: "",
    cseCost: "",
    cseGain: "",
    hasREIT: false,
    reitFund: "",
    reitIncome: "",
  };
}

function blankSection4(): Section4Detail {
  return {
    businesses: [blankBiz()],
    hasFreelance: false,
    freelancePlatform: "",
    freelanceCurrency: "usd",
    freelanceRevenue: "",
    freelanceRate: "",
    freelanceLkr: "",
    freelanceExpenses: "",
    freelanceCommissions: "",
    hasAgri: false,
    agriCrop: "",
    agriRevenue: "",
    agriExpenses: "",
    hasProfessional: false,
    professionalPractice: "",
    professionalRevenue: "",
    professionalExpenses: "",
  };
}

function blankSection5(): Section5Detail {
  return {
    properties: [],
    hasDisposal: false,
    disposalAddr: "",
    disposalAcquired: "",
    disposalDisposed: "",
    disposalCost: "",
    disposalProceeds: "",
    disposalExpenses: "",
    hasLand: false,
    landAddr: "",
    landType: "",
    landRevenue: "",
  };
}

function blankSection6(): Section6Detail {
  return {
    hasLife: false,
    lifePremium: "",
    lifeInsurer: "",
    lifePolicy: "",
    hasMedical: false,
    medicalPremium: "",
    medicalInsurer: "",
    hasCharitable: false,
    charitablePresident: "",
    charitableApproved: "",
    charitableReligious: "",
    charitableOther: "",
    hasEducation: false,
    educationSchool: "",
    educationFees: "",
    educationChildren: "",
    hasPension: false,
    pensionFund: "",
    pensionType: "",
    pensionAmount: "",
    hasMortgage: false,
    mortgageBank: "",
    mortgageAccount: "",
    mortgageInterest: "",
    hasRD: false,
    rdAmount: "",
    rdDescription: "",
    hasDisability: false,
    disabilityCategory: "",
    disabilityAmount: "",
  };
}

function blankSection7(): Section7Detail {
  return {
    hasForEmp: false,
    forEmpEmployer: "",
    forEmpCountry: "",
    forEmpCurrency: "usd",
    forEmpFgross: "",
    forEmpRate: "",
    forEmpLkr: "",
    forEmpFtax: "",
    forEmpDta: "unsure",
    hasForBiz: false,
    forBizDescription: "",
    forBizCountry: "",
    forBizRevenue: "",
    forBizFtax: "",
    hasForDiv: false,
    forDivCompany: "",
    forDivCountry: "",
    forDivTotal: "",
    forDivFtax: "",
    hasForProp: false,
    forPropCountry: "",
    forPropAddr: "",
    forPropType: "",
    forPropRental: "",
    forPropFtax: "",
    hasDTA: false,
    dtaCountry: "",
    dtaFtaxPaid: "",
    dtaCreditClaimed: "",
  };
}

function blankSection8(): Section8Detail {
  return { agreed: false };
}

/** Empty 8-section shell — no demo placeholders. */
export function emptyTaxReturnDetail(): TaxReturnDetail {
  return {
    section1: blankSection1(),
    section2: blankSection2(),
    section3: blankSection3(),
    section4: blankSection4(),
    section5: blankSection5(),
    section6: blankSection6(),
    section7: blankSection7(),
    section8: blankSection8(),
  };
}

/**
 * Pre-fill Tax Return Profile from auditor-created ORM scalars (Bucket A only).
 * Recommendation-only scalars (expenses, debt, risk, income_sources, etc.) are
 * intentionally omitted — they stay on the profile for the ranker.
 */
export function createDefaultTaxReturnDetail(profile?: FinancialProfile): TaxReturnDetail {
  const detail = emptyTaxReturnDetail();
  if (!profile) {
    return detail;
  }

  const fullName = profile.full_name ?? "";
  const district = profile.district ?? "";
  const lifePremium = profile.life_insurance_premium_annual ?? "";
  const homeLoanInterest = profile.home_loan_interest_annual ?? "";
  const donations = profile.donations_annual ?? "";
  const grossAnnual = profile.gross_monthly_income
    ? String(Math.round(Number(profile.gross_monthly_income) * 12))
    : "";

  detail.section1 = {
    ...detail.section1,
    fullName,
    preferredName: fullName.split(/\s+/)[0] ?? "",
    dob: profile.date_of_birth ?? "",
    gender: profile.gender ?? "",
    nationality: nationalityToCode(profile.nationality),
    residency:
      profile.residency_status === "non_resident"
        ? "non-resident"
        : profile.residency_status === "dual"
          ? "dual"
          : "resident",
    marital: profile.marital_status ?? "single",
    dependants: profile.dependents != null ? String(profile.dependents) : "0",
    taxYear: taxYearForUi(profile.tax_year),
    district,
    province: provinceFromDistrict(district),
    hasSpouse: profile.marital_status === "married",
  };

  if (grossAnnual || profile.annual_bonus_lkr || profile.epf_balance || profile.etf_balance) {
    detail.section2 = {
      ...detail.section2,
      employers: [
        {
          ...blankEmployer(),
          gross: grossAnnual,
          bonus: profile.annual_bonus_lkr ?? "",
          epf: profile.epf_balance ?? "",
          etf: profile.etf_balance ?? "",
        },
      ],
    };
  }

  detail.section6 = {
    ...detail.section6,
    hasLife: hasPositiveAmount(lifePremium),
    lifePremium,
    hasMedical: profile.health_insurance ?? false,
    hasCharitable: hasPositiveAmount(donations),
    charitableApproved: donations,
    hasMortgage: hasPositiveAmount(homeLoanInterest),
    mortgageInterest: homeLoanInterest,
  };

  return detail;
}
