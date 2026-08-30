import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, TrendingUp } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import { generateRecommendations } from "../api/recommendations";
import { simulateImpact } from "../api/impact";
import { recommendationCodeToCatalog } from "../constants/strategies";
import { TAXPAYER_IMPACT_HORIZON_YEARS, TAXPAYER_IMPACT_N_PATHS } from "../constants/taxpayer-impact";
import { TaxpayerImpactSimpleView } from "./taxpayer-impact-simple";

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

  const items = recommendationsQuery.data?.items ?? [];
  const [selectedIndex, setSelectedIndex] = useState(0);
  const selected = items[selectedIndex];
  const strategyCode = selected ? recommendationCodeToCatalog(selected.strategy.code) : null;

  const impactQuery = useQuery({
    queryKey: ["taxpayer-impact", profileId, strategyCode],
    queryFn: () =>
      simulateImpact({
        profile_id: profileId,
        strategy_code: strategyCode,
        horizon_years: TAXPAYER_IMPACT_HORIZON_YEARS,
        n_paths: TAXPAYER_IMPACT_N_PATHS,
        random_seed: 42,
      }),
    enabled: !!profileId && !!strategyCode,
  });

  return (
    <Card className="border-[var(--uv-border)] bg-[var(--uv-bg-card)] text-[var(--uv-text)]">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg text-[var(--uv-text)]">
          <TrendingUp className="h-5 w-5 text-[var(--uv-accent)]" />
          What this could mean for you
        </CardTitle>
        <CardDescription className="text-[var(--uv-text-muted)]">
          Pick any recommendation below — we show a simple {TAXPAYER_IMPACT_HORIZON_YEARS}-year picture
          with easy charts (no tax jargon needed).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {recommendationsQuery.isLoading && (
          <p className="text-sm text-[var(--uv-text-muted)]">Loading your recommendations…</p>
        )}

        {items.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {items.map((item, index) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setSelectedIndex(index)}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-left text-xs font-medium transition-colors",
                  index === selectedIndex
                    ? "border-[var(--uv-accent)] bg-[var(--uv-accent)]/15 text-[var(--uv-accent)]"
                    : "border-[var(--uv-border)] text-[var(--uv-text-muted)] hover:bg-white/5 hover:text-[var(--uv-text)]",
                )}
              >
                #{item.rank} {item.strategy.name}
              </button>
            ))}
          </div>
        )}

        {impactQuery.isLoading && (
          <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Building your picture…
          </p>
        )}
        {impactQuery.isError && (
          <div className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">
            {(impactQuery.error as Error).message}
          </div>
        )}
        {impactQuery.data && selected && (
          <TaxpayerImpactSimpleView
            result={impactQuery.data}
            strategyName={selected.strategy.name}
            userView
          />
        )}
      </CardContent>
    </Card>
  );
}
