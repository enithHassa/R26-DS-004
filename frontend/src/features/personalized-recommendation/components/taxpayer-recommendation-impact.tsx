import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";

import { simulateImpact } from "../api/impact";
import { TAXPAYER_IMPACT_HORIZON_YEARS, TAXPAYER_IMPACT_N_PATHS } from "../constants/taxpayer-impact";
import { TaxpayerImpactSimpleView } from "./taxpayer-impact-simple";

type Props = {
  profileId: string;
  strategyCode: string;
  strategyName: string;
};

export function TaxpayerRecommendationImpact({ profileId, strategyCode, strategyName }: Props) {
  const [open, setOpen] = useState(false);

  const impactQuery = useQuery({
    queryKey: ["taxpayer-rec-impact", profileId, strategyCode],
    queryFn: () =>
      simulateImpact({
        profile_id: profileId,
        strategy_code: strategyCode,
        horizon_years: TAXPAYER_IMPACT_HORIZON_YEARS,
        n_paths: TAXPAYER_IMPACT_N_PATHS,
        random_seed: 42,
      }),
    enabled: open && !!profileId && !!strategyCode,
  });

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-md border border-[var(--uv-accent)]/40 bg-[var(--uv-accent)]/10 px-3 py-1.5 text-xs font-medium text-[var(--uv-accent)] transition-colors hover:bg-[var(--uv-accent)]/20"
      >
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        {open ? "Hide money picture" : "See what this could mean for your money"}
      </button>

      {open && (
        <div className="mt-4 space-y-4 rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)]/80 p-4">
          {impactQuery.isLoading && (
            <p className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Building a simple picture for you…
            </p>
          )}
          {impactQuery.isError && (
            <p className="text-sm text-red-400">{(impactQuery.error as Error).message}</p>
          )}
          {impactQuery.data && (
            <TaxpayerImpactSimpleView
              result={impactQuery.data}
              strategyName={strategyName}
              userView
            />
          )}
        </div>
      )}
    </div>
  );
}
