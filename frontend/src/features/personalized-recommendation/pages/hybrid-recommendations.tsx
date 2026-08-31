import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Filter, Loader2, Merge, SlidersHorizontal } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { hybridQuery } from "../api/hybrid";
import type { HybridResultItem, HybridRulesContext } from "../api/hybrid";
import { getProfileHistory } from "../api/profiles";
import { AdoptionEvidenceModal } from "../components/adoption-evidence-panel";
import { AuditorHybridRecommendationCard } from "../components/auditor-recommendations/recommendation-card";
import { StrategyExplanationModal } from "../components/auditor-recommendations/strategy-explanation-modal";
import { CatalogRulesSyncPanel } from "../components/catalog-rules-sync-panel";
import { PageHeader } from "../components/page-header";
import { ProfilePicker } from "../components/profile-picker";
import { useActiveProfileId } from "../store/dashboard-store";
import { computeAdoptionEvidence } from "../utils/adoption-evidence";

export function HybridRecommendationsPage() {
  const activeProfileId = useActiveProfileId();
  const [profileId, setProfileId] = useState<string>(activeProfileId ?? "");
  const [topK, setTopK] = useState<number>(5);
  const [useCatalogRules, setUseCatalogRules] = useState(false);
  const [assessmentYear, setAssessmentYear] = useState("2024_25");
  const [rulesContext, setRulesContext] = useState<HybridRulesContext | null>(null);
  const [evidenceItem, setEvidenceItem] = useState<HybridResultItem | null>(null);
  const [explainItem, setExplainItem] = useState<HybridResultItem | null>(null);

  useEffect(() => {
    if (activeProfileId && activeProfileId !== profileId) setProfileId(activeProfileId);
  }, [activeProfileId, profileId]);

  const hybridMutation = useMutation({
    mutationFn: () =>
      hybridQuery({
        profile_id: profileId,
        top_k: topK,
        rules_source: useCatalogRules ? "catalog" : "default",
        assessment_year: useCatalogRules ? assessmentYear : undefined,
      }),
    onSuccess: (data) => setRulesContext(data.rules_context),
  });

  useEffect(() => {
    if (profileId) hybridMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when profile, top_k, or catalog toggle changes
  }, [profileId, topK, useCatalogRules, assessmentYear]);

  const historyQuery = useQuery({
    queryKey: ["profile-history", profileId],
    queryFn: () => getProfileHistory(profileId, 36),
    enabled: profileId.length > 0,
  });

  const items = hybridMutation.data?.items ?? [];
  const evidence =
    evidenceItem && historyQuery.data
      ? computeAdoptionEvidence(
          historyQuery.data,
          evidenceItem.adoption_probability,
          evidenceItem.estimated_annual_savings,
        )
      : null;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Merge}
        title="Smart Recommendations"
        description="Hybrid-ranked strategies for the active taxpayer case."
      />

      <Card className="border-border/70 shadow-sm">
        <CardContent className="flex flex-col gap-4 p-4 sm:flex-row sm:items-end">
          <div className="min-w-[220px] flex-1 max-w-md">
            <ProfilePicker value={profileId} onChange={setProfileId} label="Taxpayer profile" />
          </div>
          <div className="w-full max-w-[120px] space-y-1.5">
            <Label>Top K</Label>
            <Select value={String(topK)} onChange={(e) => setTopK(Number(e.target.value))}>
              {[3, 5, 7, 10].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      <CatalogRulesSyncPanel
        useCatalogRules={useCatalogRules}
        onUseCatalogRulesChange={setUseCatalogRules}
        assessmentYear={assessmentYear}
        onAssessmentYearChange={setAssessmentYear}
        onSynced={() => {
          if (profileId) hybridMutation.mutate();
        }}
      />

      {!profileId && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            Select a taxpayer profile to generate recommendations.
          </CardContent>
        </Card>
      )}

      {profileId && (
        <>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-2xl font-bold tracking-tight">Tax Recommendations</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Ranked by AI · {items.length} active recommendation{items.length === 1 ? "" : "s"}
                {rulesContext && (
                  <>
                    {" "}
                    · Rules:{" "}
                    <span className="font-medium text-foreground">
                      {rulesContext.rules_source === "catalog"
                        ? `catalog YA ${rulesContext.assessment_year?.replace("_", "/")}`
                        : `default (${rulesContext.rules_version})`}
                    </span>
                    {rulesContext.rules_source === "catalog" && (
                      <>
                        {" "}
                        · baseline tax Rs.{" "}
                        {rulesContext.baseline_tax_lkr.toLocaleString("en-LK", {
                          maximumFractionDigits: 0,
                        })}
                      </>
                    )}
                  </>
                )}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                disabled
                title="Coming soon"
                className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium text-muted-foreground opacity-60"
              >
                <Filter className="h-3.5 w-3.5" />
                Filter
              </button>
              <button
                type="button"
                disabled
                title="Coming soon"
                className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium text-muted-foreground opacity-60"
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Sort
              </button>
            </div>
          </div>

          {hybridMutation.isPending && (
            <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Generating smart recommendations…
            </div>
          )}

          {hybridMutation.isError && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
              {(hybridMutation.error as Error).message}
            </div>
          )}

          {!hybridMutation.isPending && items.length > 0 && (
            <div className="mx-auto max-w-4xl space-y-4">
              {items.map((item) => (
                <AuditorHybridRecommendationCard
                  key={item.strategy_id}
                  item={item}
                  profileId={profileId}
                  onExplain={() => setExplainItem(item)}
                  onAdoptionEvidence={
                    historyQuery.data ? () => setEvidenceItem(item) : undefined
                  }
                />
              ))}
            </div>
          )}
        </>
      )}

      {evidence && evidenceItem && (
        <AdoptionEvidenceModal
          evidence={evidence}
          strategyName={evidenceItem.name}
          onClose={() => setEvidenceItem(null)}
        />
      )}

      {explainItem && (
        <StrategyExplanationModal
          item={explainItem}
          profileId={profileId}
          onClose={() => setExplainItem(null)}
        />
      )}
    </div>
  );
}
