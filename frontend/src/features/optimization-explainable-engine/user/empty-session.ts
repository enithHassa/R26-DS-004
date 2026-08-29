import {
  adjacentCompareYa,
  hydrateIncomeAmounts,
  EMPTY_INCOME_FORM,
  type InterviewSession,
} from "../types";
import { emptyAmountsForCard, incomeCatalogCard } from "../income-catalog";

/** Taxpayer session with zero demo income — never seed auditor demo salary. */
export function createEmptyTaxpayerSession(assessmentYear = "2025_26"): InterviewSession {
  return {
    assessmentYear,
    compareYear: adjacentCompareYa(assessmentYear),
    excludeSourceDocId: null,
    selectedCompareGroupId: "personal_relief",
    income: hydrateIncomeAmounts({
      taxpayerName: "",
      tin: "",
      form: { ...EMPTY_INCOME_FORM },
      employmentMode: "components",
      businessMode: "net",
      investmentMode: "components",
      otherMode: "components",
      employmentAmounts: emptyAmountsForCard(incomeCatalogCard("employment")),
      businessAmounts: emptyAmountsForCard(incomeCatalogCard("business")),
      investmentAmounts: emptyAmountsForCard(incomeCatalogCard("investment")),
      otherAmounts: emptyAmountsForCard(incomeCatalogCard("other_income")),
      otherCustomRows: [],
      interestSchedule: [],
      apitAlreadyPaid: "0",
      hasTerminalBenefits: false,
      terminalBenefits: [],
    }),
    reliefAnswers: [],
    evidenceChecks: {},
  };
}
