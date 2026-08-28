import { useQuery } from "@tanstack/react-query";
import { TrendingUp } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { generateRecommendations } from "../api/recommendations";
import { simulateImpact } from "../api/impact";
import { recommendationCodeToCatalog } from "../constants/strategies";
import { ImpactCharts } from "./impact-charts";
import { ImpactSummaryCards } from "./impact-summary-cards";

type TaxpayerImpactPanelProps = {
  profileId: string;
};

export function TaxpayerImpactPanel({ profileId }: TaxpayerImpactPanelProps) {
  const recommendationsQuery = useQuery({
    queryKey: ["taxpayer-impact-recommendations", profileId],
    queryFn: () => generateRecommendations({ profile_id: profileId, top_k: 5 }),
    enabled: !!profileId,
    refetchOnMount: "always",
  });

  const topStrategyCode = recommendationsQuery.data?.items[0]
    ? recommendationCodeToCatalog(recommendationsQuery.data.items[0].strategy.code)
    : null;

  const impactQuery = useQuery({
    queryKey: ["taxpayer-impact", profileId, topStrategyCode],
    queryFn: () =>
      simulateImpact({
        profile_id: profileId,
        strategy_code: topStrategyCode,
        horizon_years: 10,
        n_paths: 1000,
        random_seed: 42,
      }),
    enabled: !!profileId && !!topStrategyCode,
  });

  return (
    <Card className="border-[var(--uv-border)] bg-[var(--uv-bg-card)]">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <TrendingUp className="h-5 w-5 text-[var(--uv-accent)]" />
          What this could mean for you
        </CardTitle>
        <CardDescription className="text-[var(--uv-text-muted)]">
          {topStrategyCode
            ? "A plain-language look at where you could stand in 10 years if you follow our top recommendation."
            : "A plain-language look at where you could stand in 10 years."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {recommendationsQuery.isLoading && (
          <p className="text-sm text-[var(--uv-text-muted)]">Loading recommendations…</p>
        )}
        {impactQuery.isLoading && (
          <p className="text-sm text-[var(--uv-text-muted)]">Running your projection…</p>
        )}
        {impactQuery.isError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
            {(impactQuery.error as Error).message}
          </div>
        )}
        {impactQuery.data && (
          <>
            <ImpactSummaryCards
              summary={impactQuery.data.summary}
              hasStrategy={Boolean(impactQuery.data.strategy_path)}
            />
            <div className="mt-6">
              <ImpactCharts result={impactQuery.data} />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
