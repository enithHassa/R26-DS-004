import { createApiClient } from "@/lib/api-client";

import type {
  ComplianceCheckRequest,
  ComplianceFromTransactionsRequest,
  ComplianceResult,
  TaxOptBCompareFromFinancialInputsRequestV1,
  TaxOptBCompareStrategiesRequestV1,
  TaxOptBCompareStrategiesResponseV1,
  TaxOptBComplianceFromFinancialInputsRequestV1,
  TaxOptBComputeTaxResponseV1,
  TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
  TaxOptBSearchStrategiesMlRankRequestV1,
  TaxOptBSearchStrategiesResponseV1,
  TaxOptBRfTaxPredictRequestV1,
  TaxOptBRfTaxPredictResponseV1,
  MLRankedStrategyV1,
  MLRankResponseV1,
} from "./types";

/** All requests go through the API gateway (see `VITE_API_BASE_URL`). */
export const taxOptimizationApi = createApiClient("/api/v1/optimization");

export async function postComplianceCheck(
  body: ComplianceCheckRequest,
): Promise<ComplianceResult> {
  const { data } = await taxOptimizationApi.post<ComplianceResult>("/compliance/check", body);
  return data;
}

export async function postComplianceCheckFromTransactions(
  body: ComplianceFromTransactionsRequest,
): Promise<ComplianceResult> {
  const { data } = await taxOptimizationApi.post<ComplianceResult>(
    "/compliance/check-from-transactions",
    body,
  );
  return data;
}

export async function postComplianceCheckFromFinancialInputs(
  body: TaxOptBComplianceFromFinancialInputsRequestV1,
): Promise<ComplianceResult> {
  const { data } = await taxOptimizationApi.post<ComplianceResult>(
    "/compliance/check-from-financial-inputs",
    body,
  );
  return data;
}

export async function postComputeTax(body: ComplianceCheckRequest): Promise<TaxOptBComputeTaxResponseV1> {
  const { data } = await taxOptimizationApi.post<TaxOptBComputeTaxResponseV1>(
    "/compliance/compute-tax",
    body,
  );
  return data;
}

export async function postComputeTaxFromFinancialInputs(
  body: TaxOptBComplianceFromFinancialInputsRequestV1,
): Promise<TaxOptBComputeTaxResponseV1> {
  const { data } = await taxOptimizationApi.post<TaxOptBComputeTaxResponseV1>(
    "/compliance/compute-tax-from-financial-inputs",
    body,
  );
  return data;
}

export async function postCompareStrategies(
  body: TaxOptBCompareStrategiesRequestV1,
): Promise<TaxOptBCompareStrategiesResponseV1> {
  const { data } = await taxOptimizationApi.post<TaxOptBCompareStrategiesResponseV1>(
    "/compliance/compare-strategies",
    body,
  );
  return data;
}

export async function postCompareStrategiesFromFinancialInputs(
  body: TaxOptBCompareFromFinancialInputsRequestV1,
): Promise<TaxOptBCompareStrategiesResponseV1> {
  const { data } = await taxOptimizationApi.post<TaxOptBCompareStrategiesResponseV1>(
    "/compliance/compare-strategies-from-financial-inputs",
    body,
  );
  return data;
}

export async function postSearchStrategiesFromFinancialInputs(
  body: TaxOptBSearchStrategiesFromFinancialInputsRequestV1,
): Promise<TaxOptBSearchStrategiesResponseV1> {
  const { data } = await taxOptimizationApi.post<TaxOptBSearchStrategiesResponseV1>(
    "/compliance/search-strategies-from-financial-inputs",
    body,
  );
  return data;
}

/** Function 3 — ML-assisted ranking over the legal candidate set only. */
export async function postSearchStrategiesMlRank(
  body: TaxOptBSearchStrategiesMlRankRequestV1,
): Promise<TaxOptBSearchStrategiesResponseV1> {
  const { data } = await taxOptimizationApi.post<TaxOptBSearchStrategiesResponseV1>(
    "/strategies/ml-rank",
    body,
    /** Model load + scoring over large candidate sets often exceeds the default 30s client limit. */
    { timeout: 180_000 },
  );
  return data;
}

/** Phase 2.D — ML ranking endpoint: Rank 20 strategies by utility score with legal explanations. */
export async function postMlRankStrategies(
  taxYear: string,
  salary: number,
  rentalIncome: number,
  interestIncome: number,
  businessIncome: number,
  lifeInsurancePremium: number,
  healthInsurancePremium: number,
  homeLoanInterest: number,
  rentRelief: number,
  charitableDonations: number,
  retirementContribution: number,
  complexityTolerance: number,
  auditRiskTolerance: number,
  timeAvailable: number,
): Promise<MLRankResponseV1> {
  const body = {
    tax_year: taxYear,
    salary,
    rental_income: rentalIncome,
    interest_income: interestIncome,
    business_income: businessIncome,
    life_insurance_premium: lifeInsurancePremium,
    health_insurance_premium: healthInsurancePremium,
    home_loan_interest: homeLoanInterest,
    rent_relief: rentRelief,
    charitable_donations: charitableDonations,
    retirement_contribution: retirementContribution,
    complexity_tolerance: complexityTolerance,
    audit_risk_tolerance: auditRiskTolerance,
    time_available: timeAvailable,
  };

  const { data } = await taxOptimizationApi.post<MLRankResponseV1>(
    "/compliance/ml-rank-strategies",
    body,
    { timeout: 60_000 }, // 60s timeout for ML ranking
  );
  return data;
}

/** 2025/26 filing calculator — Random Forest tax estimate with SHAP reasoning. */
export async function postRfTaxPredict(
  body: TaxOptBRfTaxPredictRequestV1,
): Promise<TaxOptBRfTaxPredictResponseV1> {
  const { data } = await taxOptimizationApi.post<TaxOptBRfTaxPredictResponseV1>(
    "/tax-filing/rf-predict",
    body,
  );
  return data;
}
