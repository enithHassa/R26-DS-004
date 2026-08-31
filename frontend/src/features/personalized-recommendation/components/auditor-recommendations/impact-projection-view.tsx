import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

import { hybridQuery } from "../../api/hybrid";
import { simulateImpact } from "../../api/impact";
import {
  AUDITOR_IMPACT_HORIZON_YEARS,
  AUDITOR_IMPACT_N_PATHS,
} from "../../constants/auditor-impact";
import { recommendationCodeToCatalog } from "../../constants/strategies";
import type { HybridResultItem } from "../../api/hybrid";
import { AuditorImpactDetailSections } from "./auditor-impact-detail-sections";

type Props = {
  profileId: string;
};

function resolveHybridItem(
  items: HybridResultItem[],
  strategyParam: string | undefined,
): HybridResultItem | undefined {
  if (!strategyParam) return items[0];
  return (
    items.find(
      (i) =>
        i.strategy_id === strategyParam ||
        recommendationCodeToCatalog(i.strategy_id) === recommendationCodeToCatalog(strategyParam),
    ) ?? items[0]
  );
}

export function AuditorImpactProjectionView({ profileId }: Props) {
  const { strategyId: routeStrategy } = useParams();
  const [searchParams] = useSearchParams();
  const strategyParam =
    routeStrategy && routeStrategy !== "new" ? routeStrategy : searchParams.get("strategy") ?? undefined;
  const rankParam = Number(searchParams.get("rank") ?? "1");
  const nameParam = searchParams.get("name");

  const hybridQueryResult = useQuery({
    queryKey: ["auditor-impact-hybrid", profileId],
    queryFn: () => hybridQuery({ profile_id: profileId, top_k: 5 }),
    enabled: !!profileId,
  });

  const items = hybridQueryResult.data?.items ?? [];
  const selectedItem = resolveHybridItem(items, strategyParam);
  const strategyCode = selectedItem?.strategy_id ?? strategyParam ?? null;

  const primarySim = useQuery({
    queryKey: ["auditor-impact-primary", profileId, strategyCode],
    queryFn: () =>
      simulateImpact({
        profile_id: profileId,
        strategy_code: strategyCode,
        horizon_years: AUDITOR_IMPACT_HORIZON_YEARS,
        n_paths: AUDITOR_IMPACT_N_PATHS,
        random_seed: 42,
      }),
    enabled: !!profileId && !!strategyCode,
  });

  const strategyName = nameParam ?? selectedItem?.name ?? "Selected strategy";
  const loading = hybridQueryResult.isLoading || primarySim.isLoading;

  if (!strategyCode) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-12 text-center text-sm text-muted-foreground">
          Select a strategy from{" "}
          <Link to="/hybrid" className="font-medium text-primary underline">
            Smart Recommendations
          </Link>{" "}
          and click <strong>View Impact</strong>.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/hybrid"
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Link>
        <div>
          <h2 className="text-xl font-bold tracking-tight">Financial Impact Projection</h2>
          <p className="text-sm text-muted-foreground">Strategy: {strategyName}</p>
        </div>
      </div>

      <AuditorImpactDetailSections
        primaryResult={primarySim.data}
        selectedItem={selectedItem}
        strategyName={strategyName}
        rank={selectedItem?.rank ?? rankParam}
        isLoading={loading}
        error={primarySim.isError ? (primarySim.error as Error).message : null}
      />
    </div>
  );
}
