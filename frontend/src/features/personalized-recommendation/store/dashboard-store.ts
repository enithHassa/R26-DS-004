import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ImpactScenario, RecommendationResponse } from "../types";

export type ImpactScenarioState = {
  horizonYears: number;
  nPaths: number;
  salaryGrowthMean: number;
  inflationMean: number;
  investmentReturnMean: number;
  adoptionSuccessProb: number;
};

type DashboardState = {
  activeProfileId: string | null;
  lastRecommendations: RecommendationResponse | null;
  impactScenario: ImpactScenarioState;
  setActiveProfileId: (id: string | null) => void;
  setLastRecommendations: (data: RecommendationResponse | null) => void;
  setImpactScenario: (partial: Partial<ImpactScenarioState>) => void;
  toImpactScenarioPayload: (withStrategy: boolean) => ImpactScenario;
};

const defaultScenario: ImpactScenarioState = {
  horizonYears: 10,
  nPaths: 1000,
  salaryGrowthMean: 0.06,
  inflationMean: 0.06,
  investmentReturnMean: 0.08,
  adoptionSuccessProb: 1,
};

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set, get) => ({
      activeProfileId: null,
      lastRecommendations: null,
      impactScenario: defaultScenario,
      setActiveProfileId: (id) => set({ activeProfileId: id }),
      setLastRecommendations: (data) => set({ lastRecommendations: data }),
      setImpactScenario: (partial) =>
        set((s) => ({ impactScenario: { ...s.impactScenario, ...partial } })),
      toImpactScenarioPayload: (withStrategy) => {
        const sc = get().impactScenario;
        return {
          name: withStrategy ? "adopt_strategy" : "baseline",
          salary_growth_mean: sc.salaryGrowthMean,
          inflation_mean: sc.inflationMean,
          investment_return_mean: sc.investmentReturnMean,
          adoption_success_prob: withStrategy ? sc.adoptionSuccessProb : 1,
        };
      },
    }),
    { name: "comp3-dashboard" },
  ),
);
