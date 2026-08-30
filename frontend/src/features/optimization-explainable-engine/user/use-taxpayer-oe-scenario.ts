import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { ReliefAnswer } from "../types";
import {
  computeTaxpayerScenario,
  type TaxpayerComputeResult,
} from "./compute-scenario";
import {
  loadTaxpayerScenario,
  type TaxpayerOeScenario,
} from "./load-taxpayer-scenario";

export function useTaxpayerOeScenario(profileId: string) {
  const queryClient = useQueryClient();
  const [assessmentYear, setAssessmentYear] = useState<string | null>(null);
  const [localClaims, setLocalClaims] = useState<ReliefAnswer[] | null>(null);
  const [sessionOverride, setSessionOverride] = useState<
    TaxpayerOeScenario["session"] | null
  >(null);

  const scenarioQuery = useQuery({
    queryKey: ["taxwise-oe", "scenario", profileId, assessmentYear],
    queryFn: () => loadTaxpayerScenario(profileId, assessmentYear),
    enabled: Boolean(profileId),
    refetchOnMount: "always",
    placeholderData: (previous) => previous,
    retry: 1,
  });

  useEffect(() => {
    setLocalClaims(null);
    setSessionOverride(null);
  }, [profileId, assessmentYear]);

  useEffect(() => {
    if (scenarioQuery.data && !assessmentYear) {
      setAssessmentYear(scenarioQuery.data.assessmentYear);
    }
  }, [scenarioQuery.data, assessmentYear]);

  const scenario = scenarioQuery.data
    ? {
        ...scenarioQuery.data,
        session: sessionOverride ?? scenarioQuery.data.session,
        suggestedClaims: localClaims ?? scenarioQuery.data.suggestedClaims,
      }
    : null;

  const claims = scenario?.session.reliefAnswers ?? localClaims ?? [];

  const exploreQuery = useQuery({
    queryKey: [
      "taxwise-oe",
      "explore",
      profileId,
      scenario?.assessmentYear,
      scenario?.session.income,
      claims,
    ],
    queryFn: () => computeTaxpayerScenario(scenario!.session, claims),
    enabled: Boolean(scenario && scenario.hasProfileIncome),
    retry: false,
  });

  const selectYear = useCallback((ya: string) => {
    setAssessmentYear(ya);
    setSessionOverride(null);
    setLocalClaims(null);
  }, []);

  const patchClaims = useCallback((next: ReliefAnswer[]) => {
    setLocalClaims(next);
    setSessionOverride((prev) => {
      const base = prev ?? scenarioQuery.data?.session;
      if (!base) return prev;
      return { ...base, reliefAnswers: next };
    });
  }, [scenarioQuery.data?.session]);

  const patchIncomeSession = useCallback(
    (session: TaxpayerOeScenario["session"]) => {
      setSessionOverride(session);
    },
    [],
  );

  const reload = useCallback(async () => {
    setSessionOverride(null);
    setLocalClaims(null);
    await queryClient.invalidateQueries({ queryKey: ["taxwise-oe"] });
    await scenarioQuery.refetch();
  }, [profileId, queryClient, scenarioQuery]);

  return {
    scenario,
    isLoading: scenarioQuery.isLoading && !scenario,
    isError: scenarioQuery.isError && !scenario,
    error: scenarioQuery.error,
    explore: exploreQuery.data as TaxpayerComputeResult | undefined,
    exploreLoading: exploreQuery.isFetching,
    exploreError: exploreQuery.isError,
    selectYear,
    patchClaims,
    patchIncomeSession,
    reload,
    assessmentYear: scenario?.assessmentYear ?? assessmentYear,
  };
}
