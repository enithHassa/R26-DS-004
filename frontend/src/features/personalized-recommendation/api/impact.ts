import { recommendationApi } from "../api";
import type {
  ImpactSimulationRequest,
  ImpactSimulationResponse,
  StrategyComparisonRequest,
} from "../types";

export async function simulateImpact(
  payload: ImpactSimulationRequest,
): Promise<ImpactSimulationResponse> {
  const { data } = await recommendationApi.post<ImpactSimulationResponse>(
    "/impact/simulate",
    payload,
  );
  return data;
}

export async function compareImpactStrategies(
  payload: StrategyComparisonRequest,
): Promise<ImpactSimulationResponse[]> {
  const { data } = await recommendationApi.post<ImpactSimulationResponse[]>(
    "/impact/compare",
    payload,
  );
  return data;
}
