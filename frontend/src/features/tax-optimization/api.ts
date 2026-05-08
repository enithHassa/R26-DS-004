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
  TaxOptBSearchStrategiesResponseV1,
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
