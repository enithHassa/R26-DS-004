export interface EmployerRow {
  name: string;
  tin: string;
  role: string;
  from: string;
  to: string;
  current: string;
  gross: string;
  apit: string;
  epf: string;
  etf: string;
  bonus: string;
  allowances: string;
  noncash: string;
  overtime: string;
}

export interface FdRow {
  bank: string;
  accNo: string;
  maturity: string;
  principal: string;
  interest: string;
  wht: string;
  type: string;
}

export interface DivRow {
  company: string;
  shares: string;
  dps: string;
  total: string;
  wht: string;
  resident: string;
}

export interface BizRow {
  name: string;
  regNo: string;
  type: string;
  nature: string;
  start: string;
  revenue: string;
  cogs: string;
  wages: string;
  rent: string;
  utilities: string;
  depreciation: string;
  professional: string;
  advertising: string;
  other: string;
}

export interface PropRow {
  addr: string;
  type: string;
  usage: string;
  months: string;
  rent: string;
  gross: string;
  joint: string;
  share: string;
  maintenance: string;
  insurance: string;
  mortgage: string;
  mgmt: string;
  other: string;
}

export interface Section1Detail {
  fullName: string;
  preferredName: string;
  nic: string;
  tin: string;
  dob: string;
  gender: string;
  nationality: string;
  residency: string;
  filingBasis: string;
  marital: string;
  dependants: string;
  taxYear: string;
  email: string;
  phone: string;
  altPhone: string;
  addr1: string;
  addr2: string;
  city: string;
  district: string;
  province: string;
  postal: string;
  spouseName: string;
  spouseNic: string;
  spouseTin: string;
  spouseEmployer: string;
  agentName: string;
  agentTin: string;
  agentFirm: string;
  agentPhone: string;
  agentEmail: string;
  passport: string;
  hasSpouse: boolean;
  hasAgent: boolean;
}

export interface Section2Detail {
  employers: EmployerRow[];
  hasDirector: boolean;
  directorFees: string;
  companyName: string;
  directorTin: string;
  hasGratuity: boolean;
  gratuityAmount: string;
  gratuityYears: string;
  gratuityType: string;
  hasSeverance: boolean;
  severanceAmount: string;
  severanceReason: string;
  hasCommission: boolean;
  commissionAmount: string;
  commissionPayer: string;
  hasPension: boolean;
  pensionAmount: string;
  pensionPayer: string;
  pensionType: string;
  hasGifts: boolean;
  giftAmount: string;
  giftDescription: string;
}

export interface Section3Detail {
  fds: FdRow[];
  divs: DivRow[];
  hasSavings: boolean;
  savingsInterest: string;
  savingsWht: string;
  hasGovSec: boolean;
  govTbill: string;
  govTbond: string;
  govInterest: string;
  govWht: string;
  hasUnitTrust: boolean;
  unitTrustFund: string;
  unitTrustDistribution: string;
  unitTrustWht: string;
  hasCSE: boolean;
  cseProceeds: string;
  cseCost: string;
  cseGain: string;
  hasREIT: boolean;
  reitFund: string;
  reitIncome: string;
}

export interface Section4Detail {
  businesses: BizRow[];
  hasFreelance: boolean;
  freelancePlatform: string;
  freelanceCurrency: string;
  freelanceRevenue: string;
  freelanceRate: string;
  freelanceLkr: string;
  freelanceExpenses: string;
  freelanceCommissions: string;
  hasAgri: boolean;
  agriCrop: string;
  agriRevenue: string;
  agriExpenses: string;
  hasProfessional: boolean;
  professionalPractice: string;
  professionalRevenue: string;
  professionalExpenses: string;
}

export interface Section5Detail {
  properties: PropRow[];
  hasDisposal: boolean;
  disposalAddr: string;
  disposalAcquired: string;
  disposalDisposed: string;
  disposalCost: string;
  disposalProceeds: string;
  disposalExpenses: string;
  hasLand: boolean;
  landAddr: string;
  landType: string;
  landRevenue: string;
}

export interface Section6Detail {
  hasLife: boolean;
  lifePremium: string;
  lifeInsurer: string;
  lifePolicy: string;
  hasMedical: boolean;
  medicalPremium: string;
  medicalInsurer: string;
  hasCharitable: boolean;
  charitablePresident: string;
  charitableApproved: string;
  charitableReligious: string;
  charitableOther: string;
  hasEducation: boolean;
  educationSchool: string;
  educationFees: string;
  educationChildren: string;
  hasPension: boolean;
  pensionFund: string;
  pensionType: string;
  pensionAmount: string;
  hasMortgage: boolean;
  mortgageBank: string;
  mortgageAccount: string;
  mortgageInterest: string;
  hasRD: boolean;
  rdAmount: string;
  rdDescription: string;
  hasDisability: boolean;
  disabilityCategory: string;
  disabilityAmount: string;
}

export interface Section7Detail {
  hasForEmp: boolean;
  forEmpEmployer: string;
  forEmpCountry: string;
  forEmpCurrency: string;
  forEmpFgross: string;
  forEmpRate: string;
  forEmpLkr: string;
  forEmpFtax: string;
  forEmpDta: string;
  hasForBiz: boolean;
  forBizDescription: string;
  forBizCountry: string;
  forBizRevenue: string;
  forBizFtax: string;
  hasForDiv: boolean;
  forDivCompany: string;
  forDivCountry: string;
  forDivTotal: string;
  forDivFtax: string;
  hasForProp: boolean;
  forPropCountry: string;
  forPropAddr: string;
  forPropType: string;
  forPropRental: string;
  forPropFtax: string;
  hasDTA: boolean;
  dtaCountry: string;
  dtaFtaxPaid: string;
  dtaCreditClaimed: string;
}

export interface Section8Detail {
  agreed: boolean;
}

export interface TaxReturnDetail {
  section1: Section1Detail;
  section2: Section2Detail;
  section3: Section3Detail;
  section4: Section4Detail;
  section5: Section5Detail;
  section6: Section6Detail;
  section7: Section7Detail;
  section8: Section8Detail;
}
