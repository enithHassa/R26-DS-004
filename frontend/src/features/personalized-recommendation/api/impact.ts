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

/** Multi-strategy bundle — merges reliefs and simulates adoption together. */
export async function simulateCombinedImpact(
  payload: Omit<ImpactSimulationRequest, "strategy_code" | "strategy_id"> & {
    strategy_codes: string[];
  },
): Promise<ImpactSimulationResponse> {
  if (payload.strategy_codes.length < 2) {
    throw new Error("Select at least two strategies for a combined simulation.");
  }

  const { data } = await recommendationApi.post<ImpactSimulationResponse>(
    "/impact/simulate",
    payload,
  );

  if (!data.strategy_path?.length) {
    throw new Error(
      "Combined impact is unavailable. Restart the recommendation service on port 8003 so it picks up the latest API, then try again.",
    );
  }

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
