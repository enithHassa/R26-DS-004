import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutDashboard, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { hybridQuery } from "../api/hybrid";
import { simulateImpact } from "../api/impact";
import { getProfile, getProfileFeatures, getProfileHistory } from "../api/profiles";
import {
  AuditorAdoptionPanel,
  AuditorEvidenceModalHost,
  AuditorImpactPanel,
  AuditorKpiStrip,
  AuditorRecommendationsPanel,
  AuditorTaxpayerCard,
} from "../components/auditor-dashboard-sections";
import { PageHeader } from "../components/page-header";
import { ProfilePicker } from "../components/profile-picker";
import {
  AUDITOR_IMPACT_HORIZON_YEARS,
  AUDITOR_IMPACT_N_PATHS,
} from "../constants/auditor-impact";
import { useActiveProfileId } from "../store/dashboard-store";
import { computeAdoptionEvidence } from "../utils/adoption-evidence";

export function AuditorDashboardPage() {
  const queryClient = useQueryClient();
  const storedProfileId = useActiveProfileId();

  const [profileId, setProfileId] = useState(storedProfileId ?? "");
  const [selectedStrategyId, setSelectedStrategyId] = useState<string | null>(null);
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);

  useEffect(() => {
    if (storedProfileId && storedProfileId !== profileId) {
      setProfileId(storedProfileId);
    }
  }, [storedProfileId, profileId]);

  const profileQuery = useQuery({
    queryKey: ["auditor-dashboard-profile", profileId],
    queryFn: () => getProfile(profileId),
    enabled: !!profileId,
  });

  const featuresQuery = useQuery({
    queryKey: ["auditor-dashboard-features", profileId],
    queryFn: () => getProfileFeatures(profileId),
    enabled: !!profileId,
  });

  const historyQuery = useQuery({
    queryKey: ["auditor-dashboard-history", profileId],
    queryFn: () => getProfileHistory(profileId, 36),
    enabled: !!profileId,
  });

  const hybridMutation = useMutation({
    mutationFn: () => hybridQuery({ profile_id: profileId, top_k: 5 }),
    onSuccess: (data) => {
      const first = data.items[0]?.strategy_id ?? null;
      setSelectedStrategyId((prev) =>
        prev && data.items.some((i) => i.strategy_id === prev) ? prev : first,
      );
    },
  });

  const hybridItems = hybridMutation.data?.items ?? [];
  const selectedItem = hybridItems.find((i) => i.strategy_id === selectedStrategyId) ?? hybridItems[0];

  useEffect(() => {
    if (profileId) hybridMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when profile changes
  }, [profileId]);

  const evidence = useMemo(() => {
    if (!selectedItem || !historyQuery.data?.length) return null;
    return computeAdoptionEvidence(
      historyQuery.data,
      selectedItem.adoption_probability,
      selectedItem.estimated_annual_savings,
    );
  }, [selectedItem, historyQuery.data]);

  const primaryImpactQuery = useQuery({
    queryKey: ["auditor-dashboard-impact-primary", profileId, selectedItem?.strategy_id],
    queryFn: () =>
      simulateImpact({
        profile_id: profileId,
        strategy_code: selectedItem!.strategy_id,
        horizon_years: AUDITOR_IMPACT_HORIZON_YEARS,
        n_paths: AUDITOR_IMPACT_N_PATHS,
        random_seed: 42,
      }),
    enabled: !!profileId && !!selectedItem?.strategy_id,
  });

  const refreshAll = () => {
    if (!profileId) return;
    queryClient.invalidateQueries({ queryKey: ["auditor-dashboard-profile", profileId] });
    queryClient.invalidateQueries({ queryKey: ["auditor-dashboard-features", profileId] });
    queryClient.invalidateQueries({ queryKey: ["auditor-dashboard-history", profileId] });
    hybridMutation.mutate();
    primaryImpactQuery.refetch();
  };

  const isRefreshing =
    profileQuery.isFetching ||
    featuresQuery.isFetching ||
    hybridMutation.isPending ||
    primaryImpactQuery.isFetching;

  const impactLoading = primaryImpactQuery.isLoading || hybridMutation.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={LayoutDashboard}
        title="Decision support dashboard"
        description="Unified case review — taxpayer context, ranked strategies, adoption evidence, and Monte Carlo impact."
      />

      <Card className="overflow-hidden border-border/70 shadow-sm">
        <div
          className="h-1.5 w-full"
          style={{
            background:
              "linear-gradient(90deg, var(--primary) 0%, var(--tax-accent) 55%, transparent 100%)",
          }}
          aria-hidden
        />
        <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-[220px] flex-1 max-w-md">
            <ProfilePicker value={profileId} onChange={setProfileId} label="Taxpayer profile" />
          </div>
          <Button
            type="button"
            variant="outline"
            disabled={!profileId || isRefreshing}
            onClick={refreshAll}
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh case
          </Button>
        </CardContent>
      </Card>

      {!profileId && (
        <Card className="border-dashed">
          <CardContent className="py-16 text-center">
            <p className="text-lg font-medium">Select a taxpayer to begin</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose a profile above or use the auditor workspace panel on the right.
            </p>
          </CardContent>
        </Card>
      )}

      {profileId && profileQuery.data && (
        <>
          <AuditorKpiStrip features={featuresQuery.data} topItem={selectedItem} />

          <div className="grid gap-6 xl:grid-cols-12">
            <div className="xl:col-span-4">
              <AuditorTaxpayerCard profile={profileQuery.data} features={featuresQuery.data} />
            </div>
            <div className="xl:col-span-8">
              <AuditorRecommendationsPanel
                items={hybridItems}
                selectedId={selectedItem?.strategy_id ?? null}
                onSelect={setSelectedStrategyId}
                isLoading={hybridMutation.isPending}
              />
            </div>
          </div>

          <AuditorAdoptionPanel
            evidence={evidence}
            strategyName={selectedItem?.name ?? "Strategy"}
            onOpenDetail={() => setEvidenceModalOpen(true)}
          />

          <AuditorImpactPanel
            profileId={profileId}
            primaryResult={primaryImpactQuery.data}
            selectedItem={selectedItem}
            isLoading={impactLoading}
            error={
              primaryImpactQuery.isError
                ? (primaryImpactQuery.error as Error).message
                : null
            }
            strategyName={selectedItem?.name ?? null}
          />
        </>
      )}

      <AuditorEvidenceModalHost
        open={evidenceModalOpen}
        evidence={evidence}
        strategyName={selectedItem?.name ?? "Strategy"}
        onClose={() => setEvidenceModalOpen(false)}
      />
    </div>
  );
}
