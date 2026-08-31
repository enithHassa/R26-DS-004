import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { getProfileFeatures } from "../api/profiles";
import { EligibilityTraceCard } from "../components/eligibility-trace-card";
import { ExplainPanel } from "../components/explain-panel";
import { FeasibilityCard } from "../components/feasibility-card";
import { CATALOG_STRATEGIES, recommendationCodeToCatalog } from "../constants/strategies";
import { useDashboardStore, useActiveProfileId } from "../store/dashboard-store";

export function StrategyDetailPage() {
  const { strategyId } = useParams();
  const [searchParams] = useSearchParams();
  const activeProfileId = useActiveProfileId();
  const lastRecommendations = useDashboardStore((s) => s.lastRecommendations);
  const profileId = searchParams.get("profile") ?? activeProfileId ?? "";

  const catalogCode = strategyId ? recommendationCodeToCatalog(strategyId) : "";
  const meta = CATALOG_STRATEGIES.find(
    (s) => s.code === catalogCode || catalogCode.includes(s.code.split("_")[0]),
  );

  const recItem = lastRecommendations?.items.find(
    (i) => recommendationCodeToCatalog(i.strategy.code) === catalogCode,
  );

  const featuresQuery = useQuery({
    queryKey: ["profile-features", profileId, "strategy-detail"],
    queryFn: () => getProfileFeatures(profileId),
    enabled: Boolean(profileId),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Strategy detail</h1>
        <p className="text-muted-foreground">
          SHAP ranking drivers, feasibility breakdown, and eligibility evidence trace (FR10, FR2).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{meta?.label ?? strategyId}</CardTitle>
          <CardDescription className="font-mono text-xs">{catalogCode || strategyId}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Link
            to={`/impact/${encodeURIComponent(catalogCode)}${profileId ? `?profile=${profileId}` : ""}`}
            className="text-sm font-medium text-primary underline"
          >
            Monte Carlo impact simulation →
          </Link>
          <Link
            to={`/compare${profileId ? `?profile=${profileId}` : ""}`}
            className="text-sm font-medium text-muted-foreground underline hover:text-foreground"
          >
            Compare with other strategies
          </Link>
        </CardContent>
      </Card>

      <FeasibilityCard item={recItem} />

      <EligibilityTraceCard
        strategyCode={catalogCode}
        features={featuresQuery.data}
        isLoading={featuresQuery.isFetching}
      />

      {profileId && catalogCode ? (
        <ExplainPanel
          profileId={profileId}
          strategyCode={catalogCode}
          strategyLabel={meta?.label}
        />
      ) : (
        <Card>
          <CardContent className="pt-6 text-sm text-muted-foreground">
            Select a profile on Strategy recommendations or add{" "}
            <code className="text-xs">?profile=&lt;uuid&gt;</code> to load SHAP explanations.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
